"""Application workflow for persisting and enriching job messages."""

from __future__ import annotations

import logging

from core.interfaces import (
    DirectApplyResolverProtocol,
    HtmlExtractorProtocol,
    JobParserProtocol,
    JobRepositoryProtocol,
)
from models.job_details import JobDetails
from models.job_message import JobMessage
from utils.url_filter import is_job_url


logger = logging.getLogger(__name__)

class JobPipeline:
    """Coordinate persistence, raw-page retrieval, and HTML parsing for a job."""

    def __init__(
        self,
        *,
        repository: JobRepositoryProtocol,
        extractor: HtmlExtractorProtocol,
        parser: JobParserProtocol,
        direct_apply_resolver: DirectApplyResolverProtocol,
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._parser = parser
        self._direct_apply_resolver = direct_apply_resolver

    async def process(self, job_message: JobMessage) -> list[JobDetails]:
        """Persist a new job and return details parsed from every source URL."""

        if not isinstance(job_message, JobMessage):
            raise TypeError("JobPipeline.process accepts only JobMessage instances")

        logger.info("Pipeline received JobMessage message_id=%d", job_message.message_id)

        if self._repository.job_exists(job_message.message_id):
            logger.info("Skipping duplicate JobMessage message_id=%d", job_message.message_id)
            return []

        if not self._repository.save(job_message):
            logger.error(
                "JobMessage message_id=%d was not persisted; skipping enrichment",
                job_message.message_id,
            )
            return []

        logger.info("Persisted JobMessage message_id=%d", job_message.message_id)
        job_details: list[JobDetails] = []

        for url in job_message.urls:
            if not is_job_url(url):
                logger.info("Skipping non-job URL url=%s", url)
                continue

            try:
                logger.info("Resolving direct application url=%s", url)
                final_apply_url = await self._direct_apply_resolver.resolve(url)

                logger.info("Fetching final job page url=%s", final_apply_url)
                html = await self._extractor.fetch_html(final_apply_url)

                logger.info("Parsing final job page url=%s", final_apply_url)
                details = self._parser.parse(html, final_apply_url)
                details.apply_url = final_apply_url
                if not self._repository.save_job_application(
                    job_message.message_id, url, final_apply_url, details
                ):
                    logger.error("Unable to persist resolved application source_url=%s", url)
                job_details.append(details)
            except Exception:
                logger.exception(
                    "Unable to enrich JobMessage message_id=%d from url=%s",
                    job_message.message_id,
                    url,
                )

        logger.info(
            "Pipeline completed JobMessage message_id=%d with %d parsed pages",
            job_message.message_id,
            len(job_details),
        )
        return job_details
