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


@pytest.fixture(scope="session")
def static_zip_bytes() -> bytes:
    """The static GTFS fixture directory packed into an in-memory zip archive."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted((FIXTURES / "static_gtfs").glob("*.txt")):
            archive.write(path, path.name)
    return buffer.getvalue()


@pytest.fixture
def static_zip(tmp_path: Path, static_zip_bytes: bytes) -> Path:
    path = tmp_path / "gtfs.zip"
    path.write_bytes(static_zip_bytes)
    return path
