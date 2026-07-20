"""Application service that processes incoming Telegram job messages."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol

from models.job_message import JobMessage
from services.pipeline import JobPipeline
from utils.url_utils import extract_urls


logger = logging.getLogger(__name__)


class TelegramChat(Protocol):
    """A Telegram entity whose optional naming fields are resolved safely."""


class IncomingTelegramMessage(Protocol):
    """Structural interface implemented by the Telegram message adapter."""

    id: int
    raw_text: str
    date: datetime
    media: object | None

    async def get_chat(self) -> TelegramChat: ...


class MessageProcessor:
    """Convert incoming Telegram messages into framework-independent domain data."""

    def __init__(self, pipeline: JobPipeline) -> None:
        self._pipeline = pipeline

    async def process_message(self, message: IncomingTelegramMessage) -> JobMessage:
        """Create, log, display, and return a normalized :class:`JobMessage`."""

        job_message = await self.create_job_message(message)

        await self._pipeline.process(job_message)

        logger.info("Processing JobMessage: %s", job_message)

        self._print_job_message(job_message)
        return job_message

    async def create_job_message(self, message: IncomingTelegramMessage) -> JobMessage:
        """Factory that converts an incoming Telegram message into ``JobMessage``."""

        chat = await message.get_chat()
        message_text = message.raw_text

        return JobMessage(
            message_id=message.id,
            channel_name=self._resolve_chat_name(chat),
            message_text=message_text,
            urls=extract_urls(message_text),
            received_at=message.date,
            source="telegram",
            media_present=message.media is not None,
        )

    @staticmethod
    def _resolve_chat_name(chat: object) -> str:
        """Resolve channel, group, and user entities without unsafe attributes."""

        title = getattr(chat, "title", None)
        if isinstance(title, str) and title.strip():
            return title

        first_name = getattr(chat, "first_name", None)
        if isinstance(first_name, str) and first_name.strip():
            return first_name

        username = getattr(chat, "username", None)
        if isinstance(username, str) and username.strip():
            return username

        return "Unknown User"

    @staticmethod
    def _print_job_message(job_message: JobMessage) -> None:
        """Keep the current console output while using only domain data."""

        print("\n" + "=" * 80)
        print("NEW JOB ALERT")
        print("=" * 80)
        print(f"Channel : {job_message.channel_name}\n")
        print("Message:\n")
        print(job_message.message_text)

        if job_message.urls:
            print("\nURLs Found:")
            for url in job_message.urls:
                print("   ", url)
        else:
            print("\nNo URLs Found")

        print("=" * 80)
