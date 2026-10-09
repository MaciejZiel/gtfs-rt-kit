# Command line

Installing the package provides the `gtfs-rt-kit` command (also available as
`python -m gtfs_rt_kit`). Reading URLs needs the `http` extra.

```text
gtfs-rt-kit vehicles     SOURCE [--route R] [--static GTFS_ZIP] [--warsaw] [--json]
gtfs-rt-kit trip-updates SOURCE [--route R] [--static GTFS_ZIP] [--json]
gtfs-rt-kit alerts       SOURCE [--route R] [--lang pl] [--active | --at ISO_TIME] [--json]
```

`SOURCE` is an `http(s)://` URL, a path to a `.pb` file, or `-` for standard input.
Every command also accepts `--timeout SECONDS` (default 10) and `--retries N`
(default 2).

## Examples

```console
$ gtfs-rt-kit vehicles https://mkuran.pl/gtfs/warsaw/vehicles.pb --warsaw --route N91
VEHICLE    LINE  TRIP                         LAT       LON       TIMESTAMP
V/N91/187  N91   2026-10-09:N91:PtS:187:2453  52.28374  20.90525  2026-10-09T23:13:02Z
V/N91/188  N91   2026-10-09:N91:PtS:188:2515  52.22932  21.00283  2026-10-09T23:13:04Z
2 vehicle(s), feed time 2026-10-09T23:13:14Z
```

```bash
# JSON for scripts (jq, pandas, ...)
gtfs-rt-kit vehicles https://example.org/vehicle_positions.pb --route 15 --json

# Delays against the timetable
gtfs-rt-kit trip-updates https://example.org/trip_updates.pb --static gtfs.zip

# Alerts in Polish that are active right now
gtfs-rt-kit alerts https://mkuran.pl/gtfs/warsaw/alerts.pb --lang pl --active

# Saved snapshots work too
curl -s https://example.org/alerts.pb | gtfs-rt-kit alerts -
```

With `--static`, vehicles are matched to routes (so `--route` also accepts short names
and the output includes the transport mode and headsign) and trip updates gain
per-stop delays. The exit code is `1` when a feed cannot be fetched or decoded and `2`
for invalid arguments.
