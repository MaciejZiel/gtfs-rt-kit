from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from gtfs_rt_kit import (
    StopTimeEvent,
    StopTimeUpdate,
    TripDescriptor,
    TripUpdate,
    VehiclePosition,
    parse_feed,
)
from gtfs_rt_kit.delay import (
    estimate_vehicle_delay,
    scheduled_datetime,
    service_date_of,
    trip_delays,
)
from gtfs_rt_kit.static import StaticGtfs

WARSAW = ZoneInfo("Europe/Warsaw")
DAY = date(2026, 10, 12)


@pytest.fixture
def gtfs(static_zip_bytes: bytes) -> StaticGtfs:
    return StaticGtfs(static_zip_bytes)


def test_scheduled_datetime_handles_overnight_and_dst() -> None:
    assert scheduled_datetime(DAY, 8 * 3600, WARSAW) == datetime(2026, 10, 12, 8, tzinfo=WARSAW)
    after_midnight = scheduled_datetime(DAY, 24 * 3600 + 600, WARSAW)
    assert after_midnight == datetime(2026, 10, 13, 0, 10, tzinfo=WARSAW)
    # 2026-10-25: clocks go back at 03:00, so "noon minus 12h" is 01:00 local time.
    fall_back = scheduled_datetime(date(2026, 10, 25), 0, WARSAW)
    assert fall_back == datetime(2026, 10, 25, 1, tzinfo=WARSAW)
    # 2026-03-29: clocks go forward at 02:00, so the service day starts at 23:00 the day before.
    spring_forward = scheduled_datetime(date(2026, 3, 29), 0, WARSAW)
    assert spring_forward == datetime(2026, 3, 28, 23, tzinfo=WARSAW)


def test_trip_delays(trip_updates_bytes: bytes, gtfs: StaticGtfs) -> None:
    feed = parse_feed(trip_updates_bytes)
    update = feed.trip_update_for("T15-1")
    assert update is not None
    first, second, third = trip_delays(update, gtfs)

    assert first.event == "departure"
    assert first.delay == 60
    assert first.scheduled == datetime(2026, 10, 12, 8, 0, tzinfo=WARSAW)
    assert first.predicted == datetime(2026, 10, 12, 8, 1, tzinfo=WARSAW)

    assert second.event == "arrival"
    assert second.delay == 150
    assert second.predicted == datetime(2026, 10, 12, 8, 7, 30, tzinfo=WARSAW)

    assert third.delay == 120
    assert third.stop_id == "S3"
    assert not third.skipped


def test_overnight_trip_and_skipped_stop(trip_updates_bytes: bytes, gtfs: StaticGtfs) -> None:
    update = parse_feed(trip_updates_bytes).trip_update_for("T15-NIGHT")
    assert update is not None
    skipped, night = trip_delays(update, gtfs)
    assert skipped.skipped
    assert skipped.delay is None
    assert skipped.event is None
    assert night.scheduled == datetime(2026, 10, 13, 0, 10, tzinfo=WARSAW)
    assert night.delay == 120


def test_unknown_trip_keeps_feed_delay(trip_updates_bytes: bytes, gtfs: StaticGtfs) -> None:
    update = parse_feed(trip_updates_bytes).trip_update_for("UNKNOWN")
    assert update is not None
    (only,) = trip_delays(update, gtfs, service_date=DAY)
    assert only.delay == 30
    assert only.scheduled is None
    assert only.predicted is None
    assert only.stop_id is None


def test_match_by_stop_id_and_fallbacks(gtfs: StaticGtfs) -> None:
    update = TripUpdate(
        entity_id="x",
        trip=TripDescriptor(trip_id="T175-1"),
        stop_time_updates=(
            # Matched by stop id, arrival missing in schedule -> falls back to departure.
            StopTimeUpdate(stop_id="S4", arrival=StopTimeEvent(delay=-30)),
            # Untimed stop with a feed-provided scheduled time.
            StopTimeUpdate(
                stop_sequence=2,
                arrival=StopTimeEvent(
                    time=datetime(2026, 10, 12, 6, 20, tzinfo=ZoneInfo("UTC")),
                    scheduled_time=datetime(2026, 10, 12, 6, 15, tzinfo=ZoneInfo("UTC")),
                ),
            ),
            StopTimeUpdate(stop_sequence=3),
            StopTimeUpdate(stop_sequence=1, schedule_relationship="NO_DATA"),
        ),
    )
    airport, untimed, empty, no_data = trip_delays(update, gtfs, service_date=DAY)
    assert airport.stop_sequence is None
    assert airport.scheduled == datetime(2026, 10, 12, 8, 30, tzinfo=WARSAW)
    assert airport.delay == -30
    assert airport.predicted == datetime(2026, 10, 12, 8, 29, 30, tzinfo=WARSAW)
    assert untimed.stop_id == "S3"
    assert untimed.delay == 300
    assert empty.event is None
    assert empty.delay is None
    assert no_data.event is None
    assert not no_data.skipped


def test_departure_only_schedule_falls_back_to_arrival(gtfs: StaticGtfs) -> None:
    update = TripUpdate(
        entity_id="x",
        trip=TripDescriptor(trip_id="T15-NIGHT", start_date="20261012"),
        stop_time_updates=(StopTimeUpdate(stop_sequence=2, departure=StopTimeEvent(delay=10)),),
    )
    (only,) = trip_delays(update, gtfs)
    assert only.scheduled == datetime(2026, 10, 13, 0, 15, tzinfo=WARSAW)


def test_service_date_of() -> None:
    assert service_date_of(TripUpdate("x", TripDescriptor(start_date="20261012")), WARSAW) == DAY
    late = VehiclePosition(
        entity_id="v", timestamp=datetime(2026, 10, 12, 22, 30, tzinfo=ZoneInfo("UTC"))
    )
    assert service_date_of(late, WARSAW) == date(2026, 10, 13)
    assert service_date_of(VehiclePosition(entity_id="v"), WARSAW) is None


def test_trip_without_date_has_no_schedule(gtfs: StaticGtfs) -> None:
    update = TripUpdate(
        entity_id="x",
        trip=TripDescriptor(trip_id="T15-1"),
        stop_time_updates=(StopTimeUpdate(stop_sequence=1, arrival=StopTimeEvent(delay=5)),),
    )
    (only,) = trip_delays(update, gtfs)
    assert only.scheduled is None
    assert only.delay == 5


def test_estimate_vehicle_delay(vehicles_bytes: bytes, gtfs: StaticGtfs) -> None:
    feed = parse_feed(vehicles_bytes)
    v1 = feed.vehicles[0]
    # Stopped at S2 at 08:05:50, scheduled arrival 08:05:00.
    assert estimate_vehicle_delay(v1, gtfs) == 50
    assert estimate_vehicle_delay(feed.vehicles[2], gtfs) is None


def test_estimate_vehicle_delay_edge_cases(gtfs: StaticGtfs) -> None:
    moment = datetime(2026, 10, 12, 8, 1, tzinfo=WARSAW)
    by_stop = VehiclePosition(
        entity_id="v", trip=TripDescriptor(trip_id="T15-1"), stop_id="S1", timestamp=moment
    )
    assert estimate_vehicle_delay(by_stop, gtfs) == 60
    moving = VehiclePosition(
        entity_id="v",
        trip=TripDescriptor(trip_id="T15-1"),
        stop_id="S1",
        timestamp=moment,
        current_status="IN_TRANSIT_TO",
    )
    assert estimate_vehicle_delay(moving, gtfs) is None
    unknown_stop = VehiclePosition(
        entity_id="v", trip=TripDescriptor(trip_id="T15-1"), stop_id="S9", timestamp=moment
    )
    assert estimate_vehicle_delay(unknown_stop, gtfs) is None
    untimed = VehiclePosition(
        entity_id="v",
        trip=TripDescriptor(trip_id="T175-1"),
        current_stop_sequence=2,
        timestamp=moment,
    )
    assert estimate_vehicle_delay(untimed, gtfs, service_date=DAY) is None
