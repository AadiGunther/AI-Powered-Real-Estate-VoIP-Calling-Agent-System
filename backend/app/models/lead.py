"""Lead model for customer management."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.call import Call


class LeadQuality(str, Enum):
    """Lead quality classification."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class LeadStatus(str, Enum):
    """Lead lifecycle status."""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSource(str, Enum):
    """Lead acquisition source."""
    INBOUND_CALL = "inbound_call"
    OUTBOUND_CALL = "outbound_call"
    WEBSITE = "website"
    REFERRAL = "referral"
    WALK_IN = "walk_in"
    OTHER = "other"


class Lead(Base):
    """Lead model for customer/prospect management."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Customer Information
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Lead Classification
    quality: Mapped[str] = mapped_column(String(20), default=LeadQuality.COLD.value, index=True)
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW.value, index=True)
    source: Mapped[str] = mapped_column(String(50), default=LeadSource.INBOUND_CALL.value)
    
    # Preferences (extracted from calls)
    preferred_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    budget_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preferred_size_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preferred_size_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Property Interest
    interested_property_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI-generated summary
    
    # Assignment
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Follow-up
    next_follow_up: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Conversion
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    conversion_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    calls: Mapped[list["Call"]] = relationship("Call", back_populates="lead")

    def __repr__(self) -> str:
        return f"<Lead {self.phone} ({self.quality})>"
