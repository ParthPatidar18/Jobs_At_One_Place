"""Domain representation of a received job-channel message."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class JobMessage:
    """Normalized job message passed to all application pipeline stages."""

    message_id: int
    channel_name: str
    message_text: str
    urls: list[str]
    received_at: datetime
    source: str
    media_present: bool
