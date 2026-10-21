"""Fetch Scholar HTML with a selected browser on GitHub-hosted runners."""

import os
import time
from urllib.parse import urlencode, urlparse

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import TimeoutError as BrowserTimeout
from playwright.sync_api import sync_playwright

from scholar_cookies import validate_cookie_header


PROFILE_ORIGIN = "https://scholar.google.com"
MAX_ATTEMPTS = 2
NAVIGATION_TIMEOUT_MS = 45000
CONTENT_TIMEOUT_MS = 15000
BROWSER_LABELS = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}


def selected_browser() -> str:
    name = os.environ.get("SCHOLAR_BROWSER", "chromium").strip().lower()
    if name not in BROWSER_LABELS:
        raise ValueError("SCHOLAR_BROWSER must be chromium, firefox, or webkit.")
    return name


def browser_cookies(header: str) -> list:
    """Scope imported cookies to Scholar rather than all Google services."""
    header = validate_cookie_header(header)
    cookies = {}
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        cookies[name] = {"name": name, "value": value, "url": PROFILE_ORIGIN + "/"}
    return list(cookies.values())


def check_page(page, response, browser_label="Chromium") -> None:
    """Reject explicit blocks without repeatedly hitting the same challenge."""
    if response is None:
        raise RuntimeError("Scholar navigation returned no HTTP response.")
    print(f"Scholar document HTTP {response.status}", flush=True)
    if response.status in (401, 403, 429):
        raise RuntimeError(
            f"Google Scholar returned HTTP {response.status} in {browser_label}. "
            "Scholar rejected this browser request; the HTTP status alone does not identify the cause."
        )
    location = urlparse(page.url)
    if location.hostname != "scholar.google.com" or location.path.startswith("/sorry"):
        raise RuntimeError("Google Scholar redirected to a verification or login page.")
    if page.locator("#gs_captcha_f, #gs_captcha_ccl, iframe[src*='recaptcha']").count():
        raise RuntimeError(f"Google Scholar requires interactive verification in {browser_label}.")


def fetch_profile_html(scholar_id: str, cookie: str = "") -> str:
    """Use a browser context with its native user agent and cookie store."""
    browser_name = selected_browser()
    browser_label = BROWSER_LABELS[browser_name]
    cookies = browser_cookies(cookie) if cookie else []
    session_mode = "imported-cookie" if cookies else "anonymous"
    url = PROFILE_ORIGIN + "/citations?" + urlencode(
        {"hl": "en", "user": scholar_id, "pagesize": 100}
    )
    try:
        with sync_playwright() as playwright:
            browser_type = getattr(playwright, browser_name)
            launch_options = {"headless": True, "timeout": 30000}
            if browser_name == "chromium":
                # Use full Chromium's modern headless mode.
                launch_options["channel"] = "chromium"
            browser = browser_type.launch(**launch_options)
            try:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    print(
                        f"Fetching Scholar with {browser_label} [{session_mode}] "
                        f"(attempt {attempt}/{MAX_ATTEMPTS})...",
                        flush=True,
                    )
                    context = browser.new_context(locale="en-US")
                    try:
                        if cookies:
                            context.add_cookies(cookies)
                        page = context.new_page()
                        response = page.goto(
                            url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS
                        )
                        check_page(page, response, browser_label)
                        if response.status >= 500:
                            if attempt == MAX_ATTEMPTS:
                                raise RuntimeError(f"Google Scholar returned HTTP {response.status} twice.")
                        elif response.status >= 400:
                            raise RuntimeError(f"Google Scholar returned HTTP {response.status}.")
                        else:
                            page.locator("#gsc_prf_in").wait_for(timeout=CONTENT_TIMEOUT_MS)
                            # Avoid publishing a silently truncated list of papers.
                            more = page.locator("#gsc_bpf_more")
                            if more.count() and more.is_enabled():
                                raise RuntimeError(
                                    "Scholar reports more than 100 publications; pagination is required. "
                                    "No partial citation data will be published."
                                )
                            return page.content()
                    except BrowserTimeout:
                        if attempt == MAX_ATTEMPTS:
                            raise RuntimeError(f"{browser_label} timed out loading the Scholar profile twice.") from None
                        print("Scholar page timed out; retrying once.", flush=True)
                    finally:
                        context.close()
                    time.sleep(5)
            finally:
                browser.close()
    except BrowserError:
        # Playwright errors can contain URLs; never dump imported session data.
        raise RuntimeError(
            f"{browser_label} failed to start or navigate. Ensure its Playwright browser and system dependencies are installed."
        ) from None
    raise RuntimeError(f"{browser_label} could not fetch the Scholar profile.")
