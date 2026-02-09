"""Property model for real estate listings."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PropertyType(str, Enum):
    """Property type enumeration."""
    APARTMENT = "apartment"
    VILLA = "villa"
    PLOT = "plot"
    COMMERCIAL = "commercial"
    OFFICE = "office"
    WAREHOUSE = "warehouse"


class PropertyStatus(str, Enum):
    """Property availability status."""
    AVAILABLE = "available"
    SOLD = "sold"
    RESERVED = "reserved"
    UNDER_CONSTRUCTION = "under_construction"


class Property(Base):
    """Property model for real estate listings."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Basic Information
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    property_type: Mapped[str] = mapped_column(String(50), default=PropertyType.APARTMENT.value)
    
    # Location
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    locality: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    landmark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Pricing
    price: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    price_per_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    maintenance_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Size and Configuration
    size_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parking_spaces: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Features (stored as JSON string for SQLite compatibility)
    amenities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=PropertyStatus.AVAILABLE.value, index=True
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Images (stored as JSON array of URLs)
    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Ownership
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)  # User ID
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Property {self.title} ({self.city})>"
