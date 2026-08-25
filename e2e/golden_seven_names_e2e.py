"""Real-backend browser E2E for the IMMUTABLE 7-name Golden Path
acceptance fixture (see backend/tests/test_seven_name_golden_fixture.py
and scripts/production-smoke.py:GOLDEN_SEVEN_NAMES) — exact text, exact
order, WITH an uploaded reference image, through the real customer UI.

Usage: python3 e2e/golden_seven_names_e2e.py  (servers must be running:
  uvicorn app.main:app --port 8000  |  cd frontend && npm start)
Screenshots + JSON evidence land in docs/evidence/ (seven-names-flow-*).

Set BASE=<frontend origin> to point this at a real deployment instead
of localhost:3000 — this script imports golden_path_e2e's BASE-relative
run_flow(), so BASE must be set BEFORE import if overridden.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright

import golden_path_e2e as gp

GOLDEN_SEVEN_NAMES = ("حامد", "محمد", "سلطان", "ميثة", "حمد", "خالد", "مهرة")
GOLDEN_TEXT = " ".join(GOLDEN_SEVEN_NAMES)


def main():
    with sync_playwright() as p:
        exe = None
        for cand in (
            "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
            "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            "/opt/pw-browsers/chromium",
        ):
            if pathlib.Path(cand).is_file():
                exe = cand
                break
        browser = p.chromium.launch(executable_path=exe)
        ctx = browser.new_context(**gp.MOBILE)
        page = ctx.new_page()
        # 7-name generation is slower than a single-word text (~30-60s+
        # depending on host CPU contention) — generous timeout so a busy
        # shared environment doesn't produce a false failure.
        gp.run_flow(page, "seven-names-flow", GOLDEN_TEXT, with_reference=True, message=None,
                    generate_timeout_ms=240000)
        browser.close()

    flow = gp.results["flows"]["seven-names-flow"]
    assert flow["text"] == GOLDEN_TEXT
    assert flow["text"].split(" ") == list(GOLDEN_SEVEN_NAMES)

    out_path = gp.EVIDENCE / "seven-names-e2e-results.json"
    out_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2))
    print(f"SEVEN-NAME E2E PASSED — text preserved exactly: {flow['text']}")
    print(f"Evidence: {out_path}")


if __name__ == "__main__":
    sys.exit(main())
