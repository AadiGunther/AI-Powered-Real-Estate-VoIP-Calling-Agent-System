"""Lead schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field

from app.models.lead import LeadQuality, LeadStatus, LeadSource


class LeadBase(BaseModel):
    """Base lead schema."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=20)
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
