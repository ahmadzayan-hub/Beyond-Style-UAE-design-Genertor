"""Secure customer approval link E2E (real stack): studio mints a single-use
link → customer opens it WITHOUT a session (fresh browser context) → sees
exact text + dimensioned proof → retype-to-confirm → approve → version
locked with SECURE_LINK; the link is dead afterwards.
Usage: python3 e2e/approval_link_e2e.py (uvicorn :8000 + next start :3000)."""
from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE", "http://localhost:3000")
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
TEXT = "ميثه"
MOBILE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}


def main():
    exe = None
    for cand in ("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
                 "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "/opt/pw-browsers/chromium"):
        if pathlib.Path(cand).is_file():
            exe = cand
            break
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe)
        studio = browser.new_context(**MOBILE).new_page()
        studio.goto(BASE)
        studio.get_by_test_id("text-input").fill(TEXT)
        studio.get_by_test_id("start-continue").click()
        expect(studio.get_by_test_id("confirm-text-display")).to_have_text(TEXT, timeout=20000)
        studio.get_by_test_id("confirm-checkbox").check()
        studio.get_by_test_id("confirm-continue").click()
        expect(studio.get_by_test_id("proof-card")).to_have_count(10, timeout=180000)
        studio.get_by_test_id("choose-1").click()
        expect(studio.get_by_test_id("current-version")).to_have_text("1", timeout=60000)
        studio.get_by_test_id("to-approve").click()
        expect(studio.get_by_test_id("approve-text-display")).to_have_text(TEXT)
        studio.get_by_test_id("create-approval-link").click()
        expect(studio.get_by_test_id("approval-link-url")).to_be_visible(timeout=15000)
        url = studio.get_by_test_id("approval-link-url").input_value()
        assert url.startswith(BASE + "/approve/"), url
        studio.screenshot(path=str(EVIDENCE / "approval-link-1-studio.png"), full_page=True)

        # Customer: fresh context, no session storage.
        customer = browser.new_context(**MOBILE).new_page()
        customer.goto(url)
        expect(customer.get_by_test_id("link-text-display")).to_have_text(TEXT, timeout=20000)
        expect(customer.get_by_test_id("link-proof")).to_be_visible()
        assert customer.evaluate("sessionStorage.getItem('bs_session_token')") is None
        customer.get_by_test_id("link-retype").fill("ميثة")            # wrong taa marbuta → cannot approve
        expect(customer.get_by_test_id("link-mismatch")).to_be_visible()
        assert customer.get_by_test_id("link-approve").is_disabled()
        customer.get_by_test_id("link-retype").fill(TEXT)
        customer.get_by_test_id("link-name").fill("Maitha")
        customer.screenshot(path=str(EVIDENCE / "approval-link-2-customer.png"), full_page=True)
        customer.get_by_test_id("link-approve").click()
        expect(customer.get_by_test_id("link-approved")).to_be_visible(timeout=30000)
        approval_hash = customer.get_by_test_id("link-approval-hash").inner_text()
        customer.screenshot(path=str(EVIDENCE / "approval-link-3-approved.png"), full_page=True)

        # Single use: reopening the link is refused.
        again = browser.new_context(**MOBILE).new_page()
        again.goto(url)
        expect(again.get_by_test_id("link-invalid")).to_be_visible(timeout=20000)

        # Studio sees the lock through the API (readiness ladder → SECURE_LINK).
        facts = studio.evaluate(
            """async () => {
              const token = sessionStorage.getItem('bs_session_token');
              const designId = sessionStorage.getItem('bs_design_id');
              const ev = await (await fetch(`/api/designs/${designId}/events`, {headers: {'X-Session-Token': token}})).json();
              const approved = ev.find(e => e.event_type === 'CUSTOMER_APPROVED');
              const vid = approved.version_id;
              const ladder = await (await fetch(`/api/versions/${vid}/readiness`, {headers: {'X-Session-Token': token}})).json();
              const rung = ladder.rungs.find(r => r.state === 'CUSTOMER_APPROVED');
              return {method: approved.metadata.method, channel: rung.approval_channel, hash: approved.metadata.approval_hash};
            }"""
        )
        assert facts["method"] == "SECURE_LINK" and facts["channel"] == "SECURE_LINK", facts
        assert facts["hash"] == approval_hash, (facts, approval_hash)
        browser.close()
    print("APPROVAL LINK E2E PASSED — SECURE_LINK approval", approval_hash[:12], "…")


if __name__ == "__main__":
    sys.exit(main())
