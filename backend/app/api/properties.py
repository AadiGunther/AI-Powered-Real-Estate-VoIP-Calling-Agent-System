"""Properties API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.property import Property
from app.models.user import User
from app.schemas.property import (
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdate,
)
from app.utils.security import require_manager

router = APIRouter()


def property_to_response(prop: Property) -> PropertyResponse:
    """Convert Property model to response schema."""
    amenities = json.loads(prop.amenities) if prop.amenities else None
    images = json.loads(prop.images) if prop.images else None
    
    return PropertyResponse(
        id=prop.id,
        title=prop.title,
        description=prop.description,
        property_type=prop.property_type,
        address=prop.address,
        city=prop.city,
        state=prop.state,
        pincode=prop.pincode,
        locality=prop.locality,
        landmark=prop.landmark,
        latitude=prop.latitude,
        longitude=prop.longitude,
        price=prop.price,
        price_per_sqft=prop.price_per_sqft,
        maintenance_cost=prop.maintenance_cost,
        negotiable=prop.negotiable,
        size_sqft=prop.size_sqft,
        bedrooms=prop.bedrooms,
        bathrooms=prop.bathrooms,
        parking_spaces=prop.parking_spaces,
        floor_number=prop.floor_number,
        total_floors=prop.total_floors,
        status=prop.status,
        is_featured=prop.is_featured,
        is_active=prop.is_active,
        amenities=amenities,
        images=images,
        created_by=prop.created_by,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
    )


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    locality: Optional[str] = None,
    property_type: Optional[str] = None,
    status: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    is_featured: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
) -> PropertyListResponse:
    """List properties with optional filters."""
    # Build query
    query = select(Property).where(Property.is_active.is_(True))

    # Apply filters
    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
    if locality:
        query = query.where(Property.locality.ilike(f"%{locality}%"))
    if property_type:
        query = query.where(Property.property_type == property_type)
    if status:
        query = query.where(Property.status == status)
    if min_price is not None:
        query = query.where(Property.price >= min_price)
    if max_price is not None:
        query = query.where(Property.price <= max_price)
    if bedrooms is not None:
        query = query.where(Property.bedrooms == bedrooms)
    if is_featured is not None:
        query = query.where(Property.is_featured == is_featured)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Property.created_at.desc())
    
    result = await db.execute(query)
    properties = result.scalars().all()
    
    return PropertyListResponse(
        properties=[property_to_response(p) for p in properties],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    request: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> PropertyResponse:
    """Create a new property listing. Requires Manager or Admin role."""
    property_data = Property(
        title=request.title,
        description=request.description,
        property_type=request.property_type.value,
        address=request.address,
        city=request.city,
        state=request.state,
        pincode=request.pincode,
        locality=request.locality,
        landmark=request.landmark,
        latitude=request.latitude,
        longitude=request.longitude,
        price=request.price,
        price_per_sqft=request.price_per_sqft,
        maintenance_cost=request.maintenance_cost,
        negotiable=request.negotiable,
        size_sqft=request.size_sqft,
        bedrooms=request.bedrooms,
        bathrooms=request.bathrooms,
        parking_spaces=request.parking_spaces,
        floor_number=request.floor_number,
        total_floors=request.total_floors,
        status=request.status.value,
        is_featured=request.is_featured,
        is_active=True,
        amenities=json.dumps(request.amenities) if request.amenities else None,
        images=json.dumps(request.images) if request.images else None,
        created_by=current_user.id,
    )
    
    db.add(property_data)
    await db.flush()
    await db.refresh(property_data)
    
    return property_to_response(property_data)


@router.get("/search", response_model=PropertyListResponse)
async def search_properties(
    q: str = Query(..., min_length=2, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PropertyListResponse:
    """Search properties by location, title, or description."""
    search_term = f"%{q}%"
    
    query = select(Property).where(
        and_(
            Property.is_active.is_(True),
            or_(
                Property.title.ilike(search_term),
                Property.city.ilike(search_term),
                Property.locality.ilike(search_term),
                Property.address.ilike(search_term),
                Property.landmark.ilike(search_term),
            )
        )
    )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Property.is_featured.desc(), Property.created_at.desc())
    
    result = await db.execute(query)
    properties = result.scalars().all()
    
    return PropertyListResponse(
        properties=[property_to_response(p) for p in properties],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
) -> PropertyResponse:
    """Get property details by ID."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    property_data = result.scalar_one_or_none()
    
    if not property_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    return property_to_response(property_data)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    request: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> PropertyResponse:
    """Update property details. Requires Manager or Admin role."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    property_data = result.scalar_one_or_none()
    
    if not property_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "amenities" and value is not None:
            value = json.dumps(value)
        elif field == "images" and value is not None:
            value = json.dumps(value)
        elif field == "property_type" and value is not None:
            value = value.value
        elif field == "status" and value is not None:
            value = value.value
        setattr(property_data, field, value)
    
    await db.flush()
    await db.refresh(property_data)
    
    return property_to_response(property_data)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> None:
    """Soft delete a property. Requires Manager or Admin role."""
    result = await db.execute(select(Property).where(Property.id == property_id))
    property_data = result.scalar_one_or_none()
    
    if not property_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )
    
    property_data.is_active = False
    await db.flush()
