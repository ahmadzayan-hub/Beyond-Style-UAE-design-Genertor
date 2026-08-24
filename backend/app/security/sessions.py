"""Anonymous session ownership + simple rate limiting.

A secret token is issued when a design request is created; only its sha256
is stored. Every request-scoped endpoint must present the token — one
session can never read another session's designs, references or exports.

Rate limiting: deterministic in-process sliding window (per token/IP).
Good enough for a single API instance; Redis-backed limiting is a later
scale slice. Limits are configurable via environment.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from collections import defaultdict, deque


def issue_token() -> tuple[str, str]:
    """Returns (secret_token, sha256_hash)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str | None, stored_hash: str | None) -> bool:
    if not token or not stored_hash:
        return False
    return secrets.compare_digest(hash_token(token), stored_hash)


class RateLimiter:
    """Sliding-window counter per key. Thread-safe, deterministic."""

    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window = window_seconds
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_calls:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


UPLOAD_LIMITER = RateLimiter(
    max_calls=int(os.environ.get("UPLOAD_RATE_MAX", 10)),
    window_seconds=float(os.environ.get("UPLOAD_RATE_WINDOW_S", 60)),
)
GENERATE_LIMITER = RateLimiter(
    max_calls=int(os.environ.get("GENERATE_RATE_MAX", 5)),
    window_seconds=float(os.environ.get("GENERATE_RATE_WINDOW_S", 60)),
)
