import unittest
from unittest.mock import Mock, patch

from main import fetch_author, main, parse_author
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

    @patch("main.fetch_profile_html", return_value=PROFILE_HTML)
    def test_browser_html_is_parsed(self, fetch: Mock) -> None:
        author = fetch_author("abc", "NID=secret-value")
        self.assertEqual(author["citedby"], 1234)
        fetch.assert_called_once_with("abc", "NID=secret-value")

    def test_cookie_validation_rejects_header_injection(self) -> None:
        self.assertEqual(validate_cookie_header("Cookie: NID=abc; SID=xyz"), "NID=abc; SID=xyz")
        for value in ("", "NID=abc\r\nHost: example.com", "not-a-cookie"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_cookie_header(value)

    @patch.dict("os.environ", {
        "GOOGLE_SCHOLAR_ID": "abc",
        "GOOGLE_SCHOLAR_COOKIE": "NID=should-not-be-used",
        "SCHOLAR_PROVIDER": "browser",
    }, clear=True)
    @patch("main.write_results")
    @patch("main.fetch_author", return_value={"citedby": 42, "publications": []})
    def test_anonymous_default_ignores_existing_cookie_secret(self, fetch, write):
        with patch("builtins.print"):
            main()
        fetch.assert_called_once_with("abc", "")
        write.assert_called_once()

    @patch.dict("os.environ", {
        "GOOGLE_SCHOLAR_ID": "abc",
        "SCHOLAR_AUTH_MODE": "cookie",
        "SCHOLAR_PROVIDER": "browser",
    }, clear=True)
    @patch("main.fetch_author")
    def test_explicit_cookie_mode_requires_cookie(self, fetch):
        with self.assertRaisesRegex(RuntimeError, "Cookie mode requires"):
            main()
        fetch.assert_not_called()

if __name__ == "__main__":
    unittest.main()
