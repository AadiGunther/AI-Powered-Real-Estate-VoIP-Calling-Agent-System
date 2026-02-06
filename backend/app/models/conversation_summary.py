"""MongoDB document models for conversation summaries."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """MongoDB document for conversation summaries."""
    
    call_sid: str = Field(..., description="Twilio call SID")
    summary: str = Field(..., description="Short summary for sales agents (max 200 words)")
    
    # Customer Information
    customer_name: Optional[str] = Field(None, description="Customer name if provided")
    phone_number: str = Field(..., description="Customer phone number")
    preferred_language: Optional[str] = Field(None, description="Preferred language (Hindi, English, etc.)")
    
    # Requirements Extracted
    requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted requirements: location, property_type, budget_min, budget_max, size_min, size_max, bedrooms"
    )
    
    # Properties Discussed
    properties_discussed: List[int] = Field(
        default_factory=list,
        description="List of property IDs discussed during call"
    )
    
    # Lead Quality Assessment
    lead_quality: str = Field("cold", description="hot, warm, or cold")
    
    # Key Points
    key_points: List[str] = Field(
        default_factory=list,
        description="Important points from the conversation"
    )
    
    # Next Steps
    next_steps: Optional[str] = Field(None, description="Recommended next steps for sales agent")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_sid": "CA1234567890abcdef",
                "summary": "Customer looking for 2BHK apartment in Whitefield, budget 45-50 lakhs. Interested in properties near schools. Wants to schedule site visit next weekend.",
                "customer_name": "Rajesh Kumar",
                "phone_number": "+919876543210",
                "preferred_language": "Hindi",
                "requirements": {
                    "location": "Whitefield",
                    "property_type": "apartment",
                    "budget_min": 4500000,
                    "budget_max": 5000000,
                    "bedrooms": 2
                },
                "properties_discussed": [101, 105, 108],
                "lead_quality": "hot",
                "key_points": [
                    "Needs property near good schools",
                    "Ready to move in 3 months",
                    "Prefers ground or first floor"
                ],
                "next_steps": "Schedule site visit for next Saturday. Send property details via WhatsApp."
            }
        }
