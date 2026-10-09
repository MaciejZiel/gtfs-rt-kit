"""Synchronous and asynchronous HTTP clients for GTFS-Realtime feeds.

Requires the optional ``http`` extra: ``pip install "gtfs-rt-kit[http]"``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType

from .decode import parse_feed
from .errors import FeedFetchError
from .models import Alert, Feed, TripUpdate, VehiclePosition
from .retry import RetryPolicy

try:
    import httpx
except ImportError as error:  # pragma: no cover - exercised in a subprocess test
    raise ImportError(
        'The HTTP clients need httpx. Install it with: pip install "gtfs-rt-kit[http]"'
    ) from error

__all__ = ["DEFAULT_TIMEOUT", "AsyncGtfsRtClient", "GtfsRtClient"]

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_ACCEPT = "application/x-protobuf, application/octet-stream;q=0.9, */*;q=0.1"


def _default_headers(extra: Mapping[str, str] | None) -> dict[str, str]:
    from . import __version__

    headers = {"User-Agent": f"gtfs-rt-kit/{__version__}", "Accept": _ACCEPT}
    if extra:
        headers.update(extra)
    return headers


def _status_error(url: str, response: httpx.Response) -> FeedFetchError:
    return FeedFetchError(
        f"GET {url} returned HTTP {response.status_code}",
        url=url,
        status_code=response.status_code,
    )


def _transport_error(url: str, error: httpx.TransportError) -> FeedFetchError:
    kind = "timed out" if isinstance(error, httpx.TimeoutException) else "failed"
    return FeedFetchError(f"GET {url} {kind}: {error!r}", url=url)


class GtfsRtClient:
    """Blocking client that downloads and decodes GTFS-Realtime feeds.

    Example:
        >>> with GtfsRtClient() as client:  # doctest: +SKIP
        ...     feed = client.fetch("https://example.org/vehicles.pb")
    """

    def __init__(
        self,
        *,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        retry: RetryPolicy | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.retry = retry or RetryPolicy()
        self._sleep = sleep
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=timeout, headers=_default_headers(headers), follow_redirects=True
        )

    def fetch_bytes(self, url: str) -> bytes:
        """Download the raw feed payload, retrying transient failures."""
        policy = self.retry
        for attempt in range(1, policy.attempts + 1):
            last = attempt == policy.attempts
            try:
                response = self._http.get(url)
            except httpx.TransportError as error:
                if last:
                    raise _transport_error(url, error) from error
                self._sleep(policy.delay(attempt))
                continue
            if response.is_success:
                return response.content
            if last or not policy.should_retry_status(response.status_code):
                raise _status_error(url, response)
            self._sleep(policy.delay(attempt, response.headers.get("Retry-After")))
        raise AssertionError("unreachable")  # pragma: no cover

    def fetch(self, url: str) -> Feed:
        """Download and decode a feed."""
        return parse_feed(self.fetch_bytes(url))

    def vehicles(self, url: str) -> tuple[VehiclePosition, ...]:
        """Vehicle positions from the feed at ``url``."""
        return self.fetch(url).vehicles

    def trip_updates(self, url: str) -> tuple[TripUpdate, ...]:
        """Trip updates from the feed at ``url``."""
        return self.fetch(url).trip_updates

    def alerts(self, url: str) -> tuple[Alert, ...]:
        """Service alerts from the feed at ``url``."""
        return self.fetch(url).alerts

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> GtfsRtClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncGtfsRtClient:
    """Asynchronous counterpart of :class:`GtfsRtClient`.

    Example:
        >>> async with AsyncGtfsRtClient() as client:  # doctest: +SKIP
        ...     feed = await client.fetch("https://example.org/vehicles.pb")
    """

    def __init__(
        self,
        *,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        retry: RetryPolicy | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.retry = retry or RetryPolicy()
        self._sleep = sleep
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout, headers=_default_headers(headers), follow_redirects=True
        )

    async def fetch_bytes(self, url: str) -> bytes:
        """Download the raw feed payload, retrying transient failures."""
        policy = self.retry
        for attempt in range(1, policy.attempts + 1):
            last = attempt == policy.attempts
            try:
                response = await self._http.get(url)
            except httpx.TransportError as error:
                if last:
                    raise _transport_error(url, error) from error
                await self._sleep(policy.delay(attempt))
                continue
            if response.is_success:
                return response.content
            if last or not policy.should_retry_status(response.status_code):
                raise _status_error(url, response)
            await self._sleep(policy.delay(attempt, response.headers.get("Retry-After")))
        raise AssertionError("unreachable")  # pragma: no cover

    async def fetch(self, url: str) -> Feed:
        """Download and decode a feed."""
        return parse_feed(await self.fetch_bytes(url))

    async def vehicles(self, url: str) -> tuple[VehiclePosition, ...]:
        """Vehicle positions from the feed at ``url``."""
        return (await self.fetch(url)).vehicles

    async def trip_updates(self, url: str) -> tuple[TripUpdate, ...]:
        """Trip updates from the feed at ``url``."""
        return (await self.fetch(url)).trip_updates

    async def alerts(self, url: str) -> tuple[Alert, ...]:
        """Service alerts from the feed at ``url``."""
        return (await self.fetch(url)).alerts

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncGtfsRtClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
