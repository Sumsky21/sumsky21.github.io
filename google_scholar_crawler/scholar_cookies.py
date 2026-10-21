"""Validate a Cookie request header without logging its contents."""

import re


def validate_cookie_header(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("cookie:"):
        value = value[7:].strip()
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Cookie must be a nonempty, single-line ASCII request header.")
    for part in value.split(";"):
        name, separator, _ = part.strip().partition("=")
        if not separator or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise ValueError("Invalid Cookie header. Copy the request's Cookie value.")
    if len(value.encode("utf-8")) > 40000:
        raise ValueError("Cookie header is too large for this uploader.")
    return value
