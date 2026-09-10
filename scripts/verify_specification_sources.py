#!/usr/bin/env python3
"""Try to fetch every external `verify_at` URL in
backend/app/data/jewellery_specifications.json and record what happened.

Honest by construction: a blocked or failed fetch is recorded as such and the
section's evidence level stays TRADE_STANDARD_UNVERIFIED_ONLINE. A reachable
page only proves the URL resolves — a human still has to confirm the values
against it and change the evidence level by hand.

    python3 scripts/verify_specification_sources.py [--timeout 15]

Writes docs/evidence/specification_sources.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "backend" / "app" / "data" / "jewellery_specifications.json"
OUT = ROOT / "docs" / "evidence" / "specification_sources.json"


def probe(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "beyond-style-spec-verifier/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — explicit allowlisted use
            status = resp.status
            body = resp.read(4096)
        return {"url": url, "status": "REACHABLE", "http_status": status, "bytes_sampled": len(body)}
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 407):
            return {"url": url, "status": "EGRESS_BLOCKED", "http_status": exc.code, "detail": str(exc.reason)}
        return {"url": url, "status": "HTTP_ERROR", "http_status": exc.code, "detail": str(exc.reason)}
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
        return {"url": url, "status": "UNREACHABLE", "detail": str(exc)[:200]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    results = []
    for name, section in spec["sections"].items():
        for url in section.get("verify_at", []):
            if not url.startswith("http"):
                results.append({"section": name, "url": url, "status": "IN_REPO", "exists": (ROOT / "backend" / url.split("#")[0]).exists()})
                continue
            r = probe(url, args.timeout)
            r["section"] = name
            results.append(r)
            print(f"{r['status']:15} {name:38} {url}")
    summary = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "specifications_version": spec["specifications_version"],
        "reachable": sum(1 for r in results if r["status"] == "REACHABLE"),
        "blocked_or_unreachable": sum(1 for r in results if r["status"] in ("EGRESS_BLOCKED", "UNREACHABLE", "HTTP_ERROR")),
        "in_repo": sum(1 for r in results if r["status"] == "IN_REPO"),
        "note": "REACHABLE only means the URL resolved; values must still be confirmed by a person before an evidence level is raised.",
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {summary['reachable']} reachable, {summary['blocked_or_unreachable']} blocked/unreachable, {summary['in_repo']} in-repo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
