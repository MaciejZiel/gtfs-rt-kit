from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from gtfs_rt_kit import FeedFetchError
from gtfs_rt_kit.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
VEHICLES = str(FIXTURES / "vehicle_positions.pb")
TRIP_UPDATES = str(FIXTURES / "trip_updates.pb")
ALERTS = str(FIXTURES / "alerts.pb")


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(list(argv), out=out)
    return code, out.getvalue()


def run_json(*argv: str) -> Any:
    code, text = run(*argv, "--json")
    assert code == 0
    return json.loads(text)


def test_vehicles_table() -> None:
    code, text = run("vehicles", VEHICLES)
    assert code == 0
    lines = text.splitlines()
    assert lines[0].split() == ["VEHICLE", "LINE", "TRIP", "LAT", "LON", "TIMESTAMP"]
    assert "V/15/1" in lines[1]
    assert "52.22970" in lines[1]
    assert "2026-10-12T06:05:50Z" in lines[1]
    assert lines[-1] == "4 vehicle(s), feed time 2026-10-12T06:06:00Z"


def test_vehicles_json_route_filter() -> None:
    payload = run_json("vehicles", VEHICLES, "--route", "15")
    assert [item["entity_id"] for item in payload] == ["v1"]
    assert payload[0]["vehicle_id"] == "V/15/1"
    assert payload[0]["timestamp"] == "2026-10-12T06:05:50+00:00"
    assert payload[0]["position"]["bearing"] == 90.0
    assert payload[0]["mode"] is None


def test_vehicles_warsaw_hint() -> None:
    payload = run_json("vehicles", VEHICLES, "--route", "15", "--warsaw")
    assert [item["entity_id"] for item in payload] == ["v1", "v3"]
    assert payload[1]["line"] == "15"


def test_vehicles_with_static(static_zip: Path) -> None:
    payload = run_json("vehicles", VEHICLES, "--static", str(static_zip), "--route", "m1")
    assert [item["vehicle_id"] for item in payload] == ["M1-12"]
    assert payload[0]["mode"] == "subway"
    tram = run_json("vehicles", VEHICLES, "--static", str(static_zip), "--route", "15")
    assert tram[0]["headsign"] == "P+R Al. Krakowska"
    code, text = run("vehicles", VEHICLES, "--static", str(static_zip))
    assert code == 0
    assert any(line.split()[:3] == ["M1-12", "M1", "-"] for line in text.splitlines())


def test_trip_updates_table(static_zip: Path) -> None:
    code, text = run("trip-updates", TRIP_UPDATES, "--static", str(static_zip))
    assert code == 0
    rows = {line.split()[0]: line.split() for line in text.splitlines()[1:-1]}
    assert rows["T15-1"][-1] == "+120s"
    assert rows["T175-1"][-1] == "+300s"
    assert rows["T15-NIGHT"][-1] == "+120s"
    assert rows["UNKNOWN"][-1] == "+30s"


def test_trip_updates_without_static() -> None:
    code, text = run("trip-updates", TRIP_UPDATES)
    assert code == 0
    rows = {line.split()[0]: line.split() for line in text.splitlines()[1:-1]}
    assert rows["T15-1"][-1] == "+120s"
    assert rows["T15-NIGHT"][-1] == "-"
    assert text.endswith("4 trip update(s), feed time 2026-10-12T06:06:00Z\n")


def test_trip_updates_json(static_zip: Path) -> None:
    payload = run_json("trip-updates", TRIP_UPDATES, "--static", str(static_zip), "--route", "15")
    assert [item["entity_id"] for item in payload] == ["tu1", "tu3"]
    delays = payload[0]["stop_delays"]
    assert [d["delay"] for d in delays] == [60, 150, 120]
    assert delays[0]["scheduled"] == "2026-10-12T08:00:00+02:00"
    assert run_json("trip-updates", TRIP_UPDATES, "--route", "175")[0]["delay"] == 300


def test_alerts_text() -> None:
    code, text = run("alerts", ALERTS, "--lang", "en")
    assert code == 0
    assert "[DETOUR] Line 15 detour" in text
    assert "  routes: 15" in text
    assert "[STOP_MOVED] (no header)" in text
    assert "  stops: S4" in text
    assert text.endswith("2 alert(s), feed time 2026-10-12T06:06:00Z\n")


def test_alerts_json_filters() -> None:
    payload = run_json("alerts", ALERTS, "--route", "15")
    assert [a["entity_id"] for a in payload] == ["a1"]
    assert payload[0]["header_text"]["translations"][0] == {
        "text": "Objazd linii 15",
        "language": "pl",
    }
    morning = run_json("alerts", ALERTS, "--at", "2026-10-12T08:00:00+02:00")
    assert [a["entity_id"] for a in morning] == ["a1"]
    night = run_json("alerts", ALERTS, "--at", "2026-10-12T23:00:00")
    assert [a["entity_id"] for a in night] == ["a2"]
    everything_now = run_json("alerts", ALERTS, "--active")
    assert len(everything_now) <= 2


def test_alerts_invalid_time() -> None:
    with pytest.raises(SystemExit) as info:
        run("alerts", ALERTS, "--at", "tomorrow")
    assert info.value.code == 2


def test_stdin(monkeypatch: pytest.MonkeyPatch, vehicles_bytes: bytes) -> None:
    class FakeStdin:
        buffer = io.BytesIO(vehicles_bytes)

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    assert len(run_json("vehicles", "-")) == 4


def test_url_source(monkeypatch: pytest.MonkeyPatch, vehicles_bytes: bytes) -> None:
    from gtfs_rt_kit import client

    seen: dict[str, object] = {}

    def fake_fetch(self: client.GtfsRtClient, url: str) -> bytes:
        seen["url"] = url
        seen["attempts"] = self.retry.attempts
        return vehicles_bytes

    monkeypatch.setattr(client.GtfsRtClient, "fetch_bytes", fake_fetch)
    payload = run_json("vehicles", "https://example.org/v.pb", "--retries", "0")
    assert len(payload) == 4
    assert seen == {"url": "https://example.org/v.pb", "attempts": 1}


def test_fetch_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from gtfs_rt_kit import client

    def failing(self: client.GtfsRtClient, url: str) -> bytes:
        raise FeedFetchError("GET x returned HTTP 503", url=url, status_code=503)

    monkeypatch.setattr(client.GtfsRtClient, "fetch_bytes", failing)
    code, _ = run("alerts", "https://example.org/a.pb")
    assert code == 1
    assert "gtfs-rt-kit: error: GET x returned HTTP 503" in capsys.readouterr().err


def test_missing_httpx(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setitem(sys.modules, "gtfs_rt_kit.client", None)
    code, _ = run("vehicles", "https://example.org/v.pb")
    assert code == 1
    assert "gtfs_rt_kit.client" in capsys.readouterr().err


def test_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = run("vehicles", str(tmp_path / "missing.pb"))
    assert code == 1
    assert "cannot read" in capsys.readouterr().err


def test_decode_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.pb"
    bad.write_bytes(b"\xff\xff")
    assert run("vehicles", str(bad))[0] == 1
    assert "invalid GTFS-Realtime payload" in capsys.readouterr().err


def test_negative_retries() -> None:
    with pytest.raises(SystemExit) as info:
        run("vehicles", VEHICLES, "--retries", "-1")
    assert info.value.code == 2


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    from gtfs_rt_kit import __version__

    with pytest.raises(SystemExit):
        run("--version")
    assert capsys.readouterr().out.strip() == f"gtfs-rt-kit {__version__}"


def test_python_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gtfs_rt_kit", "alerts", ALERTS],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "2 alert(s)" in result.stdout
