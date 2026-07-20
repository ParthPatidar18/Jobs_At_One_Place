"""Async Playwright extraction of raw job-page HTML."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

from playwright.async_api import Browser, async_playwright

from core.interfaces import HtmlExtractorProtocol

logger = logging.getLogger(__name__)


class JobPageExtractionError(RuntimeError):
    """Raised when a job page cannot be fetched after all attempts."""


class JobPageExtractor(HtmlExtractorProtocol):
    """Fetch the fully rendered HTML for a job URL using Playwright."""

    def __init__(self, *, timeout_ms: int = 30_000, max_retries: int = 2) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._timeout_ms = timeout_ms
        self._max_retries = max_retries

    async def fetch_html(self, url: str) -> str:
        """Return raw rendered HTML for ``url`` after at most two retries.

        Each attempt waits up to 30 seconds by default for network activity to
        become idle, allowing JavaScript-rendered job pages to finish loading.
        """

        self._validate_url(url)
        last_error: Exception | None = None
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        return await self._fetch_once(browser, url)
                    finally:
                        await browser.close()
            except Exception as error:
                last_error = error
                logger.warning(
                    "Job page fetch failed for url=%s (attempt %d/%d): %s",
                    url,
                    attempt,
                    attempts,
                    error,
                )

                if attempt < attempts:
                    await asyncio.sleep(2 ** (attempt - 1))

        logger.error("Job page fetch failed after %d attempts for url=%s", attempts, url)
        raise JobPageExtractionError(
            f"Unable to fetch job page after {attempts} attempts: {url}"
        ) from last_error

    async def _fetch_once(self, browser: Browser, url: str) -> str:
        """Fetch a page once and return only its rendered HTML."""

        context = await browser.new_context()
        try:
            page = await context.new_page()
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self._timeout_ms,
            )

            if response is None:
                raise JobPageExtractionError(f"No HTTP response received for: {url}")
            if response.status >= 400:
                raise JobPageExtractionError(
                    f"Job page returned HTTP {response.status}: {url}"
                )

            html = await page.content()
            if not html:
                raise JobPageExtractionError(f"Job page returned empty HTML: {url}")
            return html
        finally:
            await context.close()

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject invalid input before starting a browser."""

        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.error("Invalid job page URL: %r", url)
            raise JobPageExtractionError(f"Expected an absolute HTTP(S) URL, got: {url!r}")
