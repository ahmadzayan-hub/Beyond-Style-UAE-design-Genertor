"""Customer identity E2E (real stack, AUTH_DEV_ECHO_CODE=1 on the backend):
log in by phone + code on /me → start a design (auto-claimed) → open /me
in a NEW browser context (another device) → log in again → the design is
listed → Continue → the Golden Path resumes with the same exact text.
"""
from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE", "http://localhost:3000")
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
TEXT = "ميثه"
PHONE = "0501234567"
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}


def _login(page):
    page.goto(BASE + "/me")
    page.get_by_test_id("login-contact").fill(PHONE)
    page.get_by_test_id("login-start").click()
    expect(page.get_by_test_id("login-delivery")).to_be_visible(timeout=15000)
    code = page.get_by_test_id("login-dev-code").inner_text().split(":")[-1].strip()
    page.get_by_test_id("login-code").fill(code)
    page.get_by_test_id("login-name").fill("Maitha")
    page.get_by_test_id("login-verify").click()
    expect(page.get_by_test_id("me-box")).to_be_visible(timeout=15000)


def main():
    exe = None
    for cand in ("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
                 "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium"):
        if pathlib.Path(cand).is_file():
            exe = cand
            break
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe)
        dev1 = browser.new_context(**MOBILE).new_page()
        _login(dev1)
        dev1.screenshot(path=str(EVIDENCE / "identity-1-logged-in.png"), full_page=True)
        # Start a design while logged in → claimed automatically.
        dev1.goto(BASE)
        expect(dev1.get_by_test_id("me-link")).to_be_visible()
        dev1.get_by_test_id("text-input").fill(TEXT)
        dev1.get_by_test_id("start-continue").click()
        expect(dev1.get_by_test_id("confirm-text-display")).to_have_text(TEXT, timeout=20000)
        expect(dev1.get_by_test_id("claimed-note")).to_be_visible(timeout=15000)
        dev1.get_by_test_id("confirm-checkbox").check()
        dev1.get_by_test_id("confirm-continue").click()
        expect(dev1.get_by_test_id("proof-card")).to_have_count(10, timeout=180000)
        design_id = dev1.evaluate("sessionStorage.getItem('bs_design_id')")

        # Another device: fresh context (no storage at all).
        dev2 = browser.new_context(**MOBILE).new_page()
        _login(dev2)
        card = dev2.get_by_test_id(f"my-design-{design_id}")
        expect(card).to_be_visible(timeout=15000)
        assert TEXT in card.inner_text()
        dev2.screenshot(path=str(EVIDENCE / "identity-2-my-designs-other-device.png"), full_page=True)
        dev2.get_by_test_id(f"resume-{design_id}").click()
        expect(dev2.get_by_test_id("proof-card")).to_have_count(10, timeout=60000)
        expect(dev2.get_by_test_id("resumed-note")).to_be_visible()
        dev2.screenshot(path=str(EVIDENCE / "identity-3-resumed.png"), full_page=True)
        # The first device's per-request token was rotated away.
        status = dev1.evaluate(
            """async () => (await fetch(`/api/designs/${sessionStorage.getItem('bs_design_id')}`,
                 {headers: {'X-Session-Token': sessionStorage.getItem('bs_session_token')}})).status"""
        )
        assert status == 404, status
        browser.close()
    print("CUSTOMER IDENTITY E2E PASSED —", design_id)


if __name__ == "__main__":
    sys.exit(main())
