# Static GTFS

[`StaticGtfs`][gtfs_rt_kit.static.StaticGtfs] reads a GTFS zip archive from a path, from bytes
or from a binary file object. Files are parsed lazily and cached on first access, so
opening a large feed is instant and `stop_times.txt` is only read when you need
schedule data.

```python
from gtfs_rt_kit import StaticGtfs

gtfs = StaticGtfs("warsaw.zip")

gtfs.timezone  # ZoneInfo of the first agency
gtfs.stop("7013")  # Stop | None
gtfs.route("15").mode  # "tram"
gtfs.routes_by_short_name("N91")  # routes are also searchable by short name
gtfs.find_route("n91")  # id first, then short name (case-insensitive)
gtfs.trip(trip_id).headsign
gtfs.stop_times(trip_id)  # ordered by stop_sequence; times in seconds
```

Any other file can be streamed row by row:

```python
if gtfs.has_file("calendar_dates.txt"):
    for row in gtfs.rows("calendar_dates.txt"):
        ...
```

GTFS times may exceed `24:00:00`; `parse_gtfs_time()` and `format_gtfs_time()` convert
between `"25:10:00"` and seconds after the start of the service day.

Malformed archives or missing required columns raise
[`StaticGtfsError`][gtfs_rt_kit.errors.StaticGtfsError].

!!! tip "Downloading the archive"
    With the `http` extra installed, `GtfsRtClient().fetch_bytes(url)` downloads any URL
    with retries, so `StaticGtfs(client.fetch_bytes(GTFS_URL))` works for archives too.
    For large feeds, cache the archive on disk and pass its path instead.
