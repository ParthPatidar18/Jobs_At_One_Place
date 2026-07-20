"""A resolved application URL and its structured job-page details."""

from __future__ import annotations

from dataclasses import dataclass

from models.job_details import JobDetails


@dataclass(frozen=True, slots=True)
class JobApplication:
    """Persisted relationship between a source link and its final application page."""

    message_id: int
    source_url: str
    final_apply_url: str
    details: JobDetails
