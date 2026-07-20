"""URL eligibility rules for job-page scraping."""

from __future__ import annotations

from urllib.parse import urlsplit


_BLOCKED_DOMAINS = frozenset(
    {
        "whatsapp.com",
        "t.me",
        "telegram.me",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "instagram.com",
        "x.com",
        "twitter.com",
        "drive.google.com",
        "docs.google.com",
    }
)


def is_job_url(url: str) -> bool:
    """Return whether a URL is a plausible external job-page candidate."""

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    if parsed.scheme not in {"http", "https"} or not hostname:
        return False
    if any(hostname == domain or hostname.endswith(f".{domain}") for domain in _BLOCKED_DOMAINS):
        return False
    if (hostname == "linkedin.com" or hostname.endswith(".linkedin.com")) and parsed.path.startswith(
        "/feed"
    ):
        return False
    return True
