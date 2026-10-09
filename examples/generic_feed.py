"""Inspect any GTFS-Realtime feed: vehicles, delays and alerts.

Usage::

    pip install "gtfs-rt-kit[http]"
    python examples/generic_feed.py FEED_URL [GTFS_ZIP]

``FEED_URL`` may serve vehicle positions, trip updates, alerts or a mix of them.
With an optional static GTFS zip, trip updates are compared with the timetable.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from gtfs_rt_kit import AsyncGtfsRtClient, RetryPolicy, StaticGtfs, trip_delays


async def main(url: str, gtfs_path: str | None) -> None:
    async with AsyncGtfsRtClient(retry=RetryPolicy(attempts=5)) as client:
        feed = await client.fetch(url)

    print(f"Feed time: {feed.timestamp}  entities: {len(feed)}")
    print(f"  vehicles: {len(feed.vehicles)}")
    print(f"  trip updates: {len(feed.trip_updates)}")
    now = datetime.now(timezone.utc)
    print(f"  alerts: {len(feed.alerts)} ({sum(a.is_active(now) for a in feed.alerts)} active)")

    if gtfs_path and feed.trip_updates:
        gtfs = StaticGtfs(gtfs_path)
        print("\nMost delayed trips:")
        worst: list[tuple[int, str]] = []
        for update in feed.trip_updates:
            delays = [stop.delay for stop in trip_delays(update, gtfs) if stop.delay is not None]
            if delays and update.trip_id:
                worst.append((delays[-1], update.trip_id))
        for delay, trip_id in sorted(worst, reverse=True)[:10]:
            trip = gtfs.trip(trip_id)
            route = gtfs.route(trip.route_id) if trip else None
            print(f"  {route.name if route else '?':>6}  {trip_id:<30} {delay / 60:+.1f} min")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
