"""Which commit is actually running — so "Replit in sync with GitHub" is
a measured fact, not an assumption.

`.replit`'s deployment build step writes the checked-out commit to
`backend/app/BUILD_SHA`; a `BUILD_SHA` environment variable overrides it;
otherwise `/health` reports "unknown". The Production Monitor compares
the value with the pushed commit and reports IN_SYNC / BEHIND.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BUILD_SHA_FILE = Path(__file__).resolve().parent / "BUILD_SHA"
_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def build_sha() -> str:
    env = os.environ.get("BUILD_SHA", "").strip()
    if _SHA.match(env):
        return env
    try:
        value = BUILD_SHA_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return value if _SHA.match(value) else "unknown"
