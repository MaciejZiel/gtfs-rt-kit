"""Retry policy shared by the synchronous and asynchronous clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

__all__ = ["RetryPolicy"]

_DEFAULT_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How failed requests are retried.

    Attributes:
        attempts: Total number of attempts, including the first one (``1`` disables retries).
        backoff: Base delay in seconds; attempt ``n`` waits ``backoff * 2 ** (n - 1)``.
        max_backoff: Upper bound for a single delay, also applied to ``Retry-After``.
        retry_statuses: HTTP status codes that are worth retrying.
    """

    attempts: int = 3
    backoff: float = 0.5
    max_backoff: float = 8.0
    retry_statuses: frozenset[int] = field(default=_DEFAULT_RETRY_STATUSES)

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1")
        if self.backoff < 0 or self.max_backoff < 0:
            raise ValueError("backoff values must not be negative")

    def delay(self, attempt: int, retry_after: str | None = None) -> float:
        """Seconds to wait after failed attempt number ``attempt`` (1-based)."""
        if retry_after is not None:
            parsed = _parse_retry_after(retry_after)
            if parsed is not None:
                return min(parsed, self.max_backoff)
        return min(self.backoff * 2.0 ** (attempt - 1), self.max_backoff)

    def should_retry_status(self, status_code: int) -> bool:
        """Whether a response with ``status_code`` should be retried."""
        return status_code in self.retry_statuses


def _parse_retry_after(value: str) -> float | None:
    value = value.strip()
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max((moment - datetime.now(timezone.utc)).total_seconds(), 0.0)
