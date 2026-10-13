# gtfs-rt-kit

[![CI](https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/ci.yml)
[![Docs](https://github.com/MaciejZiel/gtfs-rt-kit/actions/workflows/docs.yml/badge.svg)](https://maciejziel.github.io/gtfs-rt-kit/)
[![PyPI](https://img.shields.io/pypi/v/gtfs-rt-kit.svg)](https://pypi.org/project/gtfs-rt-kit/)
[![Python versions](https://img.shields.io/pypi/pyversions/gtfs-rt-kit.svg)](https://pypi.org/project/gtfs-rt-kit/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/LICENSE)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-2a6db2.svg)](https://mypy-lang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Typed Python client and toolkit for public-transport realtime data:
[GTFS-Realtime](https://gtfs.org/realtime/) feeds (vehicle positions, trip updates,
service alerts) plus helpers for [static GTFS](https://gtfs.org/schedule/) archives.

- **Typed models**: frozen dataclasses, timezone-aware datetimes, enum names; `mypy --strict` clean.
- **Sync and async clients** on [httpx](https://www.python-httpx.org/) with timeouts, exponential backoff and `Retry-After`.
- **Lazy static GTFS loader**: only the files you touch are parsed.
- **Matching and delays**: vehicles to trips and routes, predictions vs. the timetable (overnight trips and DST handled).
- **CLI**: `gtfs-rt-kit vehicles <url> --route 15 --json`.

Documentation: <https://maciejziel.github.io/gtfs-rt-kit/>

## Installation

```bash
pip install "gtfs-rt-kit[http]"   # with the HTTP clients (httpx)
pip install gtfs-rt-kit           # decoding and static GTFS only
```

Python 3.10-3.13.

## Usage

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

## Examples

- [`examples/warsaw_live.py`](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/examples/warsaw_live.py): live Warsaw (ZTM) vehicles of a line,
  matched to the timetable, with alerts.
- [`examples/generic_feed.py`](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/examples/generic_feed.py): summary and most delayed trips of
  any GTFS-Realtime feed, using the async client.

## API overview

| Area | API |
| --- | --- |
| Decoding | `parse_feed`, `load_feed`, `Feed`, `FeedHeader` |
| Models | `VehiclePosition`, `TripUpdate`, `StopTimeUpdate`, `StopTimeEvent`, `Alert`, `TripDescriptor`, `VehicleDescriptor`, `Position`, `TranslatedString`, `TimeRange`, `EntitySelector` |
| HTTP (`http` extra) | `GtfsRtClient`, `AsyncGtfsRtClient`, `RetryPolicy` |
| Static GTFS | `StaticGtfs`, `Agency`, `Stop`, `Route`, `Trip`, `StopTime`, `parse_gtfs_time` |
| Matching | `match_vehicles`, `match_vehicle`, `filter_by_route`, `MatchedVehicle`, `gtfs_rt_kit.warsaw` |
| Delays | `trip_delays`, `StopDelay`, `estimate_vehicle_delay`, `scheduled_datetime` |
| Errors | `GtfsRtKitError`, `FeedDecodeError`, `FeedFetchError`, `StaticGtfsError` |

See the [API reference](https://maciejziel.github.io/gtfs-rt-kit/api/) for details.

## Development

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

## License

[MIT](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/LICENSE) © 2026 Maciej Zieliński. Third-party components are listed in
[3rdparty_licenses.md](https://github.com/MaciejZiel/gtfs-rt-kit/blob/main/3rdparty_licenses.md).
