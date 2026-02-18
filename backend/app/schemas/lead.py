"""Lead schemas for request/response validation."""

from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.lead import LeadQuality, LeadSource, LeadStatus
from app.utils.logging import get_logger

_ist_tz = ZoneInfo("Asia/Kolkata")
_lead_schema_logger = get_logger("schemas.lead")


class LeadBase(BaseModel):
    """Base lead schema."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: str = Field(..., min_length=5, max_length=100)
    email: Optional[EmailStr] = None


class LeadCreate(LeadBase):
    """Schema for creating a new lead."""
    source: LeadSource = LeadSource.INBOUND_CALL
    preferred_location: Optional[str] = None
    preferred_property_type: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    """Schema for updating lead information."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    
    preferred_location: Optional[str] = None
    preferred_property_type: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_size_min: Optional[float] = None
    preferred_size_max: Optional[float] = None
    
    interested_property_id: Optional[int] = None
    notes: Optional[str] = None
    
    next_follow_up: Optional[datetime] = None


class LeadQualityUpdate(BaseModel):
    """Schema for updating lead quality."""
    quality: LeadQuality


class LeadStatusUpdate(BaseModel):
    """Schema for updating lead status."""
    status: LeadStatus


class LeadAssign(BaseModel):
    """Schema for assigning lead to agent."""
    agent_id: int


class LeadBulkAssign(BaseModel):
    """Schema for bulk assigning leads to an agent."""
    agent_id: int
    lead_ids: List[int]


class LeadResponse(LeadBase):
    """Lead response schema."""
    id: int
    quality: str
    status: str
    source: str
    
    preferred_location: Optional[str] = None
    preferred_property_type: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    
    interested_property_id: Optional[int] = None
    notes: Optional[str] = None
    ai_summary: Optional[str] = None
    last_call_notes: Optional[str] = None
    
    assigned_agent_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    
    next_follow_up: Optional[datetime] = None
    follow_up_count: int = 0
    
    converted_at: Optional[datetime] = None
    conversion_value: Optional[float] = None
    
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator(
        "created_at",
        "updated_at",
        "assigned_at",
        "next_follow_up",
        "converted_at",
        "last_contacted_at",
        mode="after",
    )
    @classmethod
    def to_ist(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is None:
            return None
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            _lead_schema_logger.info(
                "lead_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class LeadSearchParams(BaseModel):
    """Lead search parameters."""
    quality: Optional[LeadQuality] = None
    status: Optional[LeadStatus] = None
    source: Optional[LeadSource] = None
    assigned_agent_id: Optional[int] = None
    unassigned: Optional[bool] = None
    phone: Optional[str] = None


class LeadListResponse(BaseModel):
    """Paginated lead list response."""
    leads: List[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadAiSummaryResponse(BaseModel):
    lead_id: int
    lead_quality_score: int = Field(..., ge=0, le=100)
    engagement_level: str
    likelihood_to_convert: int = Field(..., ge=0, le=100)
    recommended_next_actions: List[str]
    key_conversation_points: List[str]
    patterns: List[str]
    generated_at: datetime
    source_call_ids: List[int] = []
