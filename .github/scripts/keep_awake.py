#!/usr/bin/env python3
"""Keep the hosted Streamlit apps awake.

Streamlit Community Cloud puts free-tier apps to sleep after a few hours idle.
A plain HTTP GET returns 200 (and /_stcore/health returns "ok") even while the
app is asleep, because the Python app only really wakes when a browser opens its
WebSocket session. So we load each app in a real headless browser: that opens
the WebSocket (which resets the inactivity timer) and, if an app had already
nodded off, clicks the "get this app back up" button to reboot it.

Exit code is non-zero if any app could not be confirmed running, so the
workflow's failure step opens a GitHub issue.
"""

import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

APPS = [
    "https://eunice.streamlit.app/",
    "https://renewablox-savings.streamlit.app/",
]

WAKE_BUTTON = re.compile("get this app back up", re.IGNORECASE)


def visit(browser, url):
    """Load one app, wake it if it was asleep, and confirm it is running."""
    print(f"::group::{url}")
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        # If the sleep screen is showing, click the wake button to reboot.
        button = page.get_by_role("button", name=WAKE_BUTTON)
        if button.count() == 0:
            button = page.get_by_text(WAKE_BUTTON)
        if button.count() > 0 and button.first.is_visible():
            print("App was asleep — clicking the wake button.")
            button.first.click()
            page.wait_for_timeout(3_000)

        # Best signal that the app actually rendered (covers a cold reboot too).
        try:
            page.wait_for_selector("[data-testid='stApp']", timeout=120_000)
            print("App is up (stApp rendered).")
            up = True
        except PlaywrightTimeoutError:
            # Fallback: the sleep screen is gone and the page has real content.
            still_asleep = page.get_by_text(WAKE_BUTTON).count() > 0
            has_content = page.locator("#root *").count() > 0
            up = (not still_asleep) and has_content
            print(f"stApp not found; fallback judged up={up}.")

        # Let the WebSocket session run briefly so it counts as real activity.
        page.wait_for_timeout(8_000)
        return up
    except Exception as exc:  # report and keep going to the next app
        print(f"FAILED to confirm app is up: {exc}")
        return False
    finally:
        page.close()
        print("::endgroup::")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            results = [visit(browser, url) for url in APPS]
        finally:
            browser.close()

    failed = [url for url, ok in zip(APPS, results) if not ok]
    if failed:
        print(f"::error::Could not confirm: {', '.join(failed)}")
        sys.exit(1)
    print("All apps awake.")


if __name__ == "__main__":
    main()
