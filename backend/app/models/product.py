"""Product model for solar panel inventory."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductType(str, Enum):
    MONOCRYSTALLINE = "monocrystalline"
    POLYCRYSTALLINE = "polycrystalline"
    THIN_FILM = "thin_film"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProductType.MONOCRYSTALLINE.value,
    )

    wattage: Mapped[int] = mapped_column(Integer, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, nullable=False)

    length_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thickness_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    price_inr: Mapped[float] = mapped_column(Float, nullable=False)
    warranty_years: Mapped[int] = mapped_column(Integer, nullable=False)

    manufacturer: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_specifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Product {self.name} ({self.model_number})>"
