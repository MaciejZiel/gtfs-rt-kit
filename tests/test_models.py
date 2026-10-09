from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from gtfs_rt_kit import (
    Alert,
    EntitySelector,
    Feed,
    TimeRange,
    TranslatedString,
    Translation,
    VehiclePosition,
    parse_feed,
)

UTC = timezone.utc
NOON = datetime(2026, 10, 12, 12, tzinfo=UTC)


def test_models_are_frozen() -> None:
    vehicle = VehiclePosition(entity_id="x")
    with pytest.raises(FrozenInstanceError):
        vehicle.entity_id = "y"  # type: ignore[misc]


def test_translated_string() -> None:
    assert TranslatedString().text() is None
    tagged = TranslatedString((Translation("Hallo", "de"), Translation("Hello", "en")))
    assert tagged.text() == "Hallo"
    assert tagged.text("fr") == "Hallo"
    mixed = TranslatedString((Translation("Hello", "en"), Translation("Cześć")))
    assert mixed.text() == "Cześć"
    assert mixed.text("EN") == "Hello"


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (TimeRange(), True),
        (TimeRange(start=NOON), True),
        (TimeRange(start=NOON + timedelta(seconds=1)), False),
        (TimeRange(end=NOON - timedelta(seconds=1)), False),
        (TimeRange(start=NOON - timedelta(hours=1), end=NOON + timedelta(hours=1)), True),
    ],
)
def test_time_range_contains(period: TimeRange, expected: bool) -> None:
    assert period.contains(NOON) is expected


def test_alert_is_active() -> None:
    assert Alert(entity_id="a").is_active(NOON)
    past = Alert(entity_id="b", active_periods=(TimeRange(end=NOON - timedelta(days=1)),))
    assert not past.is_active(NOON)


def test_alert_selectors() -> None:
    alert = Alert(
        entity_id="a",
        informed_entities=(EntitySelector(stop_id="S1"), EntitySelector(agency_id="ZTM")),
    )
    assert alert.affects_stop("S1")
    assert not alert.affects_stop("S2")
    assert not alert.affects_route("15")


def test_feed_helpers(
    vehicles_bytes: bytes, trip_updates_bytes: bytes, alerts_bytes: bytes
) -> None:
    vehicles = parse_feed(vehicles_bytes)
    assert len(vehicles) == 4
    assert [v.entity_id for v in vehicles.vehicles_on_route("15")] == ["v1"]
    assert vehicles.vehicles_on_route("999") == ()

    updates = parse_feed(trip_updates_bytes)
    found = updates.trip_update_for("T175-1")
    assert found is not None
    assert found.delay == 300
    assert updates.trip_update_for("nope") is None

    alerts = parse_feed(alerts_bytes)
    assert [a.entity_id for a in alerts.alerts_for_route("15")] == ["a1"]
    assert [a.entity_id for a in alerts.alerts_for_route("175")] == ["a2"]
    active = [a.entity_id for a in alerts.alerts if a.is_active(NOON)]
    assert active == ["a1", "a2"]

    combined = Feed(
        header=vehicles.header,
        vehicles=vehicles.vehicles,
        trip_updates=updates.trip_updates,
        alerts=alerts.alerts,
    )
    assert len(list(combined)) == len(combined) == 10
