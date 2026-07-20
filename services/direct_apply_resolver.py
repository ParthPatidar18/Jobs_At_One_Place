"""Resolve job aggregators to the most relevant direct application page."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit

from core.interfaces import DirectApplyResolverProtocol
from playwright.async_api import Browser, Page, async_playwright


logger = logging.getLogger(__name__)

_ATS_DOMAINS = frozenset(
    {
        "workday.com",
        "myworkdayjobs.com",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "oraclecloud.com",
        "icims.com",
        "successfactors.com",
        "taleo.net",
    }
)
_BLOCKED_DOMAINS = frozenset(
    {
        "whatsapp.com",
        "api.whatsapp.com",
        "telegram.org",
        "telegram.dog",
        "t.me",
        "instagram.com",
        "facebook.com",
        "youtube.com",
        "youtu.be",
        "play.google.com",
    }
)
_HARD_NEGATIVE_TERMS = ("download", "share", "subscribe", "login", "register group", "channel")


@dataclass(frozen=True, slots=True)
class _ScoredLink:
    url: str
    score: int


class DirectApplyResolver(DirectApplyResolverProtocol):
    """Find the highest-relevance application link and follow its redirects."""

    def __init__(self, *, timeout_ms: int = 30_000, max_depth: int = 5, max_retries: int = 2) -> None:
        self._timeout_ms = timeout_ms
        self._max_depth = max_depth
        self._max_retries = max_retries

    async def resolve(self, url: str) -> str:
        """Return the strongest direct application URL, falling back to ``url`` on failure."""

        for attempt in range(1, self._max_retries + 2):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        return await self._resolve_once(browser, url)
                    finally:
                        await browser.close()
            except Exception as error:
                logger.warning(
                    "Direct apply resolution failed url=%s attempt=%d/%d error=%s",
                    url,
                    attempt,
                    self._max_retries + 1,
                    error,
                )
                if attempt <= self._max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        logger.error("Direct apply resolution exhausted retries url=%s", url)
        return url

    async def _resolve_once(self, browser: Browser, source_url: str) -> str:
        context = await browser.new_context()
        try:
            page = await context.new_page()
            current_url = source_url
            visited: set[str] = set()

            for depth in range(self._max_depth + 1):
                current_url = urldefrag(current_url).url
                if current_url in visited:
                    logger.warning("Stopping direct apply resolution due to URL loop url=%s", current_url)
                    return current_url
                visited.add(current_url)

                await page.goto(current_url, wait_until="networkidle", timeout=self._timeout_ms)
                current_url = urldefrag(page.url).url
                logger.info("Direct apply redirect depth=%d url=%s", depth, current_url)

                if _is_ats_url(current_url):
                    logger.info("Selected ATS application URL url=%s", current_url)
                    return current_url

                selected = await self._select_best_link(page)
                if selected is None:
                    logger.info("No eligible application link found; using url=%s", current_url)
                    return current_url

                logger.info("Selected direct apply candidate url=%s score=%d", selected.url, selected.score)
                current_url = selected.url

            logger.info("Direct apply resolver reached max depth url=%s", current_url)
            return current_url
        finally:
            await context.close()

    async def _select_best_link(self, page: Page) -> _ScoredLink | None:
        """Score every anchor on the page and return the strongest eligible URL."""

        anchors = page.locator("a[href]")
        candidates: list[_ScoredLink] = []

        for index in range(await anchors.count()):
            anchor = anchors.nth(index)
            href = await anchor.get_attribute("href")
            if not href:
                continue

            absolute_url = urldefrag(urljoin(page.url, href)).url
            score = _score_link(absolute_url, await anchor.text_content())
            logger.info("Direct apply candidate url=%s score=%d", absolute_url, score)
            if score > 0:
                candidates.append(_ScoredLink(absolute_url, score))

        if not candidates:
            return None
        return max(candidates, key=lambda candidate: (candidate.score, candidate.url))


def _score_link(url: str, anchor_text: str | None) -> int:
    """Score a candidate using career/ATS signals and hard social-link exclusions."""

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    haystack = f"{hostname}{parsed.path} {anchor_text or ''}".casefold()

    if parsed.scheme not in {"http", "https"} or not hostname:
        return -1000
    if _matches_domain(hostname, _BLOCKED_DOMAINS):
        return -1000
    if any(term in haystack for term in _HARD_NEGATIVE_TERMS):
        return -1000
    path_segments = {segment for segment in parsed.path.casefold().split("/") if segment}
    if hostname.startswith("app.") or "app" in path_segments or "app-download" in haystack:
        return -1000

    score = 0
    if hostname.startswith("careers.") or hostname.startswith("jobs."):
        score += 100
    if _matches_domain(hostname, _ATS_DOMAINS):
        score += 80
    if "apply" in haystack:
        score += 25
    if "careers" in haystack or "career" in haystack:
        score += 20
    if "job" in haystack or "position" in haystack:
        score += 15
    return score


def _is_ats_url(url: str) -> bool:
    return _matches_domain((urlsplit(url).hostname or "").lower(), _ATS_DOMAINS)


def _matches_domain(hostname: str, domains: frozenset[str]) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)
