"""Fetch Scholar HTML with Chromium on GitHub-hosted runners."""

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


def browser_cookies(header: str) -> list:
    """Scope imported cookies to Scholar rather than all Google services."""
    header = validate_cookie_header(header)
    cookies = {}
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        cookies[name] = {"name": name, "value": value, "url": PROFILE_ORIGIN + "/"}
    return list(cookies.values())


def check_page(page, response) -> None:
    """Reject explicit blocks without repeatedly hitting the same challenge."""
    if response is None:
        raise RuntimeError("Scholar navigation returned no HTTP response.")
    print(f"Scholar document HTTP {response.status}", flush=True)
    if response.status in (401, 403, 429):
        raise RuntimeError(
            f"Google Scholar returned HTTP {response.status} in Chromium. "
            "The hosted runner request is blocked; copying Cookie alone did not resolve it."
        )
    location = urlparse(page.url)
    if location.hostname != "scholar.google.com" or location.path.startswith("/sorry"):
        raise RuntimeError("Google Scholar redirected to a verification or login page.")
    if page.locator("#gs_captcha_f, #gs_captcha_ccl, iframe[src*='recaptcha']").count():
        raise RuntimeError("Google Scholar requires interactive verification in Chromium.")


def fetch_profile_html(scholar_id: str, cookie: str) -> str:
    """Use an actual Chromium context with its native user agent and cookie store."""
    cookies = browser_cookies(cookie)
    url = PROFILE_ORIGIN + "/citations?" + urlencode(
        {"hl": "en", "user": scholar_id, "pagesize": 100}
    )
    try:
        with sync_playwright() as playwright:
            # Use full Chromium's modern headless mode, not an HTTP UA override.
            browser = playwright.chromium.launch(channel="chromium", headless=True)
            try:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    print(f"Fetching Scholar with Chromium (attempt {attempt}/{MAX_ATTEMPTS})...", flush=True)
                    context = browser.new_context(locale="en-US")
                    try:
                        context.add_cookies(cookies)
                        page = context.new_page()
                        response = page.goto(
                            url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS
                        )
                        check_page(page, response)
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
                            raise RuntimeError("Chromium timed out loading the Scholar profile twice.") from None
                        print("Scholar page timed out; retrying once.", flush=True)
                    finally:
                        context.close()
                    time.sleep(5)
            finally:
                browser.close()
    except BrowserError:
        # Playwright errors can contain URLs; never dump imported session data.
        raise RuntimeError(
            "Chromium failed to start or navigate. Ensure Playwright Chromium and system dependencies are installed."
        ) from None
    raise RuntimeError("Chromium could not fetch the Scholar profile.")
