#!/usr/bin/env python3
"""Publish the OpenAPI document of the backend as a versioned artefact.

    python3 scripts/export_openapi.py            → writes docs/api/openapi.json
    python3 scripts/export_openapi.py --check    → exit 1 if docs/api/openapi.json is stale

The live document is always served by the running backend at /openapi.json
(and /docs); this file is the reviewable, diff-able copy committed with the
code so API changes are visible in pull requests and CI fails when it is
not regenerated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "api" / "openapi.json"


def build() -> str:
    from app.main import app

    spec = app.openapi()
    return json.dumps(spec, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    doc = build()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != doc:
            print(f"STALE: {OUT} does not match the running code — run scripts/export_openapi.py", file=sys.stderr)
            return 1
        print(f"OK: {OUT} is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    n = len(json.loads(doc).get("paths", {}))
    print(f"wrote {OUT} ({n} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
