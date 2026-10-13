<p align="center">
  <img src="https://raw.githubusercontent.com/MaciejZiel/gtfs-rt-kit/main/docs/logo.svg" width="72" height="72" alt="gtfs-rt-kit logo">
</p>

<h1 align="center">gtfs-rt-kit</h1>

<p align="center">
  <b>Typed Python client and toolkit for public-transport realtime data.</b>
</p>

<p align="center">
  <a href="https://maciejziel.github.io/gtfs-rt-kit/">Documentation</a> · <a href="https://pypi.org/project/gtfs-rt-kit/">PyPI</a> · <a href="https://github.com/MaciejZiel/gtfs-rt-kit">Source</a>
</p>

<p align="center">
  <a href="https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://maciejziel.github.io/gtfs-rt-kit/"><img alt="Docs" src="https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/gtfs-rt-kit/"><img alt="PyPI" src="https://img.shields.io/pypi/v/gtfs-rt-kit.svg"></a>
  <a href="https://pypi.org/project/gtfs-rt-kit/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/gtfs-rt-kit.svg"></a>
  <a href="https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/LICENSE"><img alt="Licence: MIT" src="https://img.shields.io/badge/licence-MIT-blue.svg"></a>
  <a href="https://mypy-lang.org/"><img alt="mypy strict" src="https://img.shields.io/badge/mypy-strict-2a6db2.svg"></a>
</p>

<p align="center">Covers <a href="https://gtfs.org/realtime/">GTFS-Realtime</a> feeds (vehicle positions, trip updates, service alerts) plus helpers for <a href="https://gtfs.org/schedule/">static GTFS</a> archives.</p>

## ✨ Features

- **Typed models**: frozen dataclasses, timezone-aware datetimes, enum names; `mypy --strict` clean.
- **Sync and async clients** on [httpx](https://www.python-httpx.org/) with timeouts, exponential backoff and `Retry-After`.
- **Lazy static GTFS loader**: only the files you touch are parsed.
- **Matching and delays**: vehicles to trips and routes, predictions vs. the timetable (overnight trips and DST handled).
- **CLI**: `gtfs-rt-kit vehicles <url> --route 15 --json`.

## 📦 Installation

```bash
pip install "gtfs-rt-kit[http]"   # with the HTTP clients (httpx)
pip install gtfs-rt-kit           # decoding and static GTFS only
```

Python 3.10-3.13.

## 🚀 Usage

### Fetch and decode a feed

```python
from gtfs_rt_kit import GtfsRtClient, RetryPolicy

with GtfsRtClient(timeout=5.0, retry=RetryPolicy(attempts=4)) as client:
    feed = client.fetch("https://mkuran.pl/gtfs/warsaw/vehicles.pb")

print(feed.timestamp, len(feed.vehicles))
vehicle = feed.vehicles[0]
print(vehicle.vehicle_id, vehicle.trip_id, vehicle.position, vehicle.timestamp)
```

Already have the bytes or a file? Use `parse_feed(data)` or `load_feed("vehicles.pb")`.

### Async

```python
import asyncio
from gtfs_rt_kit import AsyncGtfsRtClient


async def main() -> None:
    async with AsyncGtfsRtClient() as client:
        vehicles, alerts = await asyncio.gather(
            client.vehicles("https://mkuran.pl/gtfs/warsaw/vehicles.pb"),
            client.alerts("https://mkuran.pl/gtfs/warsaw/alerts.pb"),
        )
    print(len(vehicles), "vehicles,", len(alerts), "alerts")


asyncio.run(main())
```

### Static GTFS, matching and delays

```python
from gtfs_rt_kit import StaticGtfs, filter_by_route, load_feed, match_vehicles, trip_delays

gtfs = StaticGtfs("gtfs.zip")  # lazy: nothing is parsed yet
matched = match_vehicles(feed, gtfs)  # `feed` from the first example
for item in filter_by_route(matched, "15"):  # route id or short name
    print(item.vehicle.vehicle_id, item.line, item.mode, item.trip and item.trip.headsign)

updates_feed = load_feed("trip_updates.pb")  # or client.fetch(...)
update = updates_feed.trip_update_for("T15-1")  # a trip id from your feed
for stop in trip_delays(update, gtfs):
    print(stop.stop_id, stop.scheduled, stop.predicted, stop.delay)
```

### Command line

Example output (live data, so yours will differ):

```console
$ gtfs-rt-kit vehicles https://mkuran.pl/gtfs/warsaw/vehicles.pb --warsaw --route N91
VEHICLE    LINE  TRIP                         LAT       LON       TIMESTAMP
V/N91/187  N91   2026-10-09:N91:PtS:187:2453  52.28374  20.90525  2026-10-09T23:13:02Z
V/N91/188  N91   2026-10-09:N91:PtS:188:2515  52.22932  21.00283  2026-10-09T23:13:04Z
2 vehicle(s), feed time 2026-10-09T23:13:14Z

$ gtfs-rt-kit vehicles https://example.org/vehicle_positions.pb --route 15 --json
$ gtfs-rt-kit trip-updates https://example.org/trip_updates.pb --static gtfs.zip
$ gtfs-rt-kit alerts https://mkuran.pl/gtfs/warsaw/alerts.pb --lang pl --active
```

The source can be a URL, a `.pb` file or `-` for stdin. Other options: `--static` (match against a
static GTFS zip), `--at ISO_TIME` (alerts active at a given time), `--timeout` and `--retries`.

## 🧩 Examples

- [`examples/warsaw_live.py`](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/examples/warsaw_live.py): live Warsaw (ZTM) vehicles of a line,
  matched to the timetable, with alerts.
- [`examples/generic_feed.py`](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/examples/generic_feed.py): summary and most delayed trips of
  any GTFS-Realtime feed, using the async client.

## 🔌 API overview

| Area | API |
| --- | --- |
| Decoding | `parse_feed`, `load_feed`, `Feed`, `FeedHeader` |
| Models | `VehiclePosition`, `TripUpdate`, `StopTimeUpdate`, `StopTimeEvent`, `Alert`, `TripDescriptor`, `VehicleDescriptor`, `Position`, `TranslatedString`, `Translation`, `TimeRange`, `EntitySelector` |
| HTTP (`http` extra) | `GtfsRtClient`, `AsyncGtfsRtClient`, `RetryPolicy` |
| Static GTFS | `StaticGtfs`, `Agency`, `Stop`, `Route`, `Trip`, `StopTime`, `parse_gtfs_time` |
| Matching | `match_vehicles`, `match_vehicle`, `filter_by_route`, `MatchedVehicle`, `gtfs_rt_kit.warsaw` |
| Delays | `trip_delays`, `StopDelay`, `estimate_vehicle_delay`, `scheduled_datetime` |
| Serialization | `gtfs_rt_kit.serialize.to_jsonable` |
| Errors | `GtfsRtKitError`, `FeedDecodeError`, `FeedFetchError`, `StaticGtfsError` |

See the [API reference](https://maciejziel.github.io/gtfs-rt-kit/api/) for details.

## 🛠 Tech stack

| Layer | Used |
|---|---|
| Decoding | `gtfs-realtime-bindings`, `protobuf` |
| HTTP clients (`http` extra) | `httpx` |
| Docs | MkDocs, Material for MkDocs, mkdocstrings |
| Quality | pytest, ruff, mypy (strict) |

## 🧪 Development

```bash
uv sync --all-extras          # runtime, http extra and dev tools
uv run pytest --cov           # tests (no network access needed)
uv run ruff check && uv run ruff format --check
uv run mypy                   # strict mode
uv sync --all-extras --group docs && uv run mkdocs serve
```

Test fixtures live in `tests/fixtures`; regenerate the realtime feeds with
`uv run python tests/fixtures/make_fixtures.py`.

Releases are published to PyPI from version tags via Trusted Publishing; see
[RELEASING.md](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/RELEASING.md).

## 📄 Licence

[MIT](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/LICENSE) © 2026 Maciej Zieliński. Third-party components are listed in
[3rdparty_licenses.md](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/3rdparty_licenses.md).
