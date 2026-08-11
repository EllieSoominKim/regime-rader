"""Simple in-memory daily cache shared by both the scheduled/lazy history
endpoints (regime/hrp/backtest) and the live /api/regime/today endpoint.

Same pattern everywhere, just a different trigger:
  - history endpoints: lazily recompute on the first request after the
    cached entry's date has rolled over (no cron needed for this timeline).
  - /api/regime/today: same lazy-on-first-request-of-the-day trigger, but
    keyed separately so a cache miss there never forces the much heavier
    history bundle to recompute, and vice versa.

Deliberately a plain in-memory dict, not Redis/etc: this API is a single
process for the competition timeline, and "recompute once per calendar
day, otherwise serve the cached value" doesn't need anything more durable
than that. A process restart just means the next request pays the
recompute cost once, same as a real first-request-of-the-day would.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, Optional


@dataclass
class CacheResult:
    value: Any
    cache_hit: bool
    computed_on: date
    compute_seconds: float


@dataclass
class _Entry:
    computed_on: date
    value: Any
    compute_seconds: float


class DailyCache:
    """Keyed daily cache: `get_or_compute(key, fn)` calls `fn()` at most
    once per calendar day per key, and serves the stored value on every
    other call that day.

    Thread-safe per key (a lock per key, not a single global lock) so two
    concurrent requests racing on the first hit of the day don't both
    trigger `fn()`, while requests for a DIFFERENT key are never blocked
    waiting on this one's (possibly ~85s) computation.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, _Entry] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._registry_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any]) -> CacheResult:
        today = date.today()

        entry = self._entries.get(key)
        if entry is not None and entry.computed_on == today:
            return CacheResult(entry.value, True, entry.computed_on, entry.compute_seconds)

        with self._lock_for(key):
            # Re-check after acquiring the lock: another thread may have
            # just finished computing this key while we were waiting on it.
            entry = self._entries.get(key)
            if entry is not None and entry.computed_on == today:
                return CacheResult(entry.value, True, entry.computed_on, entry.compute_seconds)

            start = time.perf_counter()
            value = compute_fn()
            elapsed = time.perf_counter() - start
            self._entries[key] = _Entry(today, value, elapsed)
            return CacheResult(value, False, today, elapsed)

    def peek(self, key: str) -> Optional[_Entry]:
        """Inspect a cache entry without triggering a compute. Used by the
        root/health endpoint to report cache state."""
        return self._entries.get(key)

    def clear(self, key: Optional[str] = None) -> None:
        """Drop a cache entry (or all of them) -- for manual testing only,
        not wired to any route."""
        if key is None:
            self._entries.clear()
        else:
            self._entries.pop(key, None)


# One process-wide cache instance, imported by every router.
cache = DailyCache()
