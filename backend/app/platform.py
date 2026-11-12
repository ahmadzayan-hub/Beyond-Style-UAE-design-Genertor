"""Where the backend is running, and what that host can and cannot do.

The backend runs on two kinds of host:

- a long-lived server (Docker, Replit, a VM): writable disk under backend/var,
  migrations at start-up, large request bodies;
- a Vercel Function (VERCEL=1): read-only code directory, only /tmp is writable
  and it is per-instance and short-lived, request bodies are capped by the
  platform at about 4.5 MB, and there is no release phase for migrations.

Code that writes files or accepts uploads asks this module instead of assuming
a server. Nothing here hides a limitation: features that need durable local
disk refuse clearly on Vercel rather than writing to /tmp and losing data.
"""
from __future__ import annotations

import os
from pathlib import Path

# Vercel rejects request bodies above 4.5 MB before the app sees them. Keep the
# app's own limit below that so the customer gets our clear 413, not a
# platform error page; multipart framing needs some of the headroom.
VERCEL_MAX_BODY_BYTES = 4 * 1024 * 1024

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def on_vercel() -> bool:
    return os.environ.get("VERCEL", "") == "1"


def host_name() -> str:
    return "vercel" if on_vercel() else "server"


def writable_root() -> Path:
    """Default parent for local writable state. On Vercel only /tmp is writable,
    and it does not survive the instance: readiness reports that honestly."""
    return Path("/tmp/beyond-style") if on_vercel() else _BACKEND_DIR / "var"


def cap_body_bytes(limit: int) -> int:
    """The smaller of an app limit and what the host can actually receive."""
    return min(limit, VERCEL_MAX_BODY_BYTES) if on_vercel() else limit


def has_durable_local_disk() -> bool:
    """False on Vercel: files written at run time vanish with the instance and
    are invisible to other instances."""
    return not on_vercel()


def info() -> dict:
    return {
        "host": host_name(),
        "durable_local_disk": has_durable_local_disk(),
        "max_body_bytes": VERCEL_MAX_BODY_BYTES if on_vercel() else None,
    }
