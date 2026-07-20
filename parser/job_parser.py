"""Extract framework-independent job details from raw HTML."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from core.interfaces import JobParserProtocol
from models.job_details import JobDetails


logger = logging.getLogger(__name__)

_NON_VISIBLE_TAGS = ("script", "style", "noscript", "template", "svg")
_WHITESPACE = re.compile(r"[\t \f\v]+")
_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")


class JobParser(JobParserProtocol):
    """Parse a job page without depending on its site-specific implementation."""

    def parse(self, html: str, url: str) -> JobDetails:
        """Return structured job details extracted only from ``html`` and ``url``."""

        soup = BeautifulSoup(html, "html.parser")
        job_posting = _find_job_posting(soup)
        visible_text = _visible_text(soup)

        details = JobDetails(
            title=_first_non_empty(
                _as_text(job_posting.get("title")),
                _meta_content(soup, "property", "og:title"),
                _meta_content(soup, "name", "twitter:title"),
                _element_text(soup.select_one("h1")),
                _element_text(soup.title),
            ),
            company=_first_non_empty(
                _organization_name(job_posting.get("hiringOrganization")),
                _label_value(visible_text, "company", "organization", "employer"),
            ),
            location=_none_if_empty(
                _first_non_empty(
                    _location_text(job_posting.get("jobLocation")),
                    _label_value(visible_text, "location", "job location"),
                )
            ),
            experience=_none_if_empty(
                _first_non_empty(
                    _as_text(job_posting.get("experienceRequirements")),
                    _label_value(visible_text, "experience", "experience required"),
                )
            ),
            salary=_none_if_empty(
                _first_non_empty(
                    _salary_text(job_posting.get("baseSalary")),
                    _label_value(visible_text, "salary", "compensation", "pay"),
                )
            ),
            employment_type=_none_if_empty(
                _first_non_empty(
                    _as_text(job_posting.get("employmentType")),
                    _label_value(visible_text, "employment type", "job type", "type"),
                )
            ),
            work_mode=_none_if_empty(
                _label_value(visible_text, "work mode", "workplace type", "remote status")
            ),
            skills=_skills(job_posting.get("skills"), visible_text),
            description=_first_non_empty(
                _html_to_visible_text(_as_text(job_posting.get("description"))),
                _description_from_page(soup),
                visible_text,
            ),
            apply_url=_find_apply_url(soup, url),
        )
        logger.info(
            "Parsed job details title=%r company=%r skills=%d from url=%s",
            details.title,
            details.company,
            len(details.skills),
            url,
        )
        return details
def _find_job_posting(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select('script[type="application/ld+json"]'):
        raw_json = script.string or script.get_text()
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.debug("Skipping invalid JSON-LD block while parsing job page")
            continue

        for item in _json_ld_items(payload):
            item_type = item.get("@type")
            if item_type == "JobPosting" or (
                isinstance(item_type, list) and "JobPosting" in item_type
            ):
                return item
    return {}


def _json_ld_items(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from _json_ld_items(item)
    elif isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _json_ld_items(item)
        yield payload


def _visible_text(soup: BeautifulSoup) -> str:
    """Return human-visible page text with stable, readable whitespace."""

    visible_soup = BeautifulSoup(str(soup), "html.parser")
    for element in visible_soup.find_all(_NON_VISIBLE_TAGS):
        element.decompose()
    for element in visible_soup.select("[hidden], [aria-hidden='true']"):
        element.decompose()

    text = visible_soup.get_text("\n", strip=True)
    return _normalize_text(text)


def _html_to_visible_text(html: str) -> str:
    return _visible_text(BeautifulSoup(html, "html.parser")) if html else ""


def _normalize_text(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    return _MULTIPLE_NEWLINES.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def _element_text(element: Tag | None) -> str:
    return _normalize_text(element.get_text(" ", strip=True)) if element else ""


def _meta_content(soup: BeautifulSoup, attribute: str, value: str) -> str:
    element = soup.find("meta", attrs={attribute: value})
    return _normalize_text(str(element.get("content", ""))) if element else ""


def _description_from_page(soup: BeautifulSoup) -> str:
    selectors = (
        "[data-testid*='description']",
        "[class*='job-description' i]",
        "[id*='job-description' i]",
        "article",
        "main",
    )
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            return _visible_text(BeautifulSoup(str(element), "html.parser"))
    return ""


def _label_value(text: str, *labels: str) -> str:
    for label in labels:
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*[:\-]\s*(.+)$", text)
        if match:
            return _normalize_text(match.group(1))
    return ""


def _organization_name(value: Any) -> str:
    if isinstance(value, dict):
        return _as_text(value.get("name"))
    return _as_text(value)


def _location_text(value: Any) -> str:
    locations = value if isinstance(value, list) else [value]
    results: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            results.append(_as_text(location))
            continue
        address = location.get("address", location)
        if isinstance(address, dict):
            parts = [
                _as_text(address.get(key))
                for key in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")
            ]
            results.append(", ".join(part for part in parts if part))
        else:
            results.append(_as_text(address))
    return "; ".join(result for result in results if result)


def _salary_text(value: Any) -> str:
    if not isinstance(value, dict):
        return _as_text(value)
    currency = _as_text(value.get("currency"))
    amount = value.get("value")
    if isinstance(amount, dict):
        amount = amount.get("value") or amount.get("minValue")
    return " ".join(part for part in (currency, _as_text(amount)) if part)


def _skills(value: Any, visible_text: str) -> list[str]:
    raw_skills = _as_text(value) or _label_value(visible_text, "skills", "required skills")
    if not raw_skills:
        return []
    return list(dict.fromkeys(skill.strip() for skill in re.split(r"[,;|\n]", raw_skills) if skill.strip()))


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(item for item in (_as_text(item) for item in value) if item)
    if isinstance(value, dict):
        return _as_text(value.get("name") or value.get("value"))
    return _normalize_text(str(value))


def _first_non_empty(*values: str) -> str:
    return next((value for value in values if value), "")


def _none_if_empty(value: str) -> str | None:
    return value or None


def _find_apply_url(soup: BeautifulSoup, page_url: str) -> str:
    for anchor in soup.find_all("a", href=True):
        text = _element_text(anchor).lower()
        href = str(anchor["href"])
        if "apply" in text or "apply" in href.lower():
            return urljoin(page_url, href)
    return page_url
