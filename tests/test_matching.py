from __future__ import annotations

import pytest

from gtfs_rt_kit import TripDescriptor, VehicleDescriptor, VehiclePosition, parse_feed
from gtfs_rt_kit.matching import filter_by_route, match_vehicle, match_vehicles
from gtfs_rt_kit.static import StaticGtfs
from gtfs_rt_kit.warsaw import route_from_vehicle_id


@pytest.fixture
def gtfs(static_zip_bytes: bytes) -> StaticGtfs:
    return StaticGtfs(static_zip_bytes)


def test_match_feed(vehicles_bytes: bytes, gtfs: StaticGtfs) -> None:
    matched = match_vehicles(parse_feed(vehicles_bytes), gtfs)
    by_id = {item.vehicle.entity_id: item for item in matched}
    assert by_id["v1"].trip is not None
    assert by_id["v1"].trip.headsign == "P+R Al. Krakowska"
    assert by_id["v1"].line == "15"
    assert by_id["v1"].mode == "tram"
    assert by_id["v2"].mode == "bus"
    assert by_id["v3"].route is None
    assert by_id["v3"].line is None
    assert by_id["v3"].mode is None
    assert by_id["v4"].route is not None
    assert by_id["v4"].route.route_id == "M1"


def test_route_hint(vehicles_bytes: bytes, gtfs: StaticGtfs) -> None:
    feed = parse_feed(vehicles_bytes)
    matched = match_vehicles(feed.vehicles, gtfs, route_hint=route_from_vehicle_id)
    v3 = matched[2]
    assert v3.route is not None
    assert v3.route.short_name == "15"
    assert [m.vehicle.entity_id for m in filter_by_route(matched, "15")] == ["v1", "v3"]


def test_route_resolved_through_trip(gtfs: StaticGtfs) -> None:
    vehicle = VehiclePosition(entity_id="x", trip=TripDescriptor(trip_id="T175-1"))
    matched = match_vehicle(vehicle, gtfs)
    assert matched.route is not None
    assert matched.route.route_id == "175"
    assert matched.route_key == "175"


def test_unknown_route_keeps_key(gtfs: StaticGtfs) -> None:
    vehicle = VehiclePosition(
        entity_id="x",
        trip=TripDescriptor(route_id="999"),
        vehicle=VehicleDescriptor(id="V/999/1"),
    )
    matched = match_vehicle(vehicle, gtfs, route_hint=route_from_vehicle_id)
    assert matched.route is None
    assert matched.line == "999"
    assert filter_by_route([matched], "999") == [matched]
    assert filter_by_route([matched], "15") == []


def test_filter_is_case_insensitive(gtfs: StaticGtfs) -> None:
    night = match_vehicle(VehiclePosition(entity_id="n", trip=TripDescriptor(route_id="N91")), gtfs)
    assert filter_by_route([night], "n91") == [night]


@pytest.mark.parametrize(
    ("vehicle_id", "expected"),
    [("V/15/7", "15"), ("V/N91/188", "N91"), ("15/7", None), ("V//1", None), ("X/1/2", None)],
)
def test_warsaw_route_from_vehicle_id(vehicle_id: str, expected: str | None) -> None:
    vehicle = VehiclePosition(entity_id="e", vehicle=VehicleDescriptor(id=vehicle_id))
    assert route_from_vehicle_id(vehicle) == expected
