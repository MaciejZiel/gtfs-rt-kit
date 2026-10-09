"""Lazy loader for static GTFS archives (``.zip``).

Only the files you actually touch are parsed: opening a feed is cheap, reading
``stops`` parses ``stops.txt`` once and caches the result, and the potentially
large ``stop_times.txt`` is only read when schedule data is requested.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cached_property
from os import PathLike
from pathlib import Path
from typing import BinaryIO, TypeAlias
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import StaticGtfsError

__all__ = [
    "Agency",
    "Route",
    "StaticGtfs",
    "Stop",
    "StopTime",
    "Trip",
    "format_gtfs_time",
    "parse_gtfs_time",
]

# Basic and extended (https://developers.google.com/transit/gtfs/reference/extended-route-types)
# route types, reduced to a handful of modes.
_BASIC_MODES = {
    0: "tram",
    1: "subway",
    2: "rail",
    3: "bus",
    4: "ferry",
    5: "cable_tram",
    6: "aerial_lift",
    7: "funicular",
    11: "trolleybus",
    12: "monorail",
}
_EXTENDED_MODES = {
    1: "rail",
    2: "coach",
    4: "subway",
    7: "bus",
    8: "bus",
    9: "tram",
    10: "ferry",
    12: "funicular",
    13: "aerial_lift",
    14: "aerial_lift",
}


def parse_gtfs_time(value: str) -> int:
    """Convert a GTFS ``HH:MM:SS`` time (hours may exceed 23) to seconds after midnight.

    Raises:
        ValueError: if ``value`` is not a valid GTFS time.
    """
    parts = value.strip().split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid GTFS time: {value!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    if minutes > 59 or seconds > 59:
        raise ValueError(f"invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def format_gtfs_time(seconds: int) -> str:
    """Inverse of :func:`parse_gtfs_time`."""
    if seconds < 0:
        raise ValueError("GTFS times cannot be negative")
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True, slots=True)
class Agency:
    """A row of ``agency.txt``."""

    agency_id: str
    name: str
    url: str
    timezone: str


@dataclass(frozen=True, slots=True)
class Stop:
    """A row of ``stops.txt``."""

    stop_id: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    code: str | None = None
    parent_station: str | None = None
    location_type: int = 0


@dataclass(frozen=True, slots=True)
class Route:
    """A row of ``routes.txt``."""

    route_id: str
    short_name: str
    long_name: str
    route_type: int
    agency_id: str | None = None
    color: str | None = None
    text_color: str | None = None

    @property
    def name(self) -> str:
        """The short name if present, otherwise the long name."""
        return self.short_name or self.long_name

    @property
    def mode(self) -> str:
        """A coarse transport mode (``"bus"``, ``"tram"``, ``"subway"``, ...)."""
        if self.route_type in _BASIC_MODES:
            return _BASIC_MODES[self.route_type]
        return _EXTENDED_MODES.get(self.route_type // 100, "other")


@dataclass(frozen=True, slots=True)
class Trip:
    """A row of ``trips.txt``."""

    trip_id: str
    route_id: str
    service_id: str
    headsign: str | None = None
    direction_id: int | None = None
    shape_id: str | None = None
    block_id: str | None = None


@dataclass(frozen=True, slots=True)
class StopTime:
    """A row of ``stop_times.txt``; times are seconds after service-day midnight."""

    trip_id: str
    stop_sequence: int
    stop_id: str
    arrival: int | None = None
    departure: int | None = None


Source: TypeAlias = "str | PathLike[str] | bytes | BinaryIO"


class StaticGtfs:
    """A static GTFS feed backed by a zip archive.

    Args:
        source: Path to a ``.zip`` file, the archive's bytes, or a binary file object.

    Example:
        >>> gtfs = StaticGtfs("warsaw.zip")  # doctest: +SKIP
        >>> gtfs.route("15").mode  # doctest: +SKIP
        'tram'
    """

    def __init__(self, source: Source) -> None:
        if isinstance(source, bytes):
            self._source: Path | bytes = source
        elif isinstance(source, (str, PathLike)):
            self._source = Path(source)
            if not self._source.is_file():
                raise StaticGtfsError(f"GTFS archive not found: {self._source}")
        else:
            self._source = source.read()
        try:
            with self._open() as archive:
                self._names = frozenset(archive.namelist())
        except zipfile.BadZipFile as error:
            raise StaticGtfsError(f"not a valid GTFS zip archive: {error}") from error

    @classmethod
    def from_bytes(cls, data: bytes) -> StaticGtfs:
        """Load a feed from the bytes of a zip archive."""
        return cls(data)

    def _open(self) -> zipfile.ZipFile:
        if isinstance(self._source, bytes):
            return zipfile.ZipFile(io.BytesIO(self._source))
        return zipfile.ZipFile(self._source)

    @property
    def files(self) -> frozenset[str]:
        """Names of the files contained in the archive."""
        return self._names

    def has_file(self, name: str) -> bool:
        """Whether the archive contains ``name`` (for example ``"shapes.txt"``)."""
        return name in self._names

    def rows(self, name: str) -> Iterator[dict[str, str]]:
        """Stream the rows of any CSV file of the archive as dictionaries.

        Raises:
            StaticGtfsError: if the file does not exist.
        """
        if name not in self._names:
            raise StaticGtfsError(f"GTFS archive has no {name}")
        with (
            self._open() as archive,
            io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="") as text,
        ):
            for row in csv.DictReader(text):
                yield {key.strip(): (value or "").strip() for key, value in row.items() if key}

    # -- agencies ---------------------------------------------------------------

    @cached_property
    def agencies(self) -> Mapping[str, Agency]:
        """Agencies keyed by ``agency_id`` (an empty id when the column is omitted)."""
        result: dict[str, Agency] = {}
        for row in self.rows("agency.txt"):
            agency = Agency(
                agency_id=row.get("agency_id", ""),
                name=_required(row, "agency_name", "agency.txt"),
                url=row.get("agency_url", ""),
                timezone=_required(row, "agency_timezone", "agency.txt"),
            )
            result[agency.agency_id] = agency
        return result

    @cached_property
    def timezone(self) -> ZoneInfo:
        """Timezone of the feed, taken from the first agency."""
        agency = next(iter(self.agencies.values()), None)
        if agency is None:
            raise StaticGtfsError("agency.txt has no rows")
        try:
            return ZoneInfo(agency.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise StaticGtfsError(f"unknown agency timezone: {agency.timezone!r}") from error

    # -- stops ------------------------------------------------------------------

    @cached_property
    def stops(self) -> Mapping[str, Stop]:
        """Stops keyed by ``stop_id``."""
        result: dict[str, Stop] = {}
        for row in self.rows("stops.txt"):
            stop_id = _required(row, "stop_id", "stops.txt")
            result[stop_id] = Stop(
                stop_id=stop_id,
                name=row.get("stop_name", ""),
                latitude=_float(row.get("stop_lat")),
                longitude=_float(row.get("stop_lon")),
                code=row.get("stop_code") or None,
                parent_station=row.get("parent_station") or None,
                location_type=_int(row.get("location_type")) or 0,
            )
        return result

    def stop(self, stop_id: str) -> Stop | None:
        """The stop with ``stop_id``, if any."""
        return self.stops.get(stop_id)

    # -- routes -----------------------------------------------------------------

    @cached_property
    def routes(self) -> Mapping[str, Route]:
        """Routes keyed by ``route_id``."""
        result: dict[str, Route] = {}
        for row in self.rows("routes.txt"):
            route_id = _required(row, "route_id", "routes.txt")
            route_type = _int(row.get("route_type"))
            if route_type is None:
                raise StaticGtfsError(f"routes.txt: route {route_id!r} has no route_type")
            result[route_id] = Route(
                route_id=route_id,
                short_name=row.get("route_short_name", ""),
                long_name=row.get("route_long_name", ""),
                route_type=route_type,
                agency_id=row.get("agency_id") or None,
                color=row.get("route_color") or None,
                text_color=row.get("route_text_color") or None,
            )
        return result

    def route(self, route_id: str) -> Route | None:
        """The route with ``route_id``, if any."""
        return self.routes.get(route_id)

    @cached_property
    def _routes_by_name(self) -> Mapping[str, tuple[Route, ...]]:
        index: dict[str, list[Route]] = defaultdict(list)
        for route in self.routes.values():
            if route.short_name:
                index[route.short_name.casefold()].append(route)
        return {name: tuple(routes) for name, routes in index.items()}

    def routes_by_short_name(self, short_name: str) -> tuple[Route, ...]:
        """Routes whose short name equals ``short_name`` (case-insensitive)."""
        return self._routes_by_name.get(short_name.casefold(), ())

    def find_route(self, key: str) -> Route | None:
        """Look a route up by id first, then by short name."""
        route = self.route(key)
        if route is not None:
            return route
        matches = self.routes_by_short_name(key)
        return matches[0] if matches else None

    # -- trips ------------------------------------------------------------------

    @cached_property
    def trips(self) -> Mapping[str, Trip]:
        """Trips keyed by ``trip_id``."""
        result: dict[str, Trip] = {}
        for row in self.rows("trips.txt"):
            trip_id = _required(row, "trip_id", "trips.txt")
            result[trip_id] = Trip(
                trip_id=trip_id,
                route_id=_required(row, "route_id", "trips.txt"),
                service_id=row.get("service_id", ""),
                headsign=row.get("trip_headsign") or None,
                direction_id=_int(row.get("direction_id")),
                shape_id=row.get("shape_id") or None,
                block_id=row.get("block_id") or None,
            )
        return result

    def trip(self, trip_id: str) -> Trip | None:
        """The trip with ``trip_id``, if any."""
        return self.trips.get(trip_id)

    def trips_for_route(self, route_id: str) -> tuple[Trip, ...]:
        """All trips of ``route_id``."""
        return tuple(trip for trip in self.trips.values() if trip.route_id == route_id)

    # -- stop times -------------------------------------------------------------

    @cached_property
    def _stop_times(self) -> Mapping[str, tuple[StopTime, ...]]:
        index: dict[str, list[StopTime]] = defaultdict(list)
        for row in self.rows("stop_times.txt"):
            trip_id = _required(row, "trip_id", "stop_times.txt")
            sequence = _int(row.get("stop_sequence"))
            if sequence is None:
                raise StaticGtfsError(f"stop_times.txt: trip {trip_id!r} row has no stop_sequence")
            index[trip_id].append(
                StopTime(
                    trip_id=trip_id,
                    stop_sequence=sequence,
                    stop_id=_required(row, "stop_id", "stop_times.txt"),
                    arrival=_time(row.get("arrival_time")),
                    departure=_time(row.get("departure_time")),
                )
            )
        return {
            trip_id: tuple(sorted(rows, key=lambda row: row.stop_sequence))
            for trip_id, rows in index.items()
        }

    def stop_times(self, trip_id: str) -> tuple[StopTime, ...]:
        """Scheduled stop times of ``trip_id`` ordered by ``stop_sequence``.

        The first call parses ``stop_times.txt`` and indexes it by trip.
        """
        return self._stop_times.get(trip_id, ())


def _required(row: Mapping[str, str], column: str, filename: str) -> str:
    value = row.get(column, "")
    if not value:
        raise StaticGtfsError(f"{filename}: missing required column {column!r}")
    return value


def _float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _time(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return parse_gtfs_time(value)
    except ValueError as error:
        raise StaticGtfsError(f"stop_times.txt: {error}") from error
