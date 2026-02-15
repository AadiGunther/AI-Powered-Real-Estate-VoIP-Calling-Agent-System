"""Call schemas for request/response validation."""

from datetime import datetime, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from app.models.call import CallDirection, CallStatus, CallOutcome
from app.utils.logging import get_logger


_ist_tz = ZoneInfo("Asia/Kolkata")
_call_schema_logger = get_logger("schemas.call")


class CallBase(BaseModel):
    """Base call schema."""
    call_sid: str
    from_number: str
    to_number: str
    direction: CallDirection = CallDirection.INBOUND


class CallCreate(CallBase):
    """Schema for creating a new call record."""
    pass


class CallUpdate(BaseModel):
    """Schema for updating call information."""
    status: Optional[CallStatus] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    transcript_id: Optional[str] = None
    transcript_summary: Optional[str] = None
    outcome: Optional[CallOutcome] = None
    outcome_notes: Optional[str] = None
    lead_id: Optional[int] = None
    escalated_to_human: Optional[bool] = None
    escalated_to_agent_id: Optional[int] = None
    escalation_reason: Optional[str] = None


class CallOutcomeUpdate(BaseModel):
    """Schema for updating call outcome."""
    outcome: CallOutcome
    notes: Optional[str] = None


class CallNotesUpdate(BaseModel):
    """Schema for adding notes to a call."""
    notes: str = Field(..., min_length=1, max_length=2000)


class DialRequest(BaseModel):
    """Schema for initiating an outbound call."""
    to_number: str
    lead_id: Optional[int] = None


class CallResponse(BaseModel):
    """Call response schema."""
    id: int
    call_sid: str
    direction: str
    from_number: str
    to_number: str
    
    status: str
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    handled_by_ai: bool
    escalated_to_human: bool
    escalated_to_agent_id: Optional[int] = None
    escalation_reason: Optional[str] = None
    
    recording_url: Optional[str] = None
    transcript_id: Optional[str] = None
    transcript_summary: Optional[str] = None
    
    outcome: Optional[str] = None
    outcome_notes: Optional[str] = None
    
    lead_id: Optional[int] = None
    lead_created: bool
    
    sentiment_score: Optional[float] = None
    customer_satisfaction: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("created_at", "updated_at", "started_at", "answered_at", "ended_at", mode="after")
    @classmethod
    def to_ist(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is None:
            return None
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            _call_schema_logger.info(
                "call_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class CallSearchParams(BaseModel):
    """Call search parameters."""
    direction: Optional[CallDirection] = None
    status: Optional[CallStatus] = None
    outcome: Optional[CallOutcome] = None
    handled_by_ai: Optional[bool] = None
    escalated: Optional[bool] = None
    from_number: Optional[str] = None
    lead_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    agent_id: Optional[int] = None


class CallListResponse(BaseModel):
    """Paginated call list response."""
    calls: List[CallResponse]
    total: int
    page: int
    page_size: int


class TranscriptMessage(BaseModel):
    """Individual transcript message."""
    role: str  # "customer" or "agent"
    content: str
    timestamp: datetime

    @field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            _call_schema_logger.info(
                "transcript_timestamp_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class CallTranscript(BaseModel):
    """Full call transcript."""
    call_id: int
    call_sid: str
    messages: List[TranscriptMessage]
    summary: Optional[str] = None
