"""Typed client and toolkit for GTFS-Realtime feeds and static GTFS schedules."""

from .decode import load_feed, parse_feed
from .errors import FeedDecodeError, FeedFetchError, GtfsRtKitError, StaticGtfsError
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

__version__ = "0.1.0"

__all__ = [
    "Alert",
    "EntitySelector",
    "Feed",
    "FeedDecodeError",
    "FeedFetchError",
    "FeedHeader",
    "GtfsRtKitError",
    "Position",
    "StaticGtfsError",
    "StopTimeEvent",
    "StopTimeUpdate",
    "TimeRange",
    "TranslatedString",
    "Translation",
    "TripDescriptor",
    "TripUpdate",
    "VehicleDescriptor",
    "VehiclePosition",
    "__version__",
    "load_feed",
    "parse_feed",
]
