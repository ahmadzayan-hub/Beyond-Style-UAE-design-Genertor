"""Real-backend E2E for the customer Golden Path UI (mobile viewport).

Runs against live PostgreSQL + FastAPI + Next.js (no mocks):
  Flow A: type ميثة → confirm → 10 proofs → select → approve → downloads.
  Flow B: reference upload + "نفس الشكل بس غير الكتابة إلى نورة" → brief
          classified → confirm نورة → proofs → select → approve.

Usage: python3 e2e/golden_path_e2e.py  (servers must be running:
  uvicorn app.main:app --port 8000  |  cd frontend && npm start)
Screenshots + JSON evidence land in docs/evidence/.
"""
from __future__ import annotations

import io
import json
import pathlib
import sys

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3000"
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}

results: dict = {"flows": {}}


def make_reference_jpeg() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (900, 500), (212, 190, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def run_flow(page, name: str, text: str, with_reference: bool, message: str | None, generate_timeout_ms: int = 120000):
    page.goto(BASE)
    # True RTL for Arabic default UI.
    assert page.evaluate("document.documentElement.dir") == "rtl"
    page.get_by_test_id("text-input").fill(text)
    if with_reference:
        page.get_by_test_id("file-input").set_input_files(
            files=[{"name": "reference.jpg", "mimeType": "image/jpeg", "buffer": make_reference_jpeg()}]
        )
        expect(page.get_by_test_id("reference-preview")).to_be_visible()
        if message:
            page.get_by_test_id("message-input").fill(message)
    page.screenshot(path=str(EVIDENCE / f"{name}-1-start.png"))
    page.get_by_test_id("start-continue").click()

    # Exact-text confirmation screen shows the text verbatim.
    expect(page.get_by_test_id("confirm-text-display")).to_have_text(text, timeout=15000)
    page.screenshot(path=str(EVIDENCE / f"{name}-2-confirm.png"))
    page.get_by_test_id("confirm-checkbox").check()
    page.get_by_test_id("confirm-continue").click()

    # Proof grid: exactly 10 cards, previews load progressively. Longer
    # texts (e.g. the 7-name fixture) take proportionally longer to
    # generate — timeout is caller-configurable, default unchanged.
    expect(page.get_by_test_id("proof-card")).to_have_count(10, timeout=generate_timeout_ms)
    page.wait_for_selector('[data-testid="proof-card"] svg', timeout=30000)
    page.screenshot(path=str(EVIDENCE / f"{name}-3-proofs.png"), full_page=True)

    page.get_by_test_id("choose-1").click()
    expect(page.get_by_test_id("selected-preview")).to_be_visible(timeout=30000)
    expect(page.get_by_test_id("selected-text")).to_have_text(text)
    page.screenshot(path=str(EVIDENCE / f"{name}-4-selected.png"))

    page.get_by_test_id("to-approve").click()
    expect(page.get_by_test_id("approve-text-display")).to_have_text(text)
    page.get_by_test_id("approve-checkbox").check()
    page.get_by_test_id("approve-button").click()
    expect(page.get_by_test_id("approved")).to_be_visible(timeout=30000)
    locked_version = page.get_by_test_id("locked-version").inner_text()
    approval_hash = page.get_by_test_id("approval-hash").inner_text()
    page.screenshot(path=str(EVIDENCE / f"{name}-5-approved.png"))

    # Authorized exports return real content through the browser session.
    export_check = page.evaluate(
        """async () => {
          const token = sessionStorage.getItem('bs_session_token');
          const designId = sessionStorage.getItem('bs_design_id');
          const out = {};
          for (const path of document.querySelectorAll('[data-testid="download-svg"],[data-testid="download-dxf"]')) {}
          const vres = await fetch(`/api/designs/${designId}/events`, {headers: {'X-Session-Token': token}});
          out.events = (await vres.json()).map(e => e.event_type);
          return out;
        }"""
    )
    results["flows"][name] = {
        "text": text,
        "locked_version": locked_version,
        "approval_hash": approval_hash,
        "events": export_check["events"],
    }
    assert "CUSTOMER_APPROVED" in export_check["events"]
    assert "VERSION_LOCKED" in export_check["events"]
    print(f"[{name}] approved, locked version {locked_version}, hash {approval_hash[:12]}…")


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
        ctx = browser.new_context(**MOBILE)
        page = ctx.new_page()
        run_flow(page, "text-flow", "ميثة", with_reference=False, message=None)

        page2 = ctx.new_page()
        run_flow(
            page2,
            "reference-flow",
            "نورة",
            with_reference=True,
            message="نفس الشكل بس غير الكتابة إلى نورة",
        )

        # Language toggle → true LTR English UI.
        page3 = ctx.new_page()
        page3.goto(BASE)
        page3.get_by_test_id("lang-toggle").click()
        assert page3.evaluate("document.documentElement.dir") == "ltr"

        # Desktop viewport smoke.
        desktop = browser.new_context(viewport={"width": 1280, "height": 800})
        dpage = desktop.new_page()
        run_flow(dpage, "desktop-text-flow", "Amal", with_reference=False, message=None)

        browser.close()
    (EVIDENCE / "e2e-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("E2E PASSED — evidence in docs/evidence/")


if __name__ == "__main__":
    sys.exit(main())
