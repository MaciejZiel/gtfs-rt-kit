from __future__ import annotations

from datetime import date, datetime, timezone

from gtfs_rt_kit import Position, VehiclePosition
from gtfs_rt_kit.serialize import to_jsonable


def test_to_jsonable() -> None:
    vehicle = VehiclePosition(
        entity_id="v",
        position=Position(1.0, 2.0),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    data = to_jsonable({"v": vehicle, "day": date(2026, 1, 2), "tags": frozenset({"a"})})
    assert data["v"]["position"] == {
        "latitude": 1.0,
        "longitude": 2.0,
        "bearing": None,
        "odometer": None,
        "speed": None,
    }
    assert data["v"]["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert data["day"] == "2026-01-02"
    assert data["tags"] == ["a"]
    assert to_jsonable(VehiclePosition) is VehiclePosition
