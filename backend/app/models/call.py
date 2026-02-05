"""Call model for VoIP call tracking."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CallDirection(str, Enum):
    """Call direction type."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Call lifecycle status."""
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallOutcome(str, Enum):
    """Call outcome classification."""
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    ESCALATED = "escalated"
    INFORMATION_PROVIDED = "information_provided"
    WRONG_NUMBER = "wrong_number"
    VOICEMAIL = "voicemail"
    OTHER = "other"


class Call(Base):
    """Call model for VoIP call tracking and recording."""

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Twilio Identifiers
    call_sid: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    parent_call_sid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Call Details
    direction: Mapped[str] = mapped_column(String(20), default=CallDirection.INBOUND.value)
    from_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    to_number: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Status and Timing
    status: Mapped[str] = mapped_column(String(20), default=CallStatus.INITIATED.value)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # AI Handling
    handled_by_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_to_agent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    escalation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Recording
    recording_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recording_sid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recording_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Transcript (stored in MongoDB, reference here)
    transcript_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transcript_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Outcome
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Lead Association
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    lead_created: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Properties Discussed (stored as JSON array of IDs)
    properties_discussed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Quality Metrics
    sentiment_score: Mapped[Optional[float]] = mapped_column(nullable=True)  # -1 to 1
    customer_satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Call {self.call_sid} ({self.status})>"
