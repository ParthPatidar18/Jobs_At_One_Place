"""Read-only data and presentation mapping for the dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from database.repository import JobRepository
from models.job_application import JobApplication
from models.job_message import JobMessage


UNKNOWN = "Unknown"
_LABELS: dict[str, tuple[str, ...]] = {
    "company": ("company", "organization", "employer"),
    "role": ("role", "position", "job title", "title"),
    "location": ("location", "job location"),
    "experience": ("experience", "experience required"),
    "skills": ("skills", "required skills", "tech stack"),
}


@dataclass(frozen=True, slots=True)
class DashboardJob:
    """A display-safe, read-only view of a persisted job message."""

    message_id: int
    company: str
    role: str
    location: str
    experience: str
    salary: str
    employment_type: str
    work_mode: str
    skills: tuple[str, ...]
    source_channel: str
    apply_url: str | None
    received_at: datetime
    message_text: str


class DashboardService:
    """Read jobs from the existing repository without modifying application data."""

    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def load_jobs(self) -> list[DashboardJob]:
        """Return persisted jobs in reverse chronological order for the dashboard."""

        try:
            jobs = self._repository.get_all_jobs()
            applications = self._repository.get_job_applications()
            jobs_by_id = {job.message_id: job for job in jobs}
            resolved_message_ids = {application.message_id for application in applications}

            dashboard_jobs = [
                self._application_to_dashboard_job(application, jobs_by_id.get(application.message_id))
                for application in applications
                if application.message_id in jobs_by_id
            ]
            dashboard_jobs.extend(
                self._to_dashboard_job(job)
                for job in jobs
                if job.message_id not in resolved_message_ids
            )
            return sorted(
                dashboard_jobs,
                key=lambda job: job.received_at,
                reverse=True,
            )
        finally:
            self._repository.close()

    @staticmethod
    def _to_dashboard_job(job: JobMessage) -> DashboardJob:
        text = _normalize_text(job.message_text)
        company = _field(text, "company")
        role = _field(text, "role") or _first_line(text)
        skills = _skills(_field(text, "skills"))

        return DashboardJob(
            message_id=job.message_id,
            company=company or UNKNOWN,
            role=role or UNKNOWN,
            location=_field(text, "location") or UNKNOWN,
            experience=_field(text, "experience") or UNKNOWN,
            salary=UNKNOWN,
            employment_type=UNKNOWN,
            work_mode=UNKNOWN,
            skills=skills,
            source_channel=job.channel_name or UNKNOWN,
            apply_url=_first_http_url(job.urls),
            received_at=job.received_at,
            message_text=text,
        )

    @staticmethod
    def _application_to_dashboard_job(
        application: JobApplication, job: JobMessage | None
    ) -> DashboardJob:
        """Use final-page data and URL while retaining source-channel context."""

        details = application.details
        return DashboardJob(
            message_id=application.message_id,
            company=details.company or UNKNOWN,
            role=details.title or UNKNOWN,
            location=details.location or UNKNOWN,
            experience=details.experience or UNKNOWN,
            salary=details.salary or UNKNOWN,
            employment_type=details.employment_type or UNKNOWN,
            work_mode=details.work_mode or UNKNOWN,
            skills=tuple(details.skills),
            source_channel=job.channel_name if job else UNKNOWN,
            apply_url=application.final_apply_url or application.source_url,
            received_at=job.received_at if job else datetime.now(timezone.utc),
            message_text=job.message_text if job else details.description,
        )

def filter_jobs(
    jobs: list[DashboardJob],
    *,
    search: str,
    company: str,
    role: str,
    location: str,
    experience: str,
    source_channel: str,
    work_mode: str = "All",
) -> list[DashboardJob]:
    """Filter dashboard jobs using the selected sidebar criteria."""

    query = search.casefold().strip()

    def matches(job: DashboardJob) -> bool:
        searchable = " ".join(
            (job.company, job.role, job.location, job.experience, job.source_channel, *job.skills)
        ).casefold()
        return (
            (not query or query in searchable)
            and _matches_option(job.company, company)
            and _matches_option(job.role, role)
            and _matches_option(job.location, location)
            and _matches_option(job.experience, experience)
            and _matches_option(job.source_channel, source_channel)
            and (work_mode == "All" or (work_mode == "Remote" and is_remote(job)) or (work_mode == "On-site" and not is_remote(job)))
        )

    return [job for job in jobs if matches(job)]


def metrics(jobs: list[DashboardJob]) -> tuple[int, int, int, int]:
    """Return total, today, known-company, and fresher-job counts."""

    today = datetime.now(timezone.utc).date()
    jobs_today = sum(job.received_at.date() == today for job in jobs)
    companies = {job.company for job in jobs if job.company != UNKNOWN}
    fresher_jobs = sum(
        any(term in f"{job.role} {job.experience} {job.message_text}".casefold() for term in (
            "fresher", "freshers", "entry level", "0 years", "0-1 year", "0 to 1 year"
        ))
        for job in jobs
    )
    return len(jobs), jobs_today, len(companies), fresher_jobs


def options(jobs: list[DashboardJob], attribute: str) -> list[str]:
    """Return sorted values for a sidebar filter."""

    return ["All", *sorted({str(getattr(job, attribute)) for job in jobs})]


def _field(text: str, field_name: str) -> str:
    labels = "|".join(re.escape(label) for label in _LABELS[field_name])
    match = re.search(rf"(?im)^\s*(?:{labels})\s*[:\-]\s*(.+)$", text)
    return match.group(1).strip() if match else ""


def _first_line(text: str) -> str:
    return next((line for line in text.splitlines() if line.strip()), "")[:140]


def _skills(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(skill.strip() for skill in re.split(r"[,;|]", value) if skill.strip()))


def _first_http_url(urls: list[str]) -> str | None:
    for url in urls:
        if urlsplit(url).scheme in {"http", "https"}:
            return url
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _matches_option(value: str, selected: str) -> bool:
    return selected == "All" or value == selected


def is_remote(job: DashboardJob) -> bool:
    """Return a display-safe remote classification from existing job fields."""

    text = f"{job.work_mode} {job.location} {job.message_text}".casefold()
    return "remote" in text or "work from home" in text or "wfh" in text


def display_match_score(job: DashboardJob) -> int:
    """Create a stable UI-only relevance signal; it is not persisted or used by the pipeline."""

    text = f"{job.role} {job.company} {' '.join(job.skills)} {job.message_text}".casefold()
    signal_terms = ("python", "java", "backend", "software", "engineer", "developer", "ai", "data")
    signal = sum(term in text for term in signal_terms)
    entropy = sum(ord(character) for character in f"{job.company}{job.role}") % 12
    return min(98, 72 + signal * 3 + entropy)


def relative_time(received_at: datetime) -> str:
    """Format an opportunity timestamp for compact job-card metadata."""

    elapsed = max(0, int((datetime.now(timezone.utc) - received_at).total_seconds()))
    if elapsed < 3600:
        return f"{max(1, elapsed // 60)}m ago"
    if elapsed < 86400:
        return f"{elapsed // 3600}h ago"
    return f"{elapsed // 86400}d ago"
