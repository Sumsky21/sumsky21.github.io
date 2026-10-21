"""Fetch Google Scholar author data through SerpApi, keeping API keys out of logs."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://serpapi.com/search.json"
PAGE_SIZE = 100
MAX_PAGES = 10


def _count(value):
    if isinstance(value, bool):
        raise RuntimeError("SerpApi returned an invalid citation count.")
    text = str(value).replace(",", "").strip()
    if not text.isascii() or not text.isdigit():
        raise RuntimeError("SerpApi returned an invalid citation count.")
    return int(text)


def _request_page(scholar_id, api_key, start, deadline):
    query = urlencode({
        "engine": "google_scholar_author", "author_id": scholar_id,
        "api_key": api_key, "hl": "en", "num": PAGE_SIZE, "start": start,
    })
    for attempt in range(2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("SerpApi fetch exceeded its 150-second time budget.")
        print(f"Fetching Scholar via SerpApi (offset {start}, attempt {attempt + 1}/2)...", flush=True)
        try:
            with urlopen(f"{API_URL}?{query}", timeout=min(60, remaining)) as response:
                payload = json.load(response)
        except HTTPError as error:
            code = error.code
            error.close()
            if code >= 500 and attempt == 0:
                continue
            hints = {
                401: "Check the SERPAPI_API_KEY secret.",
                403: "Check SerpApi account access and API key.",
                429: "Check your SerpApi search quota or hourly limit.",
            }
            hint = hints.get(code, "Request failed; try again later.")
            raise RuntimeError(f"SerpApi HTTP {code}. {hint}") from None
        except (URLError, TimeoutError, OSError):
            if attempt == 0:
                continue
            raise RuntimeError("SerpApi network request failed after 2 attempts.") from None
        except (ValueError, UnicodeError):
            raise RuntimeError("SerpApi returned invalid JSON.") from None

        if not isinstance(payload, dict) or payload.get("error"):
            # Do not print API response bodies: they may echo request credentials.
            raise RuntimeError("SerpApi returned an API error; check the SerpApi dashboard.")
        if payload.get("search_metadata", {}).get("status") != "Success":
            raise RuntimeError("SerpApi did not return a completed search.")
        return payload


def _profile(payload, scholar_id):
    profile = payload.get("author")
    if not isinstance(profile, dict) or not profile.get("name"):
        raise RuntimeError("SerpApi response is missing the author profile.")
    author = {
        "container_type": "Author", "filled": ["basics", "publications", "indices"],
        "scholar_id": scholar_id, "source": "GOOGLE_SCHOLAR_VIA_SERPAPI",
        "name": profile["name"], "publications": [],
    }
    for row in payload.get("cited_by", {}).get("table", []):
        for api_name, output_name in (("citations", "citedby"), ("h_index", "hindex"), ("i10_index", "i10index")):
            if api_name not in row:
                continue
            values = row[api_name]
            author[output_name] = _count(values.get("all"))
            recent = [value for key, value in values.items() if key.startswith("since_")]
            if recent:
                author[output_name + "5y"] = _count(recent[0])
    if "citedby" not in author:
        raise RuntimeError("SerpApi response is missing total citations; old data will be preserved.")
    return author


def _publication(article, scholar_id):
    citation_id = article.get("citation_id", "")
    if not citation_id.startswith(scholar_id + ":") or not article.get("title"):
        raise RuntimeError("SerpApi returned an incomplete or mismatched publication.")
    cited = article.get("cited_by") or {}
    publication = {
        "container_type": "Publication", "source": "AUTHOR_PUBLICATION_ENTRY",
        "filled": False, "author_pub_id": citation_id,
        "bib": {"title": article["title"], "citation": article.get("publication", "")},
        "num_citations": _count(cited.get("value") or 0),
    }
    if article.get("year"):
        publication["bib"]["pub_year"] = str(article["year"])
    if cited.get("link"):
        publication["citedby_url"] = cited["link"]
    if cited.get("cites_id"):
        publication["cites_id"] = str(cited["cites_id"]).split(",")
    return publication


def fetch_author_serpapi(scholar_id: str, api_key: str) -> dict:
    if not api_key.strip():
        raise RuntimeError("SERPAPI_API_KEY is not set. Add it as a GitHub Actions secret.")
    deadline = time.monotonic() + 150
    author = None
    seen = set()
    start = 0
    for _ in range(MAX_PAGES):
        payload = _request_page(scholar_id, api_key.strip(), start, deadline)
        if author is None:
            author = _profile(payload, scholar_id)
        articles = payload.get("articles")
        if not isinstance(articles, list):
            raise RuntimeError("SerpApi response is missing the publications list.")
        for article in articles:
            publication = _publication(article, scholar_id)
            citation_id = publication["author_pub_id"]
            if citation_id in seen:
                raise RuntimeError("SerpApi pagination repeated a publication; refusing partial data.")
            seen.add(citation_id)
            author["publications"].append(publication)
        if not payload.get("serpapi_pagination", {}).get("next"):
            return author
        if not articles:
            raise RuntimeError("SerpApi pagination made no progress; refusing partial data.")
        start += len(articles)
    raise RuntimeError("SerpApi exceeded the 10-page limit; refusing partial data.")
