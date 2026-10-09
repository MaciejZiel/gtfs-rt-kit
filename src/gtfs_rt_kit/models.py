"""Typed, immutable models for GTFS-Realtime entities.

The models mirror the GTFS-Realtime specification but expose plain Python types:
optional protobuf fields become ``None`` when absent, POSIX timestamps become
timezone-aware :class:`~datetime.datetime` objects (UTC) and enums become their
specification names (for example ``"IN_TRANSIT_TO"``).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

__all__ = [
    "Alert",
    "EntitySelector",
    "Feed",
    "FeedHeader",
    "Position",
    "StopTimeEvent",
    "StopTimeUpdate",
    "TimeRange",
    "TranslatedString",
    "Translation",
    "TripDescriptor",
    "TripUpdate",
    "VehicleDescriptor",
    "VehiclePosition",
]


@dataclass(frozen=True, slots=True)
class FeedHeader:
    """Metadata of a feed message."""

    gtfs_realtime_version: str
    incrementality: str = "FULL_DATASET"
    timestamp: datetime | None = None
    feed_version: str | None = None


@dataclass(frozen=True, slots=True)
class TripDescriptor:
    """Identifies a trip instance (``TripDescriptor`` in the specification)."""

    trip_id: str | None = None
    route_id: str | None = None
    direction_id: int | None = None
    start_time: str | None = None
    start_date: str | None = None
    schedule_relationship: str | None = None


@dataclass(frozen=True, slots=True)
class VehicleDescriptor:
    """Identifies a physical vehicle."""

    id: str | None = None
    label: str | None = None
    license_plate: str | None = None


@dataclass(frozen=True, slots=True)
class Position:
    """Geographic position of a vehicle (WGS-84)."""

    latitude: float
    longitude: float
    bearing: float | None = None
    odometer: float | None = None
    speed: float | None = None


@dataclass(frozen=True, slots=True)
class VehiclePosition:
    """Realtime position of a vehicle, optionally linked to a trip."""

    entity_id: str
    trip: TripDescriptor | None = None
    vehicle: VehicleDescriptor | None = None
    position: Position | None = None
    current_stop_sequence: int | None = None
    stop_id: str | None = None
    current_status: str | None = None
    timestamp: datetime | None = None
    congestion_level: str | None = None
    occupancy_status: str | None = None
    occupancy_percentage: int | None = None

    @property
    def vehicle_id(self) -> str:
        """Best available identifier: vehicle id, then label, then the entity id."""
        if self.vehicle is not None:
            if self.vehicle.id:
                return self.vehicle.id
            if self.vehicle.label:
                return self.vehicle.label
        return self.entity_id

    @property
    def trip_id(self) -> str | None:
        """Trip id from the trip descriptor, if any."""
        return self.trip.trip_id if self.trip is not None else None

    @property
    def route_id(self) -> str | None:
        """Route id from the trip descriptor, if any."""
        return self.trip.route_id if self.trip is not None else None


@dataclass(frozen=True, slots=True)
class StopTimeEvent:
    """Predicted arrival or departure at a stop."""

    delay: int | None = None
    time: datetime | None = None
    uncertainty: int | None = None
    scheduled_time: datetime | None = None


@dataclass(frozen=True, slots=True)
class StopTimeUpdate:
    """Realtime update for one stop of a trip."""

    stop_sequence: int | None = None
    stop_id: str | None = None
    arrival: StopTimeEvent | None = None
    departure: StopTimeEvent | None = None
    schedule_relationship: str = "SCHEDULED"


@dataclass(frozen=True, slots=True)
class TripUpdate:
    """Realtime progress of a trip."""

    entity_id: str
    trip: TripDescriptor
    vehicle: VehicleDescriptor | None = None
    stop_time_updates: tuple[StopTimeUpdate, ...] = ()
    timestamp: datetime | None = None
    delay: int | None = None

    @property
    def trip_id(self) -> str | None:
        """Trip id from the trip descriptor."""
        return self.trip.trip_id

    @property
    def route_id(self) -> str | None:
        """Route id from the trip descriptor."""
        return self.trip.route_id


@dataclass(frozen=True, slots=True)
class Translation:
    """A single localized text."""

    text: str
    language: str | None = None


@dataclass(frozen=True, slots=True)
class TranslatedString:
    """A text available in one or more languages."""

    translations: tuple[Translation, ...] = ()

    def text(self, language: str | None = None) -> str | None:
        """Return the text in ``language``.

        Falls back to the translation without a language tag, then to the first one.
        """
        if not self.translations:
            return None
        if language is not None:
            wanted = language.casefold()
            for translation in self.translations:
                if translation.language and translation.language.casefold() == wanted:
                    return translation.text
        for translation in self.translations:
            if not translation.language:
                return translation.text
        return self.translations[0].text


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A time interval; an open end is ``None``."""

    start: datetime | None = None
    end: datetime | None = None

    def contains(self, moment: datetime) -> bool:
        """Whether ``moment`` (timezone-aware) falls into this range."""
        if self.start is not None and moment < self.start:
            return False
        return not (self.end is not None and moment > self.end)


@dataclass(frozen=True, slots=True)
class EntitySelector:
    """Selects the agency, route, trip or stop an alert applies to."""

    agency_id: str | None = None
    route_id: str | None = None
    route_type: int | None = None
    direction_id: int | None = None
    trip: TripDescriptor | None = None
    stop_id: str | None = None


@dataclass(frozen=True, slots=True)
class Alert:
    """A service alert."""

    entity_id: str
    active_periods: tuple[TimeRange, ...] = ()
    informed_entities: tuple[EntitySelector, ...] = ()
    cause: str = "UNKNOWN_CAUSE"
    effect: str = "UNKNOWN_EFFECT"
    severity_level: str = "UNKNOWN_SEVERITY"
    url: TranslatedString | None = None
    header_text: TranslatedString | None = None
    description_text: TranslatedString | None = None

    def is_active(self, moment: datetime) -> bool:
        """Whether the alert is active at ``moment``; no periods means always active."""
        if not self.active_periods:
            return True
        return any(period.contains(moment) for period in self.active_periods)

    def affects_route(self, route_id: str) -> bool:
        """Whether any informed entity references ``route_id`` (directly or via its trip)."""
        for selector in self.informed_entities:
            if selector.route_id == route_id:
                return True
            if selector.trip is not None and selector.trip.route_id == route_id:
                return True
        return False

    def affects_stop(self, stop_id: str) -> bool:
        """Whether any informed entity references ``stop_id``."""
        return any(selector.stop_id == stop_id for selector in self.informed_entities)


@dataclass(frozen=True, slots=True)
class Feed:
    """A decoded GTFS-Realtime ``FeedMessage``, split by entity type."""

    header: FeedHeader
    vehicles: tuple[VehiclePosition, ...] = ()
    trip_updates: tuple[TripUpdate, ...] = ()
    alerts: tuple[Alert, ...] = ()
    deleted_entity_ids: tuple[str, ...] = field(default=())

    @property
    def timestamp(self) -> datetime | None:
        """Timestamp of the feed header."""
        return self.header.timestamp

    def __len__(self) -> int:
        return len(self.vehicles) + len(self.trip_updates) + len(self.alerts)

    def __iter__(self) -> Iterator[VehiclePosition | TripUpdate | Alert]:
        yield from self.vehicles
        yield from self.trip_updates
        yield from self.alerts

    def vehicles_on_route(self, route_id: str) -> tuple[VehiclePosition, ...]:
        """Vehicles whose trip descriptor references ``route_id``."""
        return tuple(vehicle for vehicle in self.vehicles if vehicle.route_id == route_id)

    def trip_update_for(self, trip_id: str) -> TripUpdate | None:
        """The trip update for ``trip_id``, if present."""
        for update in self.trip_updates:
            if update.trip_id == trip_id:
                return update
        return None

    def alerts_for_route(self, route_id: str) -> tuple[Alert, ...]:
        """Alerts that reference ``route_id``."""
        return tuple(alert for alert in self.alerts if alert.affects_route(route_id))
