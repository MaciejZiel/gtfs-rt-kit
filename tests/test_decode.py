from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gtfs_rt_kit import FeedDecodeError, load_feed, parse_feed

WARSAW = timezone(timedelta(hours=2))


def test_header(vehicles_bytes: bytes) -> None:
    feed = parse_feed(vehicles_bytes)
    assert feed.header.gtfs_realtime_version == "2.0"
    assert feed.header.incrementality == "FULL_DATASET"
    assert feed.header.feed_version is None
    assert feed.timestamp == datetime(2026, 10, 12, 8, 6, tzinfo=WARSAW)
    assert feed.timestamp is not None
    assert feed.timestamp.tzinfo is timezone.utc


def test_vehicle_positions(vehicles_bytes: bytes) -> None:
    feed = parse_feed(vehicles_bytes)
    assert [v.entity_id for v in feed.vehicles] == ["v1", "v2", "v3", "v4"]
    assert feed.deleted_entity_ids == ("v5",)
    assert not feed.trip_updates
    assert not feed.alerts

    v1 = feed.vehicles[0]
    assert v1.vehicle_id == "V/15/1"
    assert v1.trip_id == "T15-1"
    assert v1.route_id == "15"
    assert v1.trip is not None
    assert v1.trip.start_date == "20261012"
    assert v1.trip.schedule_relationship == "SCHEDULED"
    assert v1.trip.direction_id is None
    assert v1.vehicle is not None
    assert v1.vehicle.label == "3101"
    assert v1.vehicle.license_plate is None
    assert v1.position is not None
    assert v1.position.latitude == pytest.approx(52.2297)
    assert v1.position.longitude == pytest.approx(21.0122)
    assert v1.position.bearing == pytest.approx(90.0)
    assert v1.position.speed == pytest.approx(8.5)
    assert v1.position.odometer is None
    assert v1.current_stop_sequence == 2
    assert v1.stop_id == "S2"
    assert v1.current_status == "STOPPED_AT"
    assert v1.occupancy_status == "MANY_SEATS_AVAILABLE"
    assert v1.congestion_level is None
    assert v1.occupancy_percentage is None
    assert v1.timestamp == datetime(2026, 10, 12, 8, 5, 50, tzinfo=WARSAW)


def test_vehicle_identifier_fallbacks(vehicles_bytes: bytes) -> None:
    feed = parse_feed(vehicles_bytes)
    v3, v4 = feed.vehicles[2], feed.vehicles[3]
    assert v3.trip is None
    assert v3.route_id is None
    assert v3.trip_id is None
    assert v3.timestamp is None
    assert v4.vehicle_id == "M1-12"
    assert v4.position is None
    assert v4.route_id == "M1"


def test_vehicle_id_falls_back_to_entity_id() -> None:
    from gtfs_rt_kit import VehicleDescriptor, VehiclePosition

    assert VehiclePosition(entity_id="e1").vehicle_id == "e1"
    assert VehiclePosition(entity_id="e2", vehicle=VehicleDescriptor()).vehicle_id == "e2"


def test_trip_updates(trip_updates_bytes: bytes) -> None:
    feed = parse_feed(trip_updates_bytes)
    assert [u.entity_id for u in feed.trip_updates] == ["tu1", "tu2", "tu3", "tu4"]
    tu1 = feed.trip_updates[0]
    assert tu1.trip_id == "T15-1"
    assert tu1.route_id == "15"
    assert tu1.vehicle is not None
    assert tu1.vehicle.id == "V/15/1"
    assert tu1.delay is None
    assert tu1.timestamp == datetime(2026, 10, 12, 8, 6, tzinfo=WARSAW)
    first, second, third = tu1.stop_time_updates
    assert first.stop_sequence == 1
    assert first.arrival is None
    assert first.departure is not None
    assert first.departure.delay == 60
    assert first.departure.time is None
    assert second.arrival is not None
    assert second.arrival.time == datetime(2026, 10, 12, 8, 7, 30, tzinfo=WARSAW)
    assert second.arrival.uncertainty == 30
    assert second.arrival.scheduled_time is None
    assert third.arrival is not None
    assert third.arrival.delay == 120
    assert third.schedule_relationship == "SCHEDULED"

    assert feed.trip_updates[1].delay == 300
    assert feed.trip_updates[1].stop_time_updates == ()
    assert feed.trip_updates[2].stop_time_updates[0].schedule_relationship == "SKIPPED"
    assert feed.trip_updates[3].route_id is None
    assert feed.trip_updates[3].stop_time_updates[0].stop_id is None


def test_alerts(alerts_bytes: bytes) -> None:
    feed = parse_feed(alerts_bytes)
    detour, closed = feed.alerts
    assert detour.cause == "CONSTRUCTION"
    assert detour.effect == "DETOUR"
    assert detour.severity_level == "WARNING"
    assert detour.header_text is not None
    assert detour.header_text.text("en") == "Line 15 detour"
    assert detour.header_text.text("PL") == "Objazd linii 15"
    assert detour.description_text is not None
    assert detour.description_text.text() == "Tramwaje kursują objazdem."
    assert detour.url is not None
    assert detour.url.text("de") == "https://example.org/alerts/a1"
    assert detour.informed_entities[0].route_id == "15"
    assert detour.active_periods[0].start == datetime(2026, 10, 12, 6, tzinfo=WARSAW)

    assert closed.cause == "UNKNOWN_CAUSE"
    assert closed.effect == "STOP_MOVED"
    assert closed.header_text is None
    assert closed.active_periods[0].end is None
    selector = closed.informed_entities[0]
    assert selector.stop_id == "S4"
    assert selector.trip is not None
    assert selector.trip.route_id == "175"
    assert selector.route_id is None


def test_load_feed_from_path(fixtures_dir: Path) -> None:
    feed = load_feed(fixtures_dir / "alerts.pb")
    assert len(feed.alerts) == 2


@pytest.mark.parametrize("payload", [b"\xff\xff\xff", b"\x0a\x05garbage"])
def test_invalid_payload(payload: bytes) -> None:
    with pytest.raises(FeedDecodeError, match="invalid GTFS-Realtime payload"):
        parse_feed(payload)


def test_missing_header() -> None:
    with pytest.raises(FeedDecodeError, match="missing feed header"):
        parse_feed(b"")
