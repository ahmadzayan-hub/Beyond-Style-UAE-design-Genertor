"""Acceptance E2E (real stack, no mocks) for the spec's mandatory case:

    حامد محمد سلطان ميثه حمد خالد مهرة   — Thuluth-inspired pendant

Verify text (ميثه must stay ميثه, never ميثة) → Thuluth (honestly labelled
"inspired") → 10 compositions → select → Pro-mode vector edit (new version)
→ JEWELRY QA + weight → approve → export SVG / DXF / PDF → export fidelity
PASS → WORKSHOP READY. Then layout checks at 360 / 390 / 768 / 1280 px
(no horizontal overflow) with screenshots.

Usage: python3 e2e/acceptance_seven_names_e2e.py   (servers running:
  uvicorn app.main:app --port 8000  |  cd frontend && npm start)
Evidence: docs/evidence/acceptance-seven-*.png + acceptance-seven-results.json
"""
from __future__ import annotations

import json
import os
import re
import pathlib
import sys
import unicodedata

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE", "http://localhost:3000")
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
NAMES = ("حامد", "محمد", "سلطان", "ميثه", "حمد", "خالد", "مهرة")
TEXT = " ".join(NAMES)
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
GEN_TIMEOUT = int(os.environ.get("GEN_TIMEOUT_MS", "300000"))


def _browser(p):
    exe = None
    for cand in (
        "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        "/opt/pw-browsers/chromium",
    ):
        if pathlib.Path(cand).is_file():
            exe = cand
            break
    return p.chromium.launch(executable_path=exe)


def _no_overflow(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def _api(page, path: str):
    return page.evaluate(
        """async (path) => {
          const token = sessionStorage.getItem('bs_session_token');
          const r = await fetch(path, {headers: {'X-Session-Token': token}});
          return {status: r.status, body: await r.json()};
        }""",
        path,
    )


def run(page) -> dict:
    out: dict = {"text": TEXT}
    page.goto(BASE)
    assert page.evaluate("document.documentElement.dir") == "rtl"
    page.get_by_test_id("text-input").fill(TEXT)
    # Thuluth is offered honestly as an INFLUENCED_ONLY style (no locked fake).
    chip = page.get_by_test_id("script-thuluth")
    expect(chip).to_be_visible(timeout=15000)
    assert chip.is_enabled(), "Thuluth chip must be selectable (influenced), not locked"
    chip.click()
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-1-start.png"), full_page=True)
    page.get_by_test_id("start-continue").click()

    # ---- exact text + integrity
    expect(page.get_by_test_id("confirm-text-display")).to_have_text(TEXT, timeout=20000)
    shown = page.get_by_test_id("confirm-text-display").inner_text()
    assert "ميثه" in shown and "ميثة" not in shown, shown
    assert unicodedata.normalize("NFC", shown) == TEXT
    expect(page.get_by_test_id("integrity-label")).to_contain_text("ناجحة", timeout=15000)
    out["integrity_label"] = page.get_by_test_id("integrity-label").inner_text()
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-2-confirm.png"), full_page=True)
    page.get_by_test_id("confirm-checkbox").check()
    page.get_by_test_id("confirm-continue").click()

    # ---- 10 compositions
    expect(page.get_by_test_id("proof-card")).to_have_count(10, timeout=GEN_TIMEOUT)
    page.wait_for_selector('[data-testid="proof-card"] svg', timeout=60000)
    cards = page.get_by_test_id("proof-card").all_inner_texts()
    out["proof_cards"] = cards
    assert len(set(cards)) >= 8, "top-10 cards should read as different compositions"
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-3-proofs.png"), full_page=True)

    # ---- select → JEWELRY QA + weight
    page.get_by_test_id("choose-1").click()
    expect(page.get_by_test_id("selected-preview")).to_be_visible(timeout=60000)
    expect(page.get_by_test_id("selected-text")).to_have_text(TEXT)
    expect(page.get_by_test_id("current-version")).to_have_text("1", timeout=30000)
    expect(page.get_by_test_id("jewelry-check")).to_be_visible(timeout=60000)
    out["jewelry_qa_label"] = page.get_by_test_id("jewelry-qa-label").inner_text()
    out["weight"] = page.get_by_test_id("weight-value").inner_text()
    assert out["weight"].endswith("g")
    # actual-size preview mode is a real toggle
    page.get_by_test_id("preview-mode-actual").click()
    expect(page.get_by_test_id("selected-preview")).to_have_class(re.compile("proof-actual"))
    page.get_by_test_id("preview-mode-fit").click()
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-4-selected.png"), full_page=True)

    # ---- Pro mode: a real vector edit becomes version 2; refused tools listed
    page.get_by_test_id("pro-toggle").click()
    expect(page.get_by_test_id("pro-panel")).to_be_visible(timeout=15000)
    expect(page.get_by_test_id("pro-refused")).to_be_visible()
    page.get_by_test_id("pro-move-1-0").click()
    expect(page.get_by_test_id("pro-pending")).to_be_visible()
    page.get_by_test_id("pro-preview").click()
    expect(page.get_by_test_id("pro-preview-result")).to_be_visible(timeout=60000)
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-5-pro-preview.png"), full_page=True)
    page.get_by_test_id("pro-apply").click()
    expect(page.get_by_test_id("current-version")).to_have_text("2", timeout=60000)
    out["vector_edit_version"] = 2

    # ---- approve
    page.get_by_test_id("to-approve").click()
    expect(page.get_by_test_id("approve-text-display")).to_have_text(TEXT)
    page.get_by_test_id("approve-checkbox").check()
    page.get_by_test_id("approve-button").click()
    expect(page.get_by_test_id("approved")).to_be_visible(timeout=60000)
    out["locked_version"] = page.get_by_test_id("locked-version").inner_text()
    out["approval_hash"] = page.get_by_test_id("approval-hash").inner_text()
    assert out["locked_version"] == "2"

    # ---- exports + fidelity gate + readiness
    for fmt in ("svg", "dxf", "pdf"):
        page.get_by_test_id(f"download-{fmt}").click()
        expect(page.get_by_test_id(f"fidelity-{fmt}")).to_contain_text("ناجحة", timeout=60000)
    expect(page.get_by_test_id("workshop-ready")).to_have_text("جاهز للورشة", timeout=30000)
    out["readiness_state"] = page.get_by_test_id("readiness-state").inner_text()
    page.screenshot(path=str(EVIDENCE / "acceptance-seven-6-approved.png"), full_page=True)

    # ---- server-side facts behind the UI claims
    design_id = page.evaluate("sessionStorage.getItem('bs_design_id')")
    events = _api(page, f"/api/designs/{design_id}/events")["body"]
    out["events"] = [e["event_type"] for e in events]
    for needed in ("TEXT_CONFIRMED", "DESIGN_SELECTED", "DESIGN_EDITED", "CUSTOMER_APPROVED", "VERSION_LOCKED", "PRODUCTION_EXPORT_CREATED"):
        assert needed in out["events"], (needed, out["events"])
    return out


def main():
    results: dict = {}
    with sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_context(**MOBILE).new_page()
        results["flow"] = run(page)

        # Layout checks: no horizontal overflow at the spec viewports.
        results["viewports"] = {}
        for w, h in ((360, 740), (390, 844), (768, 1024), (1280, 800)):
            ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=w < 700, has_touch=w < 700)
            pg = ctx.new_page()
            pg.goto(BASE)
            pg.get_by_test_id("text-input").fill(TEXT)
            ok_start = _no_overflow(pg)
            pg.screenshot(path=str(EVIDENCE / f"acceptance-seven-vp{w}-start.png"), full_page=True)
            pg.goto(f"{BASE}/styles")
            pg.wait_for_selector('[data-testid^="style-card-"]', timeout=30000)
            ok_styles = _no_overflow(pg)
            pg.screenshot(path=str(EVIDENCE / f"acceptance-seven-vp{w}-styles.png"), full_page=True)
            results["viewports"][str(w)] = {"start_no_overflow": ok_start, "styles_no_overflow": ok_styles}
            assert ok_start and ok_styles, (w, ok_start, ok_styles)
            ctx.close()
        browser.close()
    (EVIDENCE / "acceptance-seven-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("ACCEPTANCE E2E PASSED —", TEXT)
    print(json.dumps({k: v for k, v in results["flow"].items() if k != "proof_cards"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
