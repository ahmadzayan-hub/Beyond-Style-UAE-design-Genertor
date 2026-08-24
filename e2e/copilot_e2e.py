"""Designer Copilot E2E (real stack): select → manual edit → new version →
undo/redo → approve edited version → export authorized.
"""
import pathlib
import sys

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:3000"
EVIDENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def main():
    exe = None
    for cand in (
        "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    ):
        if pathlib.Path(cand).is_file():
            exe = cand
            break
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe)
        page = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        ).new_page()
        page.goto(BASE)
        page.get_by_test_id("text-input").fill("ميثة")
        page.get_by_test_id("start-continue").click()
        expect(page.get_by_test_id("confirm-text-display")).to_have_text("ميثة", timeout=15000)
        page.get_by_test_id("confirm-checkbox").check()
        page.get_by_test_id("confirm-continue").click()
        expect(page.get_by_test_id("proof-card")).to_have_count(10, timeout=120000)
        page.get_by_test_id("choose-1").click()
        expect(page.get_by_test_id("current-version")).to_have_text("1", timeout=30000)

        # Open copilot, thicken stroke, apply → NEW version 2.
        page.get_by_test_id("edit-toggle").click()
        expect(page.get_by_test_id("copilot-panel")).to_be_visible()
        page.screenshot(path=str(EVIDENCE / "copilot-1-panel.png"))
        page.get_by_test_id("slider-stroke_delta_mm").fill("0.4")
        page.get_by_test_id("slider-y_scale").fill("1.15")
        page.get_by_test_id("apply-edit").click()
        expect(page.get_by_test_id("current-version")).to_have_text("2", timeout=30000)
        page.screenshot(path=str(EVIDENCE / "copilot-2-edited-v2.png"))

        # Undo back to v1, redo to v2 — navigation between immutable versions.
        page.get_by_test_id("undo").click()
        expect(page.get_by_test_id("current-version")).to_have_text("1")
        page.get_by_test_id("redo").click()
        expect(page.get_by_test_id("current-version")).to_have_text("2")

        # Approve the edited version and confirm lock.
        page.get_by_test_id("to-approve").click()
        expect(page.get_by_test_id("approve-text-display")).to_have_text("ميثة")
        page.get_by_test_id("approve-checkbox").check()
        page.get_by_test_id("approve-button").click()
        expect(page.get_by_test_id("approved")).to_be_visible(timeout=30000)
        assert page.get_by_test_id("locked-version").inner_text() == "2"
        page.screenshot(path=str(EVIDENCE / "copilot-3-approved-v2.png"))
        browser.close()
    print("COPILOT E2E PASSED — locked edited version 2")


if __name__ == "__main__":
    sys.exit(main())
