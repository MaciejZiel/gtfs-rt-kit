from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from gtfs_rt_kit import StaticGtfsError
from gtfs_rt_kit.static import StaticGtfs, format_gtfs_time, parse_gtfs_time


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("00:00:00", 0), ("08:05:30", 29130), ("24:10:00", 87000), (" 7:00:00", 25200)],
)
def test_parse_gtfs_time(text: str, seconds: int) -> None:
    assert parse_gtfs_time(text) == seconds


@pytest.mark.parametrize("text", ["", "8:00", "08:60:00", "08:00:61", "ab:00:00"])
def test_parse_gtfs_time_rejects(text: str) -> None:
    with pytest.raises(ValueError, match="invalid GTFS time"):
        parse_gtfs_time(text)


def test_format_gtfs_time() -> None:
    assert format_gtfs_time(87000) == "24:10:00"
    with pytest.raises(ValueError, match="negative"):
        format_gtfs_time(-1)


def test_sources_are_equivalent(static_zip: Path, static_zip_bytes: bytes) -> None:
    from_path = StaticGtfs(static_zip)
    from_str = StaticGtfs(str(static_zip))
    from_bytes = StaticGtfs.from_bytes(static_zip_bytes)
    from_file = StaticGtfs(io.BytesIO(static_zip_bytes))
    for gtfs in (from_path, from_str, from_bytes, from_file):
        assert set(gtfs.stops) == {"S1", "S2", "S3", "S4"}
    assert from_path.has_file("calendar.txt")
    assert not from_path.has_file("shapes.txt")
    assert "routes.txt" in from_path.files


def test_lazy_loading(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    assert "stops" not in vars(gtfs)
    assert gtfs.stop("S1") is not None
    assert "stops" in vars(gtfs)
    assert "_stop_times" not in vars(gtfs)
    assert "trips" not in vars(gtfs)


def test_agency_and_timezone(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    agency = gtfs.agencies["ZTM"]
    assert agency.name == "Warszawski Transport Publiczny"
    assert agency.timezone == "Europe/Warsaw"
    assert str(gtfs.timezone) == "Europe/Warsaw"


def test_stops(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    centrum = gtfs.stop("S1")
    assert centrum is not None
    assert centrum.name == "Centrum"
    assert centrum.latitude == pytest.approx(52.2311)
    assert centrum.code == "01"
    airport = gtfs.stops["S4"]
    assert airport.code is None
    assert airport.location_type == 0
    assert airport.parent_station is None
    assert gtfs.stop("nope") is None


def test_routes(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    tram = gtfs.route("15")
    assert tram is not None
    assert tram.mode == "tram"
    assert tram.color == "B60000"
    assert tram.agency_id == "ZTM"
    assert gtfs.routes["175"].mode == "bus"
    assert gtfs.routes["M1"].mode == "subway"
    assert gtfs.routes["N91"].mode == "bus"
    assert gtfs.routes_by_short_name("n91")[0].route_id == "N91"
    assert gtfs.routes_by_short_name("999") == ()
    found = gtfs.find_route("m1")
    assert found is not None
    assert found.route_id == "M1"
    assert gtfs.find_route("999") is None


@pytest.mark.parametrize(
    ("route_type", "mode"),
    [(2, "rail"), (11, "trolleybus"), (900, "tram"), (401, "subway"), (1700, "other")],
)
def test_route_modes(route_type: int, mode: str) -> None:
    from gtfs_rt_kit.static import Route

    assert Route("r", "1", "", route_type).mode == mode


def test_route_name_falls_back_to_long_name() -> None:
    from gtfs_rt_kit.static import Route

    assert Route("r", "", "Airport Express", 2).name == "Airport Express"


def test_trips(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    trip = gtfs.trip("T15-1")
    assert trip is not None
    assert trip.route_id == "15"
    assert trip.headsign == "P+R Al. Krakowska"
    assert trip.direction_id == 0
    assert trip.shape_id == "SH15"
    assert gtfs.trips["T175-1"].block_id == "B1"
    assert gtfs.trips["T15-NIGHT"].direction_id is None
    assert [t.trip_id for t in gtfs.trips_for_route("15")] == ["T15-1", "T15-NIGHT"]
    assert gtfs.trip("nope") is None


def test_stop_times(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    rows = gtfs.stop_times("T15-1")
    assert [row.stop_sequence for row in rows] == [1, 2, 3]
    assert rows[1].arrival == parse_gtfs_time("08:05:00")
    assert rows[1].departure == parse_gtfs_time("08:05:30")
    untimed = gtfs.stop_times("T175-1")[1]
    assert untimed.arrival is None
    assert untimed.departure is None
    assert gtfs.stop_times("T15-NIGHT")[1].departure is None
    assert gtfs.stop_times("nope") == ()


def test_rows_of_optional_file(static_zip_bytes: bytes) -> None:
    gtfs = StaticGtfs(static_zip_bytes)
    rows = list(gtfs.rows("calendar.txt"))
    assert rows[0]["service_id"] == "WD"
    with pytest.raises(StaticGtfsError, match=r"no shapes\.txt"):
        list(gtfs.rows("shapes.txt"))


def test_missing_archive(tmp_path: Path) -> None:
    with pytest.raises(StaticGtfsError, match="not found"):
        StaticGtfs(tmp_path / "missing.zip")


def test_bad_zip() -> None:
    with pytest.raises(StaticGtfsError, match="not a valid GTFS zip"):
        StaticGtfs(b"not a zip")


@pytest.mark.parametrize(
    ("files", "attribute", "message"),
    [
        ({"agency.txt": "agency_id,agency_name\nA,Agency\n"}, "agencies", "agency_timezone"),
        ({"agency.txt": "agency_name,agency_timezone\n"}, "timezone", "no rows"),
        ({"agency.txt": "agency_name,agency_timezone\nA,Mars/Base\n"}, "timezone", "Mars/Base"),
        ({"stops.txt": "stop_name\nX\n"}, "stops", "stop_id"),
        ({"routes.txt": "route_id,route_type\nR,\n"}, "routes", "route_type"),
        ({"trips.txt": "trip_id,route_id\nT,\n"}, "trips", "route_id"),
        ({"stop_times.txt": "trip_id,stop_id\nT,S\n"}, "_stop_times", "stop_sequence"),
        (
            {"stop_times.txt": "trip_id,stop_id,stop_sequence,arrival_time\nT,S,1,8am\n"},
            "_stop_times",
            "invalid GTFS time",
        ),
    ],
)
def test_malformed_files(files: dict[str, str], attribute: str, message: str) -> None:
    gtfs = StaticGtfs(make_zip(files))
    with pytest.raises(StaticGtfsError, match=message):
        getattr(gtfs, attribute)


def test_lenient_numbers() -> None:
    gtfs = StaticGtfs(
        make_zip({"stops.txt": "stop_id,stop_lat,stop_lon,location_type\nX,north,,station\n"})
    )
    stop = gtfs.stops["X"]
    assert stop.latitude is None
    assert stop.longitude is None
    assert stop.location_type == 0
