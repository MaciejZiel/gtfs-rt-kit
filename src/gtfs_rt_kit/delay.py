"""Delay computation: realtime predictions compared with the static schedule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from .models import StopTimeEvent, StopTimeUpdate, TripUpdate, VehiclePosition
from .static import StaticGtfs, StopTime

__all__ = [
    "StopDelay",
    "estimate_vehicle_delay",
    "scheduled_datetime",
    "service_date_of",
    "trip_delays",
]


@dataclass(frozen=True, slots=True)
class StopDelay:
    """Delay of one stop of a trip, in seconds (positive means late)."""

    stop_sequence: int | None
    stop_id: str | None
    event: Literal["arrival", "departure"] | None
    scheduled: datetime | None
    predicted: datetime | None
    delay: int | None
    skipped: bool = False


def scheduled_datetime(service_date: date, seconds: int, tz: ZoneInfo) -> datetime:
    """Absolute time of a GTFS stop time.

    GTFS times count from "noon minus 12 hours" of the service day, which differs
    from midnight on days with a daylight-saving change, and may exceed 24:00:00.
    """
    noon = datetime.combine(service_date, time(12), tzinfo=tz)
    start = noon.astimezone(timezone.utc) - timedelta(hours=12)
    return (start + timedelta(seconds=seconds)).astimezone(tz)


def service_date_of(update: TripUpdate | VehiclePosition, tz: ZoneInfo) -> date | None:
    """Service date from the trip's ``start_date`` or, failing that, the local timestamp date."""
    trip = update.trip
    if trip is not None and trip.start_date:
        return datetime.strptime(trip.start_date, "%Y%m%d").date()
    if update.timestamp is not None:
        return update.timestamp.astimezone(tz).date()
    return None


def trip_delays(
    update: TripUpdate, static: StaticGtfs, *, service_date: date | None = None
) -> tuple[StopDelay, ...]:
    """Per-stop delays of a trip update compared with ``stop_times.txt``.

    For each stop time update the arrival is used when present, otherwise the
    departure. An explicit ``delay`` in the feed wins over ``time - scheduled``.
    Stops that cannot be matched to the schedule keep the feed's own delay, if any.
    """
    tz = static.timezone
    day = service_date or service_date_of(update, tz)
    schedule = static.stop_times(update.trip_id) if update.trip_id else ()
    by_sequence = {stop_time.stop_sequence: stop_time for stop_time in schedule}
    by_stop = {stop_time.stop_id: stop_time for stop_time in schedule}
    return tuple(
        _stop_delay(stop_update, by_sequence, by_stop, day, tz)
        for stop_update in update.stop_time_updates
    )


def _stop_delay(
    update: StopTimeUpdate,
    by_sequence: dict[int, StopTime],
    by_stop: dict[str, StopTime],
    day: date | None,
    tz: ZoneInfo,
) -> StopDelay:
    if update.stop_sequence is not None:
        scheduled_stop = by_sequence.get(update.stop_sequence)
    else:
        scheduled_stop = by_stop.get(update.stop_id or "")
    stop_id = update.stop_id or (scheduled_stop.stop_id if scheduled_stop else None)
    if update.schedule_relationship in {"SKIPPED", "NO_DATA"}:
        return StopDelay(
            stop_sequence=update.stop_sequence,
            stop_id=stop_id,
            event=None,
            scheduled=None,
            predicted=None,
            delay=None,
            skipped=update.schedule_relationship == "SKIPPED",
        )

    event: StopTimeEvent | None
    kind: Literal["arrival", "departure"] | None
    if update.arrival is not None:
        event, kind = update.arrival, "arrival"
    elif update.departure is not None:
        event, kind = update.departure, "departure"
    else:
        event, kind = None, None

    scheduled: datetime | None = None
    if scheduled_stop is not None and day is not None and kind is not None:
        primary = scheduled_stop.arrival if kind == "arrival" else scheduled_stop.departure
        fallback = scheduled_stop.departure if kind == "arrival" else scheduled_stop.arrival
        seconds = primary if primary is not None else fallback
        if seconds is not None:
            scheduled = scheduled_datetime(day, seconds, tz)
    if scheduled is None and event is not None and event.scheduled_time is not None:
        scheduled = event.scheduled_time.astimezone(tz)

    delay: int | None = None
    predicted: datetime | None = None
    if event is not None:
        if event.delay is not None:
            delay = event.delay
        elif event.time is not None and scheduled is not None:
            delay = round((event.time - scheduled).total_seconds())
        if event.time is not None:
            predicted = event.time.astimezone(tz)
        elif scheduled is not None and delay is not None:
            predicted = scheduled + timedelta(seconds=delay)

    return StopDelay(
        stop_sequence=update.stop_sequence,
        stop_id=stop_id,
        event=kind,
        scheduled=scheduled,
        predicted=predicted,
        delay=delay,
    )


def estimate_vehicle_delay(
    vehicle: VehiclePosition, static: StaticGtfs, *, service_date: date | None = None
) -> int | None:
    """Rough delay of a vehicle: its timestamp minus the scheduled time at its current stop.

    Only meaningful for vehicles reported ``STOPPED_AT`` (or with no status) at a stop;
    returns ``None`` when the trip, stop or timestamp is unknown.
    """
    if vehicle.trip_id is None or vehicle.timestamp is None:
        return None
    if vehicle.current_status not in {None, "STOPPED_AT"}:
        return None
    schedule = static.stop_times(vehicle.trip_id)
    stop_time = next(
        (
            row
            for row in schedule
            if (
                row.stop_sequence == vehicle.current_stop_sequence
                if vehicle.current_stop_sequence is not None
                else row.stop_id == vehicle.stop_id
            )
        ),
        None,
    )
    if stop_time is None:
        return None
    seconds = stop_time.arrival if stop_time.arrival is not None else stop_time.departure
    tz = static.timezone
    day = service_date or service_date_of(vehicle, tz)
    if seconds is None or day is None:
        return None
    return round((vehicle.timestamp - scheduled_datetime(day, seconds, tz)).total_seconds())
