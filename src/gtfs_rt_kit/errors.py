"""Exception hierarchy of gtfs-rt-kit."""

from __future__ import annotations

__all__ = ["FeedDecodeError", "FeedFetchError", "GtfsRtKitError", "StaticGtfsError"]


class GtfsRtKitError(Exception):
    """Base class for all errors raised by this library."""


class FeedDecodeError(GtfsRtKitError):
    """The payload is not a valid GTFS-Realtime ``FeedMessage``."""


class FeedFetchError(GtfsRtKitError):
    """A feed could not be downloaded (network error, timeout or HTTP error status)."""

    def __init__(self, message: str, *, url: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class StaticGtfsError(GtfsRtKitError):
    """A static GTFS archive is missing, malformed or lacks a required file."""
