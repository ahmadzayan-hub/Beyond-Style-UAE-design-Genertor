"""Shared rate limiter — one registry for every limiter in the app.

Backends
* memory (default): sliding-window deque per key, thread-safe, per process.
* redis: sliding window kept in a Redis sorted set per (limiter, key), so
  the limit is shared across uvicorn workers and instances. Selected with
  RATE_LIMIT_BACKEND=redis and REDIS_URL. Any Redis error falls back to the
  in-process window for that call and is counted — the product never
  stalls on the limiter, and readiness reports the degraded state.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque

log = logging.getLogger("beyondstyle.ratelimit")


class MemoryWindow:
    def __init__(self) -> None:
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, max_calls: int, window: float, now: float) -> bool:
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= max_calls:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class RedisWindow:
    """Sorted-set sliding window: members are event timestamps."""

    def __init__(self, client) -> None:
        self.client = client

    def allow(self, key: str, max_calls: int, window: float, now: float) -> bool:
        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        _, count = pipe.execute()[:2]
        if int(count) >= max_calls:
            return False
        pipe = self.client.pipeline()
        pipe.zadd(key, {f"{now:.6f}": now})
        pipe.expire(key, int(window) + 1)
        pipe.execute()
        return True

    def reset(self) -> None:  # tests only
        for k in self.client.keys("bs:rl:*"):
            self.client.delete(k)


class RateLimiter:
    """Named limiter. `allow(key)` is the only call sites use."""

    def __init__(self, max_calls: int, window_seconds: float, name: str = "default"):
        self.max_calls = int(max_calls)
        self.window = float(window_seconds)
        self.name = name
        self._memory = MemoryWindow()
        self.fallbacks = 0

    def allow(self, key: str, now: float | None = None) -> bool:
        backend = _shared_backend()
        if backend is None:
            return self._memory.allow(key, self.max_calls, self.window, time.monotonic() if now is None else now)
        try:
            return backend.allow(f"bs:rl:{self.name}:{key}", self.max_calls, self.window, time.time() if now is None else now)
        except Exception as exc:  # noqa: BLE001 — degrade, never block the product
            self.fallbacks += 1
            _note_failure(exc)
            return self._memory.allow(key, self.max_calls, self.window, time.monotonic() if now is None else now)

    def reset(self) -> None:
        self._memory.reset()
        backend = _shared_backend()
        if backend is not None:
            try:
                backend.reset()
            except Exception:  # noqa: BLE001
                pass


_REGISTRY: dict[str, RateLimiter] = {}
_backend: RedisWindow | None = None
_backend_checked = False
_last_failure: str | None = None
_lock = threading.Lock()


def get_limiter(name: str, max_calls: int, window_seconds: float) -> RateLimiter:
    """One limiter per name for the whole process (and, with Redis, the fleet)."""
    with _lock:
        lim = _REGISTRY.get(name)
        if lim is None:
            lim = RateLimiter(max_calls, window_seconds, name=name)
            _REGISTRY[name] = lim
        return lim


def _note_failure(exc: Exception) -> None:
    global _last_failure
    _last_failure = f"{type(exc).__name__}: {exc}"[:200]
    log.warning("rate limiter Redis failure, using in-process window: %s", _last_failure)


def _shared_backend() -> RedisWindow | None:
    global _backend, _backend_checked
    if _backend_checked:
        return _backend
    with _lock:
        if _backend_checked:
            return _backend
        _backend_checked = True
        if os.environ.get("RATE_LIMIT_BACKEND", "memory").lower() != "redis":
            return None
        url = os.environ.get("REDIS_URL")
        if not url:
            _note_failure(RuntimeError("RATE_LIMIT_BACKEND=redis but REDIS_URL is unset"))
            return None
        try:
            import redis  # pinned

            client = redis.Redis.from_url(url, socket_connect_timeout=1.0, socket_timeout=1.0)
            client.ping()
            _backend = RedisWindow(client)
        except Exception as exc:  # noqa: BLE001
            _note_failure(exc)
            _backend = None
        return _backend


def use_backend(window: RedisWindow | None) -> None:
    """Tests / explicit wiring: install a backend without env lookups."""
    global _backend, _backend_checked
    with _lock:
        _backend, _backend_checked = window, True


def reset_all() -> None:
    global _backend, _backend_checked, _last_failure
    with _lock:
        for lim in _REGISTRY.values():
            lim._memory.reset()
            lim.fallbacks = 0
        _backend, _backend_checked, _last_failure = None, False, None


def status() -> dict:
    backend = _shared_backend()
    return {
        "backend": "redis" if backend is not None else "memory",
        "configured": os.environ.get("RATE_LIMIT_BACKEND", "memory").lower(),
        "shared_across_instances": backend is not None,
        "last_failure": _last_failure,
        "limiters": {n: {"max_calls": l.max_calls, "window_s": l.window, "fallbacks": l.fallbacks} for n, l in _REGISTRY.items()},
    }
