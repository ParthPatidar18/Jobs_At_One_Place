"""Utilities for extracting URLs from message text."""

from __future__ import annotations

import re


URL_PATTERN = re.compile(r"https?://[^\s]+")


def extract_urls(text: str) -> list[str]:
    """Return all HTTP and HTTPS URLs found in *text*."""

    return URL_PATTERN.findall(text)
