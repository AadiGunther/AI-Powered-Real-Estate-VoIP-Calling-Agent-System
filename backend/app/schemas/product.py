"""Product schemas for solar panel inventory."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.product import ProductType


class ProductBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    model_number: str = Field(..., min_length=2, max_length=100)
    type: ProductType = ProductType.MONOCRYSTALLINE

    wattage: int = Field(..., ge=50, le=1000)
    efficiency: float = Field(..., ge=10.0, le=25.0)

    length_mm: Optional[float] = Field(None, ge=0)
    width_mm: Optional[float] = Field(None, ge=0)
    thickness_mm: Optional[float] = Field(None, ge=0)
    weight_kg: Optional[float] = Field(None, ge=0)

    price_inr: float = Field(..., gt=0)
    warranty_years: int = Field(..., ge=1, le=30)

    manufacturer: str = Field(..., min_length=2, max_length=255)
    manufacturer_country: Optional[str] = Field(None, max_length=100)

    description: Optional[str] = None
    technical_specifications: Optional[str] = None

    images: Optional[list[str]] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    model_number: Optional[str] = Field(None, min_length=2, max_length=100)
    type: Optional[ProductType] = None

    wattage: Optional[int] = Field(None, ge=50, le=1000)
    efficiency: Optional[float] = Field(None, ge=10.0, le=25.0)

    length_mm: Optional[float] = Field(None, ge=0)
    width_mm: Optional[float] = Field(None, ge=0)
    thickness_mm: Optional[float] = Field(None, ge=0)
    weight_kg: Optional[float] = Field(None, ge=0)

    price_inr: Optional[float] = Field(None, gt=0)
    warranty_years: Optional[int] = Field(None, ge=1, le=30)

    manufacturer: Optional[str] = Field(None, min_length=2, max_length=255)
    manufacturer_country: Optional[str] = Field(None, max_length=100)

    description: Optional[str] = None
    technical_specifications: Optional[str] = None

    images: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int

