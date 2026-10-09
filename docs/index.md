# gtfs-rt-kit

Typed Python client and toolkit for public-transport realtime data:
[GTFS-Realtime](https://gtfs.org/realtime/) feeds (vehicle positions, trip updates,
service alerts) and helpers for [static GTFS](https://gtfs.org/schedule/) archives.

- **Typed models**: frozen dataclasses with timezone-aware datetimes and enum names,
  checked with `mypy --strict`.
- **Sync and async clients** built on [httpx](https://www.python-httpx.org/), with
  timeouts, exponential backoff and `Retry-After` support.
- **Static GTFS** archives loaded lazily: only the files you touch are parsed.
- **Matching and delays**: link vehicles to trips and routes, compare predictions
  with the timetable (overnight trips and daylight-saving days included).
- **CLI**: `gtfs-rt-kit vehicles <url> --route 15 --json`.

## Installation

```bash
pip install "gtfs-rt-kit[http]"
```

The `http` extra installs httpx for the HTTP clients and for reading URLs in the CLI.
Without it you can still decode feeds from bytes or files and work with static GTFS:

```bash
pip install gtfs-rt-kit
```

Python 3.10 to 3.13 is supported.

## Quick start

```python
from gtfs_rt_kit import GtfsRtClient

with GtfsRtClient() as client:
    feed = client.fetch("https://mkuran.pl/gtfs/warsaw/vehicles.pb")

print(feed.timestamp, len(feed.vehicles))
for vehicle in feed.vehicles[:5]:
    print(vehicle.vehicle_id, vehicle.trip_id, vehicle.position)
```

From the command line:

```bash
gtfs-rt-kit vehicles https://mkuran.pl/gtfs/warsaw/vehicles.pb --warsaw --route 15
```

Continue with the [realtime feeds guide](realtime.md) or jump to the
[Warsaw example](examples/warsaw.md).
