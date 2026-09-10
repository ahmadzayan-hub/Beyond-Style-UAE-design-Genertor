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


from .ratelimit import RateLimiter, get_limiter  # noqa: E402 — shared registry (memory | redis)


UPLOAD_LIMITER = get_limiter(
    "upload",
    max_calls=int(os.environ.get("UPLOAD_RATE_MAX", 10)),
    window_seconds=float(os.environ.get("UPLOAD_RATE_WINDOW_S", 60)),
)
GENERATE_LIMITER = get_limiter(
    "generate",
    max_calls=int(os.environ.get("GENERATE_RATE_MAX", 5)),
    window_seconds=float(os.environ.get("GENERATE_RATE_WINDOW_S", 60)),
)
