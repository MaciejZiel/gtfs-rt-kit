"""Typed client and toolkit for GTFS-Realtime feeds and static GTFS schedules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .decode import load_feed, parse_feed
from .delay import StopDelay, estimate_vehicle_delay, scheduled_datetime, trip_delays
from .errors import FeedDecodeError, FeedFetchError, GtfsRtKitError, StaticGtfsError
from .matching import MatchedVehicle, filter_by_route, match_vehicle, match_vehicles
from .models import (
    Alert,
    EntitySelector,
    Feed,
    FeedHeader,
    Position,
    StopTimeEvent,
    StopTimeUpdate,
    TimeRange,
    TranslatedString,
    Translation,
    TripDescriptor,
    TripUpdate,
    VehicleDescriptor,
    VehiclePosition,
)
from .retry import RetryPolicy
from .static import Agency, Route, StaticGtfs, Stop, StopTime, Trip

if TYPE_CHECKING:
    from .client import AsyncGtfsRtClient, GtfsRtClient

__version__ = "0.1.0"

__all__ = [
    "Agency",
    "Alert",
    "AsyncGtfsRtClient",
    "EntitySelector",
    "Feed",
    "FeedDecodeError",
    "FeedFetchError",
    "FeedHeader",
    "GtfsRtClient",
    "GtfsRtKitError",
    "MatchedVehicle",
    "Position",
    "RetryPolicy",
    "Route",
    "StaticGtfs",
    "StaticGtfsError",
    "Stop",
    "StopDelay",
    "StopTime",
    "StopTimeEvent",
    "StopTimeUpdate",
    "TimeRange",
    "TranslatedString",
    "Translation",
    "Trip",
    "TripDescriptor",
    "TripUpdate",
    "VehicleDescriptor",
    "VehiclePosition",
    "__version__",
    "estimate_vehicle_delay",
    "filter_by_route",
    "load_feed",
    "match_vehicle",
    "match_vehicles",
    "parse_feed",
    "scheduled_datetime",
    "trip_delays",
]


def __getattr__(name: str) -> Any:
    # The HTTP clients depend on the optional ``http`` extra (httpx), so they are
    # imported lazily: decoding and static GTFS helpers work without it.
    if name in {"GtfsRtClient", "AsyncGtfsRtClient"}:
        from . import client

        return getattr(client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
