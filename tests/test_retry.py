from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from gtfs_rt_kit import RetryPolicy


def test_exponential_backoff_is_capped() -> None:
    policy = RetryPolicy(backoff=0.5, max_backoff=3.0)
    assert [policy.delay(n) for n in (1, 2, 3, 4)] == [0.5, 1.0, 2.0, 3.0]


def test_retry_after_seconds() -> None:
    policy = RetryPolicy(max_backoff=5.0)
    assert policy.delay(1, "2") == 2.0
    assert policy.delay(1, "120") == 5.0
    assert policy.delay(1, "-3") == 0.0
    assert policy.delay(2, "soon") == 1.0


def test_retry_after_http_date() -> None:
    policy = RetryPolicy(max_backoff=100.0)
    later = datetime.now(timezone.utc) + timedelta(seconds=30)
    assert 25.0 <= policy.delay(1, format_datetime(later, usegmt=True)) <= 30.0
    assert policy.delay(1, "Wed, 21 Oct 2015 07:28:00") == 0.0


def test_retry_statuses() -> None:
    policy = RetryPolicy()
    assert policy.should_retry_status(503)
    assert not policy.should_retry_status(404)


@pytest.mark.parametrize("kwargs", [{"attempts": 0}, {"backoff": -1.0}, {"max_backoff": -1.0}])
def test_invalid_policy(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must"):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]
