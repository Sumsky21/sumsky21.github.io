import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError as BrowserTimeout

from browser_fetch import browser_cookies, fetch_profile_html


class BrowserFetchTests(unittest.TestCase):
    def test_cookie_values_and_domain_scope(self):
        cookies = browser_cookies("NID=abc==; SID=xyz")
        self.assertEqual(cookies, [
            {"name": "NID", "value": "abc==", "url": "https://scholar.google.com/"},
            {"name": "SID", "value": "xyz", "url": "https://scholar.google.com/"},
        ])

    def make_browser(self, factory, status=200):
        browser = factory.return_value.__enter__.return_value.chromium.launch.return_value
        context = browser.new_context.return_value
        page = context.new_page.return_value
        page.goto.return_value.status = status
        page.url = "https://scholar.google.com/citations?user=abc"
        page.locator.return_value.count.return_value = 0
        page.content.return_value = "<html>profile</html>"
        return browser, context, page

    @patch("browser_fetch.sync_playwright")
    def test_success_imports_cookies_and_closes_browser(self, factory):
        browser, context, page = self.make_browser(factory)
        self.assertEqual(fetch_profile_html("abc", "NID=secret-value"), "<html>profile</html>")
        context.add_cookies.assert_called_once_with(browser_cookies("NID=secret-value"))
        context.close.assert_called_once()
        browser.close.assert_called_once()

    @patch("browser_fetch.time.sleep")
    @patch("browser_fetch.sync_playwright")
    def test_explicit_block_is_not_retried(self, factory, sleep):
        browser, context, page = self.make_browser(factory, status=403)
        with self.assertRaisesRegex(RuntimeError, "HTTP 403 in Chromium") as caught:
            fetch_profile_html("abc", "NID=secret-value")
        self.assertNotIn("secret-value", str(caught.exception))
        page.goto.assert_called_once()
        sleep.assert_not_called()
        browser.close.assert_called_once()

    @patch("browser_fetch.sync_playwright")
    def test_captcha_is_reported(self, factory):
        _, _, page = self.make_browser(factory)
        page.locator.return_value.count.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "interactive verification"):
            fetch_profile_html("abc", "NID=secret-value")

    @patch("browser_fetch.time.sleep")
    @patch("browser_fetch.sync_playwright")
    def test_timeouts_retry_only_once_and_hide_details(self, factory, sleep):
        _, context, page = self.make_browser(factory)
        page.goto.side_effect = BrowserTimeout("sensitive session data")
        with self.assertRaisesRegex(RuntimeError, "timed out") as caught:
            fetch_profile_html("abc", "NID=secret-value")
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(page.goto.call_count, 2)
        self.assertEqual(context.close.call_count, 2)
        sleep.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()
