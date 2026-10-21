import unittest
from unittest.mock import Mock, patch

import requests

from main import describe_request_error, fetch_author, parse_author


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
        response.url = "https://api.scraperapi.com?api_key=secret-value"
        error = requests.HTTPError(response=response)

        message = describe_request_error(error)

        self.assertEqual(message, "ScraperAPI returned HTTP 500")
        self.assertNotIn("secret-value", message)

    @patch("main.requests.get")
    def test_fetch_uses_direct_api_with_bounded_timeout(self, get: Mock) -> None:
        response = Mock()
        response.text = PROFILE_HTML
        get.return_value = response

        author = fetch_author("abc", "secret-value")

        self.assertEqual(author["citedby"], 1234)
        get.assert_called_once()
        _, kwargs = get.call_args
        self.assertEqual(kwargs["params"]["api_key"], "secret-value")
        self.assertIn("user=abc", kwargs["params"]["url"])
        self.assertEqual(kwargs["timeout"], (10, 70))


if __name__ == "__main__":
    unittest.main()
