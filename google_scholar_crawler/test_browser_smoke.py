"""Optional real-browser check using synthetic HTML and synthetic cookies only."""

import os
import unittest

from playwright.sync_api import sync_playwright

from browser_fetch import browser_cookies, selected_browser
from main import parse_author
from test_main import PROFILE_HTML


@unittest.skipUnless(os.environ.get("SCHOLAR_BROWSER_SMOKE") == "1", "Browser smoke check is opt-in")
class BrowserSmokeTests(unittest.TestCase):
    def test_browser_cookie_store_and_rendered_profile(self):
        with sync_playwright() as playwright:
            browser_name = selected_browser()
            launch_options = {"headless": True, "timeout": 30000}
            if browser_name == "chromium":
                launch_options["channel"] = os.environ.get("SCHOLAR_TEST_BROWSER_CHANNEL", "chromium")
            browser = getattr(playwright, browser_name).launch(**launch_options)
            try:
                context = browser.new_context(locale="en-US")
                context.add_cookies(browser_cookies("NID=synthetic-cookie"))
                profile_url = "https://scholar.google.com/citations?user=abc"
                stored_cookies = {
                    cookie["name"]: cookie["value"]
                    for cookie in context.cookies([profile_url])
                }
                self.assertEqual(stored_cookies.get("NID"), "synthetic-cookie")
                self.assertEqual(context.cookies(["https://example.org/"]), [])

                def profile_route(route):
                    # Routing happens before the network stack attaches cookies.
                    # A fulfilled request never goes over the wire, so its Cookie
                    # header cannot be used to assert actual cookie transmission.
                    route.fulfill(status=200, content_type="text/html", body=PROFILE_HTML)

                # No request reaches Google or any other external site.
                context.route("**/*", profile_route)
                page = context.new_page()
                page.goto(profile_url, wait_until="domcontentloaded")
                author = parse_author(page.content(), "abc")
                self.assertEqual(author["citedby"], 1234)
                self.assertEqual(len(author["publications"]), 2)
                self.assertIn("NID=synthetic-cookie", page.evaluate("document.cookie"))
                context.close()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
