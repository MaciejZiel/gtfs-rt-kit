from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def vehicles_bytes() -> bytes:
    return (FIXTURES / "vehicle_positions.pb").read_bytes()


@pytest.fixture
def trip_updates_bytes() -> bytes:
    return (FIXTURES / "trip_updates.pb").read_bytes()


@pytest.fixture
def alerts_bytes() -> bytes:
    return (FIXTURES / "alerts.pb").read_bytes()
