"""Live trams and buses in Warsaw, matched against the ZTM timetable.

Uses the public feeds published by Mikołaj Kuranowski at https://mkuran.pl/gtfs/
(CC0). Run with::

    pip install "gtfs-rt-kit[http]"
    python examples/warsaw_live.py 15

The static archive is cached in the working directory as ``warsaw.zip``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gtfs_rt_kit import GtfsRtClient, StaticGtfs, filter_by_route, match_vehicles, warsaw

CACHE = Path("warsaw.zip")


def main(line: str) -> None:
    with GtfsRtClient(timeout=30.0) as client:
        if not CACHE.exists():
            print("Downloading the Warsaw timetable (about 100 MB)...")
            CACHE.write_bytes(client.fetch_bytes(warsaw.GTFS_URL))
        feed = client.fetch(warsaw.VEHICLES_URL)
        alerts = client.alerts(warsaw.ALERTS_URL)

    gtfs = StaticGtfs(CACHE)
    matched = match_vehicles(feed, gtfs, route_hint=warsaw.route_from_vehicle_id)
    vehicles = filter_by_route(matched, line)

    stamp = f"{feed.timestamp:%H:%M:%S} UTC" if feed.timestamp else "unknown time"
    print(f"Line {line}: {len(vehicles)} vehicle(s) at {stamp}")
    for item in vehicles:
        position = item.vehicle.position
        headsign = item.trip.headsign if item.trip else "?"
        where = f"{position.latitude:.5f}, {position.longitude:.5f}" if position else "unknown"
        print(f"  {item.vehicle.vehicle_id:<12} {item.mode or '':<6} -> {headsign:<28} {where}")

    route = gtfs.find_route(line)
    if route is not None:
        for alert in alerts:
            if alert.affects_route(route.route_id) and alert.header_text:
                print(f"  ! {alert.header_text.text('pl')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "15")
