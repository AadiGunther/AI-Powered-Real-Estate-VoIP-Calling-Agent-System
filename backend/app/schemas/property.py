"""Property schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.property import PropertyStatus, PropertyType


class PropertyBase(BaseModel):
    """Base property schema."""
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = None
    property_type: PropertyType = PropertyType.APARTMENT
    
    # Location
    address: str = Field(..., min_length=10, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., min_length=5, max_length=10)
    locality: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Pricing
    price: float = Field(..., gt=0)
    price_per_sqft: Optional[float] = Field(None, gt=0)
    maintenance_cost: Optional[float] = Field(None, ge=0)
    negotiable: bool = True
    
    # Size and Configuration
    size_sqft: float = Field(..., gt=0)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    parking_spaces: Optional[int] = Field(None, ge=0)
    floor_number: Optional[int] = None
    total_floors: Optional[int] = Field(None, ge=1)


class PropertyCreate(PropertyBase):
    """Schema for creating a new property."""
    amenities: Optional[List[str]] = None
    images: Optional[List[str]] = None
    status: PropertyStatus = PropertyStatus.AVAILABLE
    is_featured: bool = False


class PropertyUpdate(BaseModel):
    """Schema for updating property information."""
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = None
    property_type: Optional[PropertyType] = None
    
    address: Optional[str] = Field(None, min_length=10, max_length=500)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    pincode: Optional[str] = Field(None, min_length=5, max_length=10)
    locality: Optional[str] = None
    landmark: Optional[str] = None
    
    price: Optional[float] = Field(None, gt=0)
    price_per_sqft: Optional[float] = Field(None, gt=0)
    maintenance_cost: Optional[float] = Field(None, ge=0)
    negotiable: Optional[bool] = None
    
    size_sqft: Optional[float] = Field(None, gt=0)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    parking_spaces: Optional[int] = Field(None, ge=0)
    
    status: Optional[PropertyStatus] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None
    
    amenities: Optional[List[str]] = None
    images: Optional[List[str]] = None


class PropertyResponse(PropertyBase):
    """Property response schema."""
    id: int
    status: str
    is_featured: bool
    is_active: bool
    amenities: Optional[List[str]] = None
    images: Optional[List[str]] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertySearchParams(BaseModel):
    """Property search parameters."""
    city: Optional[str] = None
    locality: Optional[str] = None
    property_type: Optional[PropertyType] = None
    status: Optional[PropertyStatus] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    bedrooms: Optional[int] = None
    is_featured: Optional[bool] = None


class PropertyListResponse(BaseModel):
    """Paginated property list response."""
    properties: List[PropertyResponse]
    total: int
    page: int
    page_size: int
