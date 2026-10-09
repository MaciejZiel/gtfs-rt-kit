from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Iterator

import httpx
import pytest

from gtfs_rt_kit import AsyncGtfsRtClient, FeedFetchError, GtfsRtClient, RetryPolicy
from gtfs_rt_kit.errors import FeedDecodeError

URL = "https://feeds.example.org/vehicles.pb"
Handler = Callable[[httpx.Request], httpx.Response]


def sequence(*responses: httpx.Response | Exception) -> tuple[Handler, list[httpx.Request]]:
    """A transport handler returning (or raising) ``responses`` in order."""
    calls: list[httpx.Request] = []
    pending: Iterator[httpx.Response | Exception] = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = next(pending)
        if isinstance(item, Exception):
            raise item
        return item

    return handler, calls


def sync_client(handler: Handler, sleeps: list[float], **kwargs: object) -> GtfsRtClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GtfsRtClient(http_client=http, sleep=sleeps.append, **kwargs)  # type: ignore[arg-type]


def test_fetch_decodes_feed(vehicles_bytes: bytes) -> None:
    handler, calls = sequence(httpx.Response(200, content=vehicles_bytes))
    with sync_client(handler, []) as client:
        feed = client.fetch(URL)
    assert len(feed.vehicles) == 4
    assert str(calls[0].url) == URL


def test_shortcuts(vehicles_bytes: bytes, trip_updates_bytes: bytes, alerts_bytes: bytes) -> None:
    handler, _ = sequence(
        httpx.Response(200, content=vehicles_bytes),
        httpx.Response(200, content=trip_updates_bytes),
        httpx.Response(200, content=alerts_bytes),
    )
    client = sync_client(handler, [])
    assert len(client.vehicles(URL)) == 4
    assert len(client.trip_updates(URL)) == 4
    assert len(client.alerts(URL)) == 2


def test_retries_transient_failures(vehicles_bytes: bytes) -> None:
    handler, calls = sequence(
        httpx.ConnectError("refused"),
        httpx.Response(503, headers={"Retry-After": "2"}),
        httpx.Response(200, content=vehicles_bytes),
    )
    sleeps: list[float] = []
    client = sync_client(handler, sleeps, retry=RetryPolicy(attempts=3, backoff=0.25))
    assert client.fetch_bytes(URL) == vehicles_bytes
    assert len(calls) == 3
    assert sleeps == [0.25, 2.0]


def test_gives_up_after_last_attempt() -> None:
    handler, calls = sequence(*(httpx.Response(502) for _ in range(3)))
    sleeps: list[float] = []
    client = sync_client(handler, sleeps)
    with pytest.raises(FeedFetchError, match="HTTP 502") as info:
        client.fetch(URL)
    assert info.value.status_code == 502
    assert info.value.url == URL
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_does_not_retry_client_errors() -> None:
    handler, calls = sequence(httpx.Response(404))
    with pytest.raises(FeedFetchError, match="HTTP 404"):
        sync_client(handler, []).fetch(URL)
    assert len(calls) == 1


def test_timeout_is_reported() -> None:
    handler, _ = sequence(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"))
    client = sync_client(handler, [], retry=RetryPolicy(attempts=2))
    with pytest.raises(FeedFetchError, match="timed out") as info:
        client.fetch(URL)
    assert info.value.status_code is None


def test_invalid_payload_is_not_retried() -> None:
    handler, calls = sequence(httpx.Response(200, content=b"\xff\xff"))
    with pytest.raises(FeedDecodeError):
        sync_client(handler, []).fetch(URL)
    assert len(calls) == 1


def test_default_client_headers_and_close() -> None:
    client = GtfsRtClient(headers={"Authorization": "token"}, timeout=3.0)
    http = client._http
    assert http.headers["User-Agent"].startswith("gtfs-rt-kit/")
    assert http.headers["Authorization"] == "token"
    assert http.timeout.read == 3.0
    client.close()
    assert http.is_closed


def test_borrowed_client_is_not_closed() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    GtfsRtClient(http_client=http).close()
    assert not http.is_closed
    http.close()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def async_client(handler: Handler, sleeps: list[float], **kwargs: object) -> AsyncGtfsRtClient:
    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncGtfsRtClient(http_client=http, sleep=sleep, **kwargs)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_async_fetch_with_retries(
    vehicles_bytes: bytes, trip_updates_bytes: bytes, alerts_bytes: bytes
) -> None:
    handler, calls = sequence(
        httpx.ReadTimeout("slow"),
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(200, content=vehicles_bytes),
        httpx.Response(200, content=trip_updates_bytes),
        httpx.Response(200, content=alerts_bytes),
    )
    sleeps: list[float] = []
    async with async_client(handler, sleeps) as client:
        assert len(await client.vehicles(URL)) == 4
        assert len(await client.trip_updates(URL)) == 4
        assert len(await client.alerts(URL)) == 2
    assert sleeps == [0.5, 1.0]
    assert len(calls) == 5


@pytest.mark.anyio
async def test_async_failures() -> None:
    handler, _ = sequence(
        httpx.ConnectError("down"), httpx.ConnectError("down"), httpx.Response(410)
    )
    client = async_client(handler, [], retry=RetryPolicy(attempts=2))
    with pytest.raises(FeedFetchError, match="failed"):
        await client.fetch(URL)
    with pytest.raises(FeedFetchError, match="HTTP 410"):
        await client.fetch(URL)


@pytest.mark.anyio
async def test_async_default_client_closes() -> None:
    client = AsyncGtfsRtClient()
    http = client._http
    await client.aclose()
    assert http.is_closed


def test_unknown_attribute() -> None:
    import gtfs_rt_kit

    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        _ = gtfs_rt_kit.nope


def test_helpful_error_without_httpx() -> None:
    code = (
        "import sys; sys.modules['httpx'] = None\n"
        "import gtfs_rt_kit\n"
        "gtfs_rt_kit.parse_feed\n"
        "try:\n"
        "    gtfs_rt_kit.GtfsRtClient\n"
        "except ImportError as error:\n"
        "    print(error)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert 'pip install "gtfs-rt-kit[http]"' in result.stdout
