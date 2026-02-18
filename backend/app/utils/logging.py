"""Structured logging utilities."""

import logging
import sys
from typing import Any

import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structured logging for the application."""
    
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance for the given name."""
    return structlog.get_logger(name)


class CallLogger:
    """Specialized logger for call-related events."""
    
    def __init__(self, call_sid: str):
        self.logger = get_logger("voip.call")
        self.call_sid = call_sid
    
    def log(self, event: str, **kwargs: Any) -> None:
        """Log a call event."""
        self.logger.info(event, call_sid=self.call_sid, **kwargs)
    
    def error(self, event: str, **kwargs: Any) -> None:
        """Log a call error."""
        self.logger.error(event, call_sid=self.call_sid, **kwargs)
    
    def audio_received(self, chunk_size: int) -> None:
        """Log audio chunk received."""
        self.logger.debug(
            "audio_chunk_received",
            call_sid=self.call_sid,
            chunk_size=chunk_size,
        )
    
    def stt_result(self, transcript: str, is_final: bool) -> None:
        """Log STT result."""
        self.logger.info(
            "stt_result",
            call_sid=self.call_sid,
            transcript=transcript,
            is_final=is_final,
        )
    
    def ai_response(self, response: str) -> None:
        """Log AI response."""
        self.logger.info("ai_response", call_sid=self.call_sid, response=response[:100])
    
    def tts_generated(self, duration_ms: int) -> None:
        """Log TTS generation."""
        self.logger.info("tts_generated", call_sid=self.call_sid, duration_ms=duration_ms)
