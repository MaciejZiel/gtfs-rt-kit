"""Regenerate the GTFS-Realtime fixture feeds used by the test-suite.

The feeds are small, deterministic snapshots shaped like the Warsaw (ZTM) feeds,
consistent with the static GTFS fixture in ``static_gtfs/``. Run with::

    uv run python tests/fixtures/make_fixtures.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.transit import gtfs_realtime_pb2 as pb

HERE = Path(__file__).parent
# 2026-10-12 is a Monday; Warsaw is UTC+2 (CEST) on that day.
WARSAW = timezone(timedelta(hours=2))


def ts(hour: int, minute: int, second: int = 0) -> int:
    return int(datetime(2026, 10, 12, hour, minute, second, tzinfo=WARSAW).timestamp())


def header(message: pb.FeedMessage) -> None:
    message.header.gtfs_realtime_version = "2.0"
    message.header.incrementality = pb.FeedHeader.FULL_DATASET
    message.header.timestamp = ts(8, 6)


def vehicle_positions() -> pb.FeedMessage:
    message = pb.FeedMessage()
    header(message)

    v1 = message.entity.add(id="v1").vehicle
    v1.trip.trip_id = "T15-1"
    v1.trip.route_id = "15"
    v1.trip.start_date = "20261012"
    v1.trip.schedule_relationship = pb.TripDescriptor.SCHEDULED
    v1.vehicle.id = "V/15/1"
    v1.vehicle.label = "3101"
    v1.position.latitude = 52.2297
    v1.position.longitude = 21.0122
    v1.position.bearing = 90.0
    v1.position.speed = 8.5
    v1.current_stop_sequence = 2
    v1.stop_id = "S2"
    v1.current_status = pb.VehiclePosition.STOPPED_AT
    v1.timestamp = ts(8, 5, 50)
    v1.occupancy_status = pb.VehiclePosition.MANY_SEATS_AVAILABLE

    v2 = message.entity.add(id="v2").vehicle
    v2.trip.trip_id = "T175-1"
    v2.trip.route_id = "175"
    v2.vehicle.id = "V/175/2"
    v2.position.latitude = 52.2190
    v2.position.longitude = 20.9650
    v2.timestamp = ts(8, 4)

    # Warsaw-style vehicle without a trip descriptor: the line is encoded in the id.
    v3 = message.entity.add(id="v3").vehicle
    v3.vehicle.id = "V/15/7"
    v3.position.latitude = 52.2310
    v3.position.longitude = 21.0050

    # A vehicle without a position, identified only by its label.
    v4 = message.entity.add(id="v4").vehicle
    v4.vehicle.label = "M1-12"
    v4.trip.route_id = "M1"

    message.entity.add(id="v5", is_deleted=True)
    return message


def trip_updates() -> pb.FeedMessage:
    message = pb.FeedMessage()
    header(message)

    update = message.entity.add(id="tu1").trip_update
    update.trip.trip_id = "T15-1"
    update.trip.route_id = "15"
    update.trip.start_date = "20261012"
    update.vehicle.id = "V/15/1"
    update.timestamp = ts(8, 6)
    first = update.stop_time_update.add(stop_sequence=1, stop_id="S1")
    first.departure.delay = 60
    second = update.stop_time_update.add(stop_sequence=2, stop_id="S2")
    second.arrival.time = ts(8, 7, 30)
    second.arrival.uncertainty = 30
    third = update.stop_time_update.add(stop_sequence=3, stop_id="S3")
    third.arrival.delay = 120
    third.arrival.time = ts(8, 12)

    late = message.entity.add(id="tu2").trip_update
    late.trip.trip_id = "T175-1"
    late.trip.route_id = "175"
    late.delay = 300

    skipped = message.entity.add(id="tu3").trip_update
    skipped.trip.trip_id = "T15-NIGHT"
    skipped.trip.start_date = "20261012"
    skipped_stop = skipped.stop_time_update.add(stop_sequence=2, stop_id="S2")
    skipped_stop.schedule_relationship = pb.TripUpdate.StopTimeUpdate.SKIPPED
    night = skipped.stop_time_update.add(stop_sequence=1, stop_id="S1")
    night.departure.time = ts(0, 12) + 24 * 3600  # 00:12 on the next calendar day

    unknown = message.entity.add(id="tu4").trip_update
    unknown.trip.trip_id = "UNKNOWN"
    unknown.stop_time_update.add(stop_sequence=1).arrival.delay = 30
    return message


def alerts() -> pb.FeedMessage:
    message = pb.FeedMessage()
    header(message)

    detour = message.entity.add(id="a1").alert
    period = detour.active_period.add()
    period.start = ts(6, 0)
    period.end = ts(22, 0)
    detour.informed_entity.add(route_id="15")
    detour.cause = pb.Alert.CONSTRUCTION
    detour.effect = pb.Alert.DETOUR
    detour.severity_level = pb.Alert.WARNING
    detour.header_text.translation.add(text="Objazd linii 15", language="pl")
    detour.header_text.translation.add(text="Line 15 detour", language="en")
    detour.description_text.translation.add(text="Tramwaje kursują objazdem.")
    detour.url.translation.add(text="https://example.org/alerts/a1")

    closed = message.entity.add(id="a2").alert
    selector = closed.informed_entity.add(stop_id="S4")
    selector.trip.route_id = "175"
    closed.effect = pb.Alert.STOP_MOVED
    closed.active_period.add(start=ts(9, 0))
    return message


def main() -> None:
    feeds = {
        "vehicle_positions.pb": vehicle_positions(),
        "trip_updates.pb": trip_updates(),
        "alerts.pb": alerts(),
    }
    for name, message in feeds.items():
        (HERE / name).write_bytes(message.SerializeToString(deterministic=True))
        print(f"wrote {name} ({message.ByteSize()} bytes)")


if __name__ == "__main__":
    main()
