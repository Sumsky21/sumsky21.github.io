import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scholar_cookies import validate_cookie_header


MAX_ATTEMPTS = 2
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 45
RESULTS_DIR = Path(__file__).resolve().parent / "results"
SCHOLAR_PROFILE_URL = "https://scholar.google.com/citations"


def parse_count(value: str) -> int:
    """Convert a formatted Scholar citation count to an integer."""
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else 0


def parse_author(html: str, scholar_id: str) -> dict:
    """Extract the citation fields consumed by the website."""
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one("form#gs_captcha_f") or soup.select_one("#gs_captcha_ccl"):
        raise RuntimeError("Google Scholar returned a CAPTCHA page")

    stats = soup.select("td.gsc_rsb_std")
    if not stats:
        raise RuntimeError("Google Scholar returned a page without citation statistics")

    author = {
        "container_type": "Author",
        "filled": ["basics", "publications", "indices"],
        "scholar_id": scholar_id,
        "source": "AUTHOR_PROFILE_PAGE",
        "citedby": parse_count(stats[0].get_text()),
        "publications": [],
    }

    name = soup.select_one("#gsc_prf_in")
    if name:
        author["name"] = name.get_text(strip=True)

    index_names = (
        "citedby",
        "citedby5y",
        "hindex",
        "hindex5y",
        "i10index",
        "i10index5y",
    )
    for key, element in zip(index_names, stats):
        author[key] = parse_count(element.get_text())

    for row in soup.select("tr.gsc_a_tr"):
        title_link = row.select_one("a.gsc_a_at")
        if not title_link:
            continue

        publication_id = parse_qs(
            urlparse(title_link.get("href", "")).query
        ).get("citation_for_view", [None])[0]
        if not publication_id:
            continue

        citation_link = row.select_one(".gsc_a_ac")
        citation_href = citation_link.get("href", "") if citation_link else ""
        gray_lines = row.select("div.gs_gray")
        year = row.select_one(".gsc_a_h")

        publication = {
            "container_type": "Publication",
            "source": "AUTHOR_PUBLICATION_ENTRY",
            "bib": {
                "title": title_link.get_text(strip=True),
                "citation": (
                    gray_lines[1].get_text(" ", strip=True)
                    if len(gray_lines) > 1
                    else ""
                ),
            },
            "filled": False,
            "author_pub_id": publication_id,
            "num_citations": (
                parse_count(citation_link.get_text()) if citation_link else 0
            ),
        }

        if year and year.get_text(strip=True):
            publication["bib"]["pub_year"] = year.get_text(strip=True)
        if citation_href:
            publication["citedby_url"] = urljoin(
                "https://scholar.google.com", citation_href
            )
            cites_ids = parse_qs(urlparse(citation_href).query).get("cites")
            if cites_ids:
                publication["cites_id"] = cites_ids[0].split(",")

        author["publications"].append(publication)

    if not author["publications"]:
        raise RuntimeError("Google Scholar returned a page without publications")

    return author


def describe_request_error(error: requests.RequestException) -> str:
    """Return an error message without request headers or cookie values."""
    if isinstance(error, requests.Timeout):
        return "Google Scholar request timed out"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return f"Google Scholar returned HTTP {error.response.status_code}"
    if isinstance(error, requests.ConnectionError):
        return "Could not connect to Google Scholar"
    return f"Google Scholar request failed ({type(error).__name__})"


def fetch_author(scholar_id: str, cookie: str, user_agent: str = "") -> dict:
    """Fetch a Scholar profile directly using a browser Cookie header."""
    cookie = validate_cookie_header(cookie)
    headers = {"Cookie": cookie, "Accept-Language": "en-US,en;q=0.9"}
    if user_agent:
        headers["User-Agent"] = user_agent
    target_request = requests.Request(
        "GET",
        SCHOLAR_PROFILE_URL,
        params={"hl": "en", "user": scholar_id, "pagesize": 100},
    ).prepare()
    last_error = "unknown error"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"Fetching Google Scholar profile "
            f"(attempt {attempt}/{MAX_ATTEMPTS})...",
            flush=True,
        )
        try:
            response = requests.get(
                target_request.url,
                headers=headers,
                # Do not forward the raw Cookie header to a redirect destination.
                allow_redirects=False,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            )
            if response.status_code in (301, 302, 303, 307, 308, 401, 403, 429):
                raise RuntimeError(
                    f"Google Scholar returned HTTP {response.status_code}. "
                    "Refresh the browser Cookie secret; Actions IP may still be blocked."
                )
            response.raise_for_status()
            return parse_author(response.text, scholar_id)
        except requests.RequestException as error:
            last_error = describe_request_error(error)
        except RuntimeError as error:
            # Repeating a CAPTCHA or blocked response does not refresh a browser session.
            raise RuntimeError(
                f"{error}. Open Scholar in your browser, complete any verification, "
                "and upload a fresh Cookie header."
            ) from None

        print(f"Attempt {attempt} failed: {last_error}", flush=True)
        if attempt < MAX_ATTEMPTS:
            time.sleep(5)

    raise RuntimeError(
        f"Google Scholar data could not be fetched after "
        f"{MAX_ATTEMPTS} attempts: {last_error}"
    )


def write_results(author: dict) -> None:
    author["updated"] = datetime.now(timezone.utc).isoformat()
    author["publications"] = {
        publication["author_pub_id"]: publication
        for publication in author["publications"]
        if publication.get("author_pub_id")
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULTS_DIR / "gs_data.json").open("w", encoding="utf-8") as output:
        json.dump(author, output, ensure_ascii=False)

    shields_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": str(author["citedby"]),
    }
    with (RESULTS_DIR / "gs_data_shieldsio.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(shields_data, output, ensure_ascii=False)


def main() -> None:
    scholar_id = os.environ.get("GOOGLE_SCHOLAR_ID", "").strip()
    if not scholar_id:
        raise RuntimeError(
            "GOOGLE_SCHOLAR_ID is not set. Add it as a GitHub Actions secret."
        )

    cookie = os.environ.get("GOOGLE_SCHOLAR_COOKIE", "").strip()
    if not cookie:
        raise RuntimeError(
            "GOOGLE_SCHOLAR_COOKIE is not set. Run upload_cookies.py locally first."
        )

    author = fetch_author(
        scholar_id, cookie, os.environ.get("GOOGLE_SCHOLAR_USER_AGENT", "").strip()
    )
    write_results(author)
    print(
        f"Saved {len(author['publications'])} publications and "
        f"{author['citedby']} total citations.",
        flush=True,
    )


if __name__ == "__main__":
    main()
