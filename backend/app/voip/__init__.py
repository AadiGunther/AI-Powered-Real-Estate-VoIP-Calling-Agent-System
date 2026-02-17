"""VoIP package initialization."""

from app.voip.media_stream import router as media_stream_router
from app.voip.prompts import (
    REAL_ESTATE_ASSISTANT_PROMPT,
    GREETING_MESSAGE,
    FALLBACK_MESSAGE,
    ESCALATION_MESSAGE,
)

__all__ = [
    "media_stream_router",
    "REAL_ESTATE_ASSISTANT_PROMPT",
    "GREETING_MESSAGE",
    "FALLBACK_MESSAGE",
    "ESCALATION_MESSAGE",
]
