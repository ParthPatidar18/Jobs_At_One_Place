"""Framework-independent structured details extracted from a job page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class JobDetails:
    """Normalized job information obtained from raw job-page HTML."""

    title: str
    company: str
    location: str | None
    experience: str | None
    salary: str | None
    employment_type: str | None
    skills: list[str]
    description: str
    apply_url: str
    work_mode: str | None = None
