"""Application entry point for the Telegram job listener."""

from __future__ import annotations

import os
from collections.abc import Sequence

from dotenv import load_dotenv

from database.repository import JobRepository
from parser.job_parser import JobParser
from scraper.extractor import JobPageExtractor
from services.direct_apply_resolver import DirectApplyResolver
from services.message_processor import MessageProcessor
from services.pipeline import JobPipeline
from telegram.listener import TelegramJobListener


TARGET_CHANNELS: Sequence[str] = (
    "Freshershunt - Off Campus Drive Updates",
    "Off Campus Jobs â›¥",
    "Fresher Jobs â›¥",
    "IT Job Updates - Freshers",
    "Placement Lelo",
    "Remote Jobs Notifier",
)


def main() -> None:
    """Load configuration, initialize the listener, and start the application."""

    load_dotenv()
    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]

    repository = JobRepository()
    repository.init()
    extractor = JobPageExtractor()
    parser = JobParser()
    direct_apply_resolver = DirectApplyResolver()
    pipeline = JobPipeline(
        repository=repository,
        extractor=extractor,
        parser=parser,
        direct_apply_resolver=direct_apply_resolver,
    )

    listener = TelegramJobListener(
        api_id=api_id,
        api_hash=api_hash,
        target_channels=TARGET_CHANNELS,
        message_processor=MessageProcessor(pipeline),
    )
    try:
        listener.run()
    finally:
        repository.close()


if __name__ == "__main__":
    main()
