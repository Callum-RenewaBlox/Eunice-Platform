#!/usr/bin/env python3
"""Keep the hosted Streamlit apps awake.

Streamlit Community Cloud puts an app to sleep after ~12 hours without a
viewer. A plain HTTP GET returns 200 (and /_stcore/health returns "ok") even
while the app is asleep, because the Python app only really wakes when a
browser opens its WebSocket session. So we load each app in a real headless
browser: that opens the WebSocket (which resets the inactivity timer) and, if
an app had already nodded off, clicks the "get this app back up" button to
reboot it.

Two things about streamlit.app worth knowing: the sleep screen is rendered by
the host page a moment after load (so we poll for its button rather than look
once), and a running app renders inside an iframe at ``/~/+/`` (so the "is it
up" check looks through every frame for Streamlit's app marker).

Exit code is non-zero if any app could not be confirmed running, so the
workflow's failure step opens a GitHub issue.
"""

import re
import sys
import time

from playwright.sync_api import sync_playwright

APPS = [
    "https://eunice.streamlit.app/",
    "https://renewablox-savings.streamlit.app/",
    "https://renewablox-client-atlas-v2.streamlit.app/",
]

WAKE_BUTTON = re.compile("get this app back up", re.IGNORECASE)
SETTLE_S = 120      # a cold app renders within this
WAKE_EXTRA_S = 120  # and a woken one gets this much longer to boot


def app_rendered(page):
    """True once any frame carries Streamlit's app marker."""
    for frame in page.frames:
        try:
            if frame.locator("[data-testid='stApp']").count() > 0:
                return True
        except Exception:  # a frame mid-navigation
            pass
    return False


def visit(browser, url):
    """Load one app, wake it if it was asleep, and confirm it is running."""
    print(f"::group::{url}")
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        deadline = time.time() + SETTLE_S
        clicked = False
        up = False
        while time.time() < deadline:
            if not clicked:
                button = page.get_by_role("button", name=WAKE_BUTTON)
                if button.count() == 0:
                    button = page.get_by_text(WAKE_BUTTON)
                if button.count() > 0 and button.first.is_visible():
                    print("App was asleep — clicking the wake button.")
                    button.first.click()
                    clicked = True
                    deadline = time.time() + WAKE_EXTRA_S
            if app_rendered(page):
                up = True
                break
            page.wait_for_timeout(2_000)
        print("App is up (stApp rendered)." if up else "Could not see the app render.")
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
