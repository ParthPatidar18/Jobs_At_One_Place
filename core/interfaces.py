"""Structural interfaces for replaceable application dependencies."""

from __future__ import annotations

from typing import Protocol

from models.job_details import JobDetails
from models.job_message import JobMessage


class JobRepositoryProtocol(Protocol):
    """Persistence operations required by the job-processing pipeline."""

    def save(self, job: JobMessage) -> bool: ...

    def job_exists(self, message_id: int) -> bool: ...

    def get_job(self, message_id: int) -> JobMessage | None: ...

    def get_all_jobs(self) -> list[JobMessage]: ...

    def save_job_application(
        self,
        message_id: int,
        source_url: str,
        final_apply_url: str,
        details: JobDetails,
    ) -> bool: ...

    def close(self) -> None: ...


class HtmlExtractorProtocol(Protocol):
    """Asynchronous retrieval of rendered HTML for a URL."""

    async def fetch_html(self, url: str) -> str: ...


class DirectApplyResolverProtocol(Protocol):
    """Resolve aggregator pages to their final application destination."""

    async def resolve(self, url: str) -> str: ...


class JobParserProtocol(Protocol):
    """Conversion of raw HTML into structured job details."""

    def parse(self, html: str, url: str) -> JobDetails: ...
