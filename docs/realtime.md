# Realtime feeds

## Decoding

`parse_feed()` turns a serialized GTFS-Realtime `FeedMessage` into a
[`Feed`][gtfs_rt_kit.models.Feed]; `load_feed()` does the same for a file.

```python
from gtfs_rt_kit import load_feed, parse_feed

feed = load_feed("vehicles.pb")
feed = parse_feed(payload_bytes)

feed.header.timestamp  # datetime in UTC, or None
feed.vehicles  # tuple[VehiclePosition, ...]
feed.trip_updates  # tuple[TripUpdate, ...]
feed.alerts  # tuple[Alert, ...]
feed.deleted_entity_ids  # ids of entities flagged is_deleted
```

Optional protobuf fields that are not set become `None` (an unset `bearing` is `None`,
not `0.0`), timestamps become timezone-aware `datetime` objects in UTC, and enums are
exposed by their specification names, for example `"STOPPED_AT"` or `"DETOUR"`.

An invalid payload raises [`FeedDecodeError`][gtfs_rt_kit.errors.FeedDecodeError].

## Useful shortcuts

```python
vehicle = feed.vehicles[0]
vehicle.vehicle_id  # vehicle id, else label, else entity id
vehicle.route_id  # from the trip descriptor
vehicle.trip_id

feed.vehicles_on_route("15")
feed.trip_update_for("T15-1")
feed.alerts_for_route("15")

alert = feed.alerts[0]
alert.header_text.text("pl")  # preferred language with sensible fallbacks
alert.is_active(datetime.now(timezone.utc))
```

## Downloading

[`GtfsRtClient`][gtfs_rt_kit.client.GtfsRtClient] and
[`AsyncGtfsRtClient`][gtfs_rt_kit.client.AsyncGtfsRtClient] require the `http` extra.

```python
from gtfs_rt_kit import GtfsRtClient, RetryPolicy

client = GtfsRtClient(
    timeout=5.0,
    retry=RetryPolicy(attempts=4, backoff=0.5, max_backoff=10.0),
    headers={"Authorization": "apikey my-secret"},
)
with client:
    vehicles = client.vehicles(URL)
    alerts = client.alerts(ALERTS_URL)
```

Connection errors, timeouts and the status codes in `RetryPolicy.retry_statuses`
(408, 425, 429, 500, 502, 503, 504) are retried with exponential backoff. A numeric or
HTTP-date `Retry-After` header overrides the backoff (capped by `max_backoff`). Other
HTTP errors fail immediately. When all attempts fail a
[`FeedFetchError`][gtfs_rt_kit.errors.FeedFetchError] carries the `url` and `status_code`.

The asynchronous client has the same API:

```python
import asyncio

from gtfs_rt_kit import AsyncGtfsRtClient


async def main() -> None:
    async with AsyncGtfsRtClient() as client:
        vehicles, alerts = await asyncio.gather(
            client.vehicles(VEHICLES_URL), client.alerts(ALERTS_URL)
        )


asyncio.run(main())
```

Pass `http_client=` to reuse your own `httpx.Client` / `httpx.AsyncClient` (proxies,
HTTP/2, custom transports); it is then left open when the GTFS-RT client closes.
