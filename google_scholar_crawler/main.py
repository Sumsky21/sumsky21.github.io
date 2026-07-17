import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from scholarly import scholarly


MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def fetch_author(scholar_id: str) -> dict:
    """Fetch an author profile, retrying short-lived Scholar failures."""
    scholarly.set_timeout(REQUEST_TIMEOUT_SECONDS)
    scholarly.set_retries(2)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(
                f"Fetching Google Scholar profile "
                f"(attempt {attempt}/{MAX_ATTEMPTS})...",
                flush=True,
            )
            author = scholarly.search_author_id(scholar_id)
            author = scholarly.fill(
                author,
                sections=["basics", "indices", "counts", "publications"],
            )

            if "citedby" not in author or "publications" not in author:
                raise RuntimeError("Google Scholar returned an incomplete author profile")
            return author
        except Exception as error:
            print(f"Attempt {attempt} failed: {error}", flush=True)
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(5 * attempt)

    raise RuntimeError("Google Scholar data could not be fetched")


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

    author = fetch_author(scholar_id)
    write_results(author)
    print(
        f"Saved {len(author['publications'])} publications and "
        f"{author['citedby']} total citations.",
        flush=True,
    )


if __name__ == "__main__":
    main()
