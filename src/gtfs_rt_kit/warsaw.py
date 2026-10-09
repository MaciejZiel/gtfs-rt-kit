"""Helpers for the Warsaw (ZTM) feeds published at https://mkuran.pl/gtfs/.

The Warsaw realtime feed identifies vehicles as ``V/<line>/<brigade>`` and does not
fill ``route_id``; :func:`route_from_vehicle_id` recovers the line from the id.
"""

from __future__ import annotations

from .models import VehiclePosition

__all__ = ["ALERTS_URL", "GTFS_URL", "VEHICLES_URL", "route_from_vehicle_id"]

GTFS_URL = "https://mkuran.pl/gtfs/warsaw.zip"
VEHICLES_URL = "https://mkuran.pl/gtfs/warsaw/vehicles.pb"
ALERTS_URL = "https://mkuran.pl/gtfs/warsaw/alerts.pb"


def route_from_vehicle_id(vehicle: VehiclePosition) -> str | None:
    """Line number encoded in a Warsaw vehicle id (``"V/15/7"`` -> ``"15"``)."""
    parts = vehicle.vehicle_id.split("/")
    if len(parts) == 3 and parts[0] == "V" and parts[1]:
        return parts[1]
    return None
