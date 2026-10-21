import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from main import main, write_results
from serpapi_fetch import fetch_author_serpapi


PROFILE = {
    "search_metadata": {"status": "Success"},
    "author": {"name": "Test Author"},
    "cited_by": {"table": [
        {"citations": {"all": 1234, "since_2021": 900}},
        {"h_index": {"all": 12, "since_2021": 10}},
        {"i10_index": {"all": 8, "since_2021": 7}},
    ]},
    "articles": [
        {"citation_id": "abc:one", "title": "Paper One", "year": "2026",
         "publication": "Venue, 2026", "cited_by": {
             "value": 42, "cites_id": "123,456",
             "link": "https://scholar.google.com/scholar?cites=123,456"}},
        {"citation_id": "abc:two", "title": "Paper Two", "cited_by": {"value": None}},
    ],
}


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class SerpApiTests(unittest.TestCase):
    def setUp(self):
        printer = patch("builtins.print")
        printer.start()
        self.addCleanup(printer.stop)

    @patch("serpapi_fetch.urlopen")
    def test_profile_keeps_website_json_contract(self, request):
        request.return_value = response(PROFILE)
        author = fetch_author_serpapi("abc", "synthetic-key")
        self.assertEqual(author["hindex5y"], 10)
        self.assertEqual(author["i10index"], 8)
        query = parse_qs(urlparse(request.call_args.args[0]).query)
        self.assertEqual(query["num"], ["100"])
        self.assertEqual(query["engine"], ["google_scholar_author"])
        with tempfile.TemporaryDirectory() as directory:
            with patch("main.RESULTS_DIR", Path(directory)):
                write_results(author)
            saved = json.loads((Path(directory) / "gs_data.json").read_text(encoding="utf-8"))
            badge = json.loads((Path(directory) / "gs_data_shieldsio.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["citedby"], 1234)
        self.assertEqual(saved["publications"]["abc:one"]["num_citations"], 42)
        self.assertEqual(saved["publications"]["abc:one"]["cites_id"], ["123", "456"])
        self.assertEqual(saved["publications"]["abc:two"]["num_citations"], 0)
        self.assertEqual(badge["message"], "1234")

    @patch("serpapi_fetch.urlopen")
    def test_pagination_uses_fixed_endpoint_and_merges_articles(self, request):
        first = copy.deepcopy(PROFILE)
        first["serpapi_pagination"] = {"next": "https://example.org/untrusted"}
        second = {"search_metadata": {"status": "Success"}, "articles": [
            {"citation_id": "abc:three", "title": "Paper Three", "cited_by": {"value": 1}},
        ]}
        request.side_effect = [response(first), response(second)]
        author = fetch_author_serpapi("abc", "synthetic-key")
        self.assertEqual(len(author["publications"]), 3)
        second_url = urlparse(request.call_args.args[0])
        self.assertEqual(second_url.netloc, "serpapi.com")
        self.assertEqual(parse_qs(second_url.query)["start"], ["2"])

    @patch("serpapi_fetch.urlopen")
    def test_repeated_page_is_rejected(self, request):
        first = copy.deepcopy(PROFILE)
        first["serpapi_pagination"] = {"next": "next"}
        request.side_effect = [response(first), response(PROFILE)]
        with self.assertRaisesRegex(RuntimeError, "repeated"):
            fetch_author_serpapi("abc", "synthetic-key")

    @patch("serpapi_fetch.urlopen")
    def test_errors_and_missing_stats_are_not_saved(self, request):
        for payload in ({"error": "synthetic-key"}, {**PROFILE, "cited_by": {}},
                        {**PROFILE, "articles": None}):
            with self.subTest(payload=payload), patch.dict("os.environ", {
                "GOOGLE_SCHOLAR_ID": "abc", "SERPAPI_API_KEY": "synthetic-key",
            }, clear=True), patch("main.write_results") as write:
                request.return_value = response(payload)
                with self.assertRaises(RuntimeError) as failure:
                    main()
                self.assertNotIn("synthetic-key", str(failure.exception))
                write.assert_not_called()

    @patch("serpapi_fetch.urlopen")
    def test_http_auth_and_quota_errors_are_not_retried(self, request):
        for code in (401, 403, 429):
            with self.subTest(code=code):
                request.reset_mock()
                request.side_effect = HTTPError("https://serpapi.com/?api_key=synthetic-key", code,
                                                "synthetic-key", {}, None)
                with self.assertRaisesRegex(RuntimeError, str(code)) as failure:
                    fetch_author_serpapi("abc", "synthetic-key")
                self.assertNotIn("synthetic-key", str(failure.exception))
                self.assertEqual(request.call_count, 1)

    @patch("serpapi_fetch.urlopen")
    def test_transient_errors_retry_once(self, request):
        for error in (HTTPError("url", 500, "error", {}, None), URLError("network")):
            with self.subTest(error=type(error).__name__):
                request.reset_mock()
                request.side_effect = [error, response(PROFILE)]
                self.assertEqual(fetch_author_serpapi("abc", "synthetic-key")["citedby"], 1234)
                self.assertEqual(request.call_count, 2)

    @patch("serpapi_fetch.urlopen")
    def test_missing_key_fails_before_network(self, request):
        with self.assertRaisesRegex(RuntimeError, "SERPAPI_API_KEY is not set"):
            fetch_author_serpapi("abc", "")
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
