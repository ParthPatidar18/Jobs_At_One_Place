"""Telegram transport adapter for monitored job-channel messages."""

from __future__ import annotations

import logging
from collections.abc import Collection
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.tl.custom.message import Message

from services.message_processor import MessageProcessor


logger = logging.getLogger(__name__)


class TelegramJobListener:
    """Receive messages from configured Telegram channels and dispatch them."""

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        target_channels: Collection[str],
        message_processor: MessageProcessor,
        session_name: str = "job_session",
    ) -> None:
        self._client = TelegramClient(session_name, api_id, api_hash)
        self._target_channels = frozenset(target_channels)
        self._message_processor = message_processor
        self._live_handler_registered = False

    def run(self) -> None:
        """Connect to Telegram and run the asynchronous message listener."""

        with self._client:
            self._client.loop.run_until_complete(self.start())
            self._client.run_until_disconnected()

    async def start(self) -> None:
        """Backfill recent history, then begin handling live Telegram messages."""

        me = await self._client.get_me()
        print("=" * 80)
        print(f"Logged in as: {me.first_name}")
        print("=" * 80)
        try:
            await self._sync_history()
        except Exception:
            logger.exception("History sync failed; starting live listener regardless")

        logger.info("Starting live listener...")
        self._register_live_handler()
        print("\nListening for new job posts...\n")
        logger.info("Telegram listener started for %d configured channels", len(self._target_channels))

    async def _sync_history(self) -> None:
        """Process the previous ten days of messages in chronological order."""

        logger.info("Starting history sync...")
        cutoff = datetime.now(timezone.utc) - timedelta(days=10)

        async for dialog in self._client.iter_dialogs():
            if dialog.name not in self._target_channels:
                continue

            logger.info("Processing channel %s...", dialog.name)
            recent_messages: list[Message] = []

            try:
                async for message in self._client.iter_messages(dialog.id):
                    message_date = message.date
                    if message_date.tzinfo is None:
                        message_date = message_date.replace(tzinfo=timezone.utc)

                    if message_date < cutoff:
                        break
                    recent_messages.append(message)
            except Exception:
                logger.exception("Unable to fetch history for channel %s", dialog.name)
                continue

            for message in reversed(recent_messages):
                await self._dispatch(message)

        logger.info("History sync completed.")

    def _register_live_handler(self) -> None:
        """Register the live handler once, after historical sync is complete."""

        if not self._live_handler_registered:
            self._client.add_event_handler(self._handle_new_message, events.NewMessage)
            self._live_handler_registered = True

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        """Receive a new Telegram message and dispatch it when it is in scope."""

        try:
            chat = await event.get_chat()
            chat_name = getattr(chat, "title", None)
            if chat_name not in self._target_channels:
                return

            logger.debug("Received a new message from monitored channel %s", chat_name)
            await self._dispatch(event.message)
        except Exception:
            logger.exception("Unable to handle incoming Telegram message")

    async def _dispatch(self, message: Message) -> None:
        """Deliver a Telegram message to the application message processor."""

        try:
            await self._message_processor.process_message(message)
        except Exception:
            logger.exception("Unable to process Telegram message; continuing listener")
