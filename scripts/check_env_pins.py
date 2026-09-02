#!/usr/bin/env python3
"""Fail if the running Python environment drifts from backend/requirements.txt.

Local environments drifted once (fontTools 4.53 installed while 4.60.2 was
pinned) and CI was red for eight commits while every local run looked
green. Run before committing (`make check-pins`), and CI runs it after
install so a pin the resolver silently overrides is caught there too.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

REQ = Path(__file__).resolve().parents[1] / "backend" / "requirements.txt"


def main() -> int:
    drift = []
    for line in REQ.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line)
        if not m:
            continue
        name, pinned = m.group(1), m.group(2)
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            drift.append(f"{name}: pinned {pinned}, NOT INSTALLED")
            continue
        if installed != pinned:
            drift.append(f"{name}: pinned {pinned}, installed {installed}")
    if drift:
        print("ENVIRONMENT DRIFT vs backend/requirements.txt:")
        for d in drift:
            print("  -", d)
        print("Fix: pip install -r backend/requirements.txt")
        return 1
    print("environment matches backend/requirements.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
