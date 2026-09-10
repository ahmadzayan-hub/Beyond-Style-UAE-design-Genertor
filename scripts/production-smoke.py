#!/usr/bin/env python3
"""Production smoke test — the release gate for a real deployment.

Zero external dependencies (stdlib only) so it can run anywhere without
a pip install step first. Exercises the exact production symptom this
deployment slice fixed: a real Arabic multi-name generation request
through the real frontend/backend origins, not a local mock.

Usage:
  FRONTEND_URL=https://www.beyondstyle.ae BACKEND_URL=https://<replit>.repl.co \
    python3 scripts/production-smoke.py

Checks (exits non-zero on the first real failure):
  A. frontend loads (200)
  B. backend /health
  C. backend /ready (200, status: ready)
  D. CORS preflight from FRONTEND_URL's origin succeeds
  E. Arabic generation request (real multi-name text)
  F. exactly 10 candidate designs returned
  G. reference upload request
  H. candidate select
  I. deterministic manufacturing validation passed
  J. external AI status endpoint reachable + honest
  K. no sensitive data (API keys, DSNs) in any response
"""
from __future__ import annotations

import json
import re
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
# The exact required 7-name Golden Path acceptance scenario, oldest to
# youngest, in this exact order — see
# backend/tests/test_seven_name_golden_fixture.py for the immutable
# regression test that locks these Unicode strings and their order.
GOLDEN_SEVEN_NAMES = ["حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة"]
ARABIC_TEXT = " ".join(GOLDEN_SEVEN_NAMES)

SECRET_PATTERNS = ("sk-ant-", "sk-proj-", "sk-", "postgresql://", "postgresql+psycopg2://", "password=")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def request(method: str, url: str, headers: dict | None = None, body: bytes | None = None, timeout: float = 15.0):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, dict(resp.headers), data
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()
    except Exception as exc:  # noqa: BLE001
        return None, {}, str(exc).encode()


def assert_no_secrets(label: str, raw: bytes) -> None:
    text = raw.decode("utf-8", errors="ignore").lower()
    leaked = [p for p in SECRET_PATTERNS if p in text]
    check(f"K. no sensitive data in {label}", not leaked, f"found: {leaked}" if leaked else "")


def main() -> int:
    if not FRONTEND_URL or not BACKEND_URL:
        print("FRONTEND_URL and BACKEND_URL must both be set — refusing to guess a production URL.")
        return 2

    # A. frontend loads
    status, _, body = request("GET", FRONTEND_URL)
    check("A. frontend loads", status == 200, f"status={status}")

    # B. backend /health — must be OUR backend's JSON, not merely "something
    # answered". A 200 HTML page here means another application occupies
    # the URL (seen in production: an AI-scaffolded SPA on the Replit
    # subdomain), which is the single most misleading failure mode.
    status, _, body = request("GET", f"{BACKEND_URL}/health")
    health_json = None
    try:
        health_json = json.loads(body)
    except Exception:
        health_json = None
    is_ours = isinstance(health_json, dict) and health_json.get("status") == "ok" and "schema_version" in health_json
    if status == 200 and not is_ours:
        # Show what actually answers so the operator can tell "another app
        # occupies the subdomain" from "Replit placeholder / asleep" from
        # "wrong URL" without opening a browser.
        snippet = re.sub(r"\s+", " ", body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body))[:160]
        check("B. backend /health", False,
              "URL answers 200 but is NOT the Beyond Style backend (non-JSON/other app at this address); "
              f"body starts with: {snippet!r}")
        _summarize(); return 1
    check("B. backend /health", status == 200 and is_ours, f"status={status}")

    # B2. GitHub ↔ Replit synchronisation — informational, never fabricated.
    # The deployed backend reports the commit it was built from; GitHub
    # tells us the commit that was just pushed. A mismatch is not a code
    # failure (Replit redeploys are manual) but it is exactly what the owner
    # asked to be able to see.
    deployed_sha = (health_json or {}).get("build_sha", "unknown")
    pushed_sha = os.environ.get("GITHUB_SHA", "")
    if deployed_sha == "unknown":
        print("[INFO] B2. sync — deployed backend does not report build_sha (deployed before the build step recorded it, or built without git)")
    elif pushed_sha and deployed_sha.startswith(pushed_sha[: len(deployed_sha)]) or (pushed_sha and pushed_sha.startswith(deployed_sha)):
        print(f"[INFO] B2. sync — IN_SYNC: deployed {deployed_sha[:7]} == pushed {pushed_sha[:7]}")
    elif pushed_sha:
        print(f"[WARN] B2. sync — BEHIND: deployed {deployed_sha[:7]} != pushed {pushed_sha[:7]} — open Replit → Git → Pull, then Deployments → Redeploy")
    else:
        print(f"[INFO] B2. sync — deployed {deployed_sha[:7]} (no GITHUB_SHA to compare against)")

    # C. backend /ready
    status, _, body = request("GET", f"{BACKEND_URL}/ready")
    ready_ok = status == 200
    try:
        ready_body = json.loads(body)
        ready_ok = ready_ok and ready_body.get("status") == "ready"
    except Exception:
        ready_ok = False
    check("C. backend /ready", ready_ok, f"status={status}")
    assert_no_secrets("/ready", body)

    # D. CORS preflight from the real frontend origin
    origin = f"{urlparse(FRONTEND_URL).scheme}://{urlparse(FRONTEND_URL).netloc}"
    status, headers, _ = request(
        "OPTIONS", f"{BACKEND_URL}/api/designs",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    allow_origin = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
    check("D. CORS allows the frontend origin", allow_origin == origin, f"got={allow_origin!r}")

    # E. Arabic multi-name generation request (the real production case).
    status, _, body = request(
        "POST", f"{BACKEND_URL}/api/designs",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"text": ARABIC_TEXT, "product_type": "pendant"}).encode(),
    )
    try:
        created = json.loads(body)
    except Exception:
        created = {}
    check("E. Arabic generation request creates a design", status in (200, 201) and "design_id" in created,
          f"status={status}")
    if "design_id" not in created:
        _summarize(); return 1
    check(
        "E. exact 7-name text preserved byte-for-byte (no substitution/omission/reorder)",
        created.get("normalized_text") == ARABIC_TEXT,
        f"got={created.get('normalized_text')!r}",
    )
    design_id, token = created["design_id"], created["session_token"]
    auth = {"X-Session-Token": token}

    # G. reference upload request — a real, PIL-encoded synthetic JPEG
    # (no real customer image) so it passes the backend's genuine
    # magic-byte/decode validation, not a hand-rolled byte guess.
    try:
        import io as _io

        from PIL import Image as _Image

        buf = _io.BytesIO()
        _Image.new("RGB", (400, 400), (200, 180, 120)).save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()
        boundary = "smokeboundary"
        body_parts = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"provenance\"\r\n\r\nCUSTOMER_OWNED\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"ref.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + jpeg_bytes + f"\r\n--{boundary}--\r\n".encode()
        status, _, body = request(
            "POST", f"{BACKEND_URL}/api/designs/{design_id}/references",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **auth},
            body=body_parts,
        )
        check("G. reference upload request", status == 201, f"status={status}")
    except ImportError:
        print("[SKIP] G. reference upload request — Pillow not installed in this smoke-test environment")

    # confirm text (required before candidates).
    status, _, body = request(
        "POST", f"{BACKEND_URL}/api/designs/{design_id}/confirm",
        headers={"Content-Type": "application/json", **auth},
        body=json.dumps({"confirmed_text": ARABIC_TEXT}).encode(),
    )
    check("confirm exact text", status == 200, f"status={status}")

    # E/F. generate candidates → exactly 10. Long multi-name Arabic text
    # (the real production case) can take up to ~30s deterministically —
    # a generous timeout here avoids a false FAIL from the smoke test
    # itself; see docs/DEPLOYMENT.md for platform proxy timeout guidance.
    status, _, body = request(
        "POST", f"{BACKEND_URL}/api/designs/{design_id}/candidates", headers=auth, timeout=60.0
    )
    try:
        gen = json.loads(body)
    except Exception:
        gen = {}
    top = gen.get("top", [])
    check("F. exactly 10 candidate designs returned", status == 200 and len(top) == 10,
          f"status={status} count={len(top)}")
    assert_no_secrets("/candidates", body)
    if not top:
        _summarize(); return 1

    # H. candidate select.
    status, _, body = request(
        "POST", f"{BACKEND_URL}/api/designs/{design_id}/select",
        headers={"Content-Type": "application/json", **auth},
        body=json.dumps({"candidate_id": top[0]["candidate_id"]}).encode(),
    )
    try:
        sel = json.loads(body)
    except Exception:
        sel = {}
    check("H. candidate select", status == 201 and "version_id" in sel, f"status={status}")
    if "version_id" not in sel:
        _summarize(); return 1

    # I. deterministic manufacturing validation.
    status, _, body = request("GET", f"{BACKEND_URL}/api/versions/{sel['version_id']}", headers=auth)
    try:
        version = json.loads(body)
    except Exception:
        version = {}
    check("I. manufacturing validation passed", version.get("validation_passed") is True, f"status={status}")

    # J. external AI status endpoint.
    status, _, body = request("GET", f"{BACKEND_URL}/api/ai/status")
    check("J. external AI status endpoint reachable", status == 200, f"status={status}")
    assert_no_secrets("/api/ai/status", body)

    return _summarize()


def _summarize() -> int:
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
