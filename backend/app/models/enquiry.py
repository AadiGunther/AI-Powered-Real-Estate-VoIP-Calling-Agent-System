"""Enquiry model for tracking customer enquiries from calls."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnquiryType(str, Enum):
    """Type of customer enquiry."""
    PROPERTY_SEARCH = "property_search"
    PRICING = "pricing"
    AVAILABILITY = "availability"
    SITE_VISIT = "site_visit"
    DOCUMENTATION = "documentation"
    GENERAL = "general"


class Enquiry(Base):
    """Enquiry model for tracking individual enquiries from calls."""

    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Call Association
    call_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    
    # Enquiry Details
    enquiry_type: Mapped[str] = mapped_column(String(50), default=EnquiryType.GENERAL.value)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)  # Original customer query
    
    # Extracted Intent
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_mentioned: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    budget_mentioned: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    property_type_mentioned: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Response
    ai_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_successful: Mapped[bool] = mapped_column(default=True)
    
    # Property Matches
    properties_suggested: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Enquiry {self.id} ({self.enquiry_type})>"
