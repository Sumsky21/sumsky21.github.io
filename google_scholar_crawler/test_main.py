import unittest
from unittest.mock import Mock, patch

import requests

from main import describe_request_error, fetch_author, parse_author
from scholar_cookies import validate_cookie_header


PROFILE_HTML = """
<html>
  <div id="gsc_prf_in">Test Author</div>
  <table>
    <tr>
      <td class="gsc_rsb_std">1,234</td>
      <td class="gsc_rsb_std">900</td>
      <td class="gsc_rsb_std">12</td>
      <td class="gsc_rsb_std">10</td>
      <td class="gsc_rsb_std">8</td>
      <td class="gsc_rsb_std">7</td>
    </tr>
  </table>
  <table>
    <tr class="gsc_a_tr">
      <td>
        <a class="gsc_a_at"
           href="/citations?view_op=view_citation&amp;citation_for_view=abc:one">
          Paper One
        </a>
        <div class="gs_gray">A Author</div>
        <div class="gs_gray">Venue, 2026</div>
      </td>
      <td><a class="gsc_a_ac" href="/scholar?cites=12345">42</a></td>
      <td class="gsc_a_h">2026</td>
    </tr>
    <tr class="gsc_a_tr">
      <td>
        <a class="gsc_a_at" href="/citations?citation_for_view=abc:two">
          Paper Two
        </a>
        <div class="gs_gray">A Author</div>
      </td>
      <td><span class="gsc_a_ac"></span></td>
    </tr>
  </table>
</html>
"""


class ParseAuthorTests(unittest.TestCase):
    def test_parses_counts_and_publications(self) -> None:
        author = parse_author(PROFILE_HTML, "abc")

        self.assertEqual(author["name"], "Test Author")
        self.assertEqual(author["citedby"], 1234)
        self.assertEqual(len(author["publications"]), 2)

        cited = author["publications"][0]
        self.assertEqual(cited["author_pub_id"], "abc:one")
        self.assertEqual(cited["num_citations"], 42)
        self.assertEqual(cited["cites_id"], ["12345"])

        uncited = author["publications"][1]
        self.assertEqual(uncited["author_pub_id"], "abc:two")
        self.assertEqual(uncited["num_citations"], 0)

    def test_rejects_incomplete_page(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "without citation statistics"):
            parse_author("<html></html>", "abc")

    def test_request_error_does_not_expose_api_key(self) -> None:
        response = requests.Response()
        response.status_code = 500
        response.url = "https://scholar.google.com/citations"
        error = requests.HTTPError(response=response)

        message = describe_request_error(error)

        self.assertEqual(message, "Google Scholar returned HTTP 500")
        self.assertNotIn("secret-value", message)

    @patch("main.requests.get")
    def test_fetch_sends_cookie_only_to_scholar(self, get: Mock) -> None:
        response = Mock()
        response.status_code = 200
        response.text = PROFILE_HTML
        get.return_value = response

        author = fetch_author("abc", "NID=secret-value", "Browser test")

        self.assertEqual(author["citedby"], 1234)
        get.assert_called_once()
        args, kwargs = get.call_args
        self.assertTrue(args[0].startswith("https://scholar.google.com/citations?"))
        self.assertIn("user=abc", args[0])
        self.assertNotIn("secret-value", args[0])
        self.assertEqual(kwargs["headers"]["Cookie"], "NID=secret-value")
        self.assertEqual(kwargs["headers"]["User-Agent"], "Browser test")
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (10, 45))

    @patch("main.requests.get")
    def test_redirect_and_blocks_stop_without_retry(self, get: Mock) -> None:
        for status in (302, 403, 429):
            with self.subTest(status=status):
                get.reset_mock()
                get.return_value.status_code = status
                with self.assertRaisesRegex(RuntimeError, f"HTTP {status}"):
                    fetch_author("abc", "NID=secret-value")
                get.assert_called_once()

    def test_cookie_validation_rejects_header_injection(self) -> None:
        self.assertEqual(validate_cookie_header("Cookie: NID=abc; SID=xyz"), "NID=abc; SID=xyz")
        for value in ("", "NID=abc\r\nHost: example.com", "not-a-cookie"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_cookie_header(value)

    @patch("main.time.sleep")
    @patch("main.requests.get")
    def test_transient_error_retries_without_leaking_cookie(self, get: Mock, sleep: Mock) -> None:
        get.side_effect = requests.ConnectionError("NID=secret-value")
        with self.assertRaises(RuntimeError) as caught:
            fetch_author("abc", "NID=secret-value")
        self.assertNotIn("secret-value", str(caught.exception))
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()
