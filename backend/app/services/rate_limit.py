"""In-memory sliding-window rate limiting for authentication endpoints.

Single-process deployment is assumed (Docker Compose runs one backend
container). Keys are (scope, identifier) pairs; timestamps of failed
attempts are kept per key. `is_limited` only reads the bucket,
`record_failure` appends a timestamp and `record_success` clears it.
"""
import threading
import time
from typing import Iterable

_lock = threading.Lock()
_buckets: dict[tuple[str, str], list[float]] = {}


def _prune(key: tuple[str, str], now: float, window: int) -> list[float]:
    """Keep only timestamps inside the window for a key."""
    entries = _buckets.get(key, [])
    entries = [t for t in entries if now - t <= window]
    _buckets[key] = entries
    return entries


def is_limited(scope: str, key: str, limit: int, window: int) -> tuple[bool, int]:
    """Return (limited, retry_after_seconds). Does not record the attempt."""
    now = time.time()
    with _lock:
        entries = _prune((scope, key), now, window)
        if len(entries) >= limit:
            retry_after = int(window - (now - entries[0])) + 1
            return True, max(retry_after, 1)
        return False, 0


def record_failure(scope: str, key: str) -> None:
    with _lock:
        _buckets.setdefault((scope, key), []).append(time.time())


def record_success(scope: str, key: str) -> None:
    """Clear all recorded failures for a key (e.g. after a successful login)."""
    with _lock:
        _buckets.pop((scope, key), None)


def reset() -> None:
    """Clear all recorded attempts (used by tests)."""
    with _lock:
        _buckets.clear()


def prune_expired(window: int = 3600) -> int:
    """Drop buckets whose newest entry is older than the window."""
    now = time.time()
    with _lock:
        stale = [k for k, v in _buckets.items() if v and now - v[-1] > window]
        for k in stale:
            del _buckets[k]
        return len(stale)
