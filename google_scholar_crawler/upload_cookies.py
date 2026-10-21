"""Upload a Scholar request Cookie header to an Actions repository secret."""

import argparse
import getpass
from pathlib import Path
import shutil
import subprocess

from scholar_cookies import validate_cookie_header


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Sumsky21/sumsky21.github.io")
    parser.add_argument("--file", type=Path, help="File containing the raw Cookie header value")
    parser.add_argument("--user-agent", help="Optional User-Agent copied from the same browser request")
    args = parser.parse_args()
    gh = shutil.which("gh")
    if not gh:
        parser.exit(1, "Install GitHub CLI first, then run: gh auth login\n")
    if subprocess.run([gh, "auth", "status"], capture_output=True).returncode:
        parser.exit(1, "GitHub CLI is not authenticated. Run: gh auth login\n")
    try:
        raw = args.file.read_text(encoding="utf-8-sig") if args.file else getpass.getpass(
            "Paste the Scholar request Cookie value (hidden): "
        )
        cookie = validate_cookie_header(raw)
    except (OSError, ValueError):
        parser.exit(1, "Cannot read a valid single-line Cookie header. Check the input.\n")
    secrets = {"GOOGLE_SCHOLAR_COOKIE": cookie}
    if args.user_agent:
        if any(ord(char) < 32 or ord(char) > 126 for char in args.user_agent):
            parser.exit(1, "User-Agent must be a single-line ASCII value.\n")
        secrets["GOOGLE_SCHOLAR_USER_AGENT"] = args.user_agent
    for name, value in secrets.items():
        # stdin keeps cookie values out of command arguments and shell history.
        result = subprocess.run(
            [gh, "secret", "set", name, "--repo", args.repo],
            input=value.encode("utf-8"), capture_output=True,
        )
        if result.returncode:
            parser.exit(1, f"Could not update {name}. Check repository access and gh authentication.\n")
        print(f"Updated {name} in {args.repo}.")
    print("After pushing the workflow changes, use Run workflow on main.")


if __name__ == "__main__":
    main()
