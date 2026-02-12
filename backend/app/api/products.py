"""Products API endpoints for solar panel inventory."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.product import Product, ProductType
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)
from app.utils.security import get_current_user, require_manager

router = APIRouter()


def product_to_response(product: Product) -> ProductResponse:
    images = json.loads(product.images) if product.images else None

    return ProductResponse(
        id=product.id,
        name=product.name,
        model_number=product.model_number,
        type=ProductType(product.type),
        wattage=product.wattage,
        efficiency=product.efficiency,
        length_mm=product.length_mm,
        width_mm=product.width_mm,
        thickness_mm=product.thickness_mm,
        weight_kg=product.weight_kg,
        price_inr=product.price_inr,
        warranty_years=product.warranty_years,
        manufacturer=product.manufacturer,
        manufacturer_country=product.manufacturer_country,
        description=product.description,
        technical_specifications=product.technical_specifications,
        images=images,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: Optional[ProductType] = None,
    min_wattage: Optional[int] = None,
    max_wattage: Optional[int] = None,
    manufacturer: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductListResponse:
    query = select(Product).where(Product.is_active == True)

    if type is not None:
        query = query.where(Product.type == type.value)
    if min_wattage is not None:
        query = query.where(Product.wattage >= min_wattage)
    if max_wattage is not None:
        query = query.where(Product.wattage <= max_wattage)
    if manufacturer:
        query = query.where(Product.manufacturer.ilike(f"%{manufacturer}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Product.wattage.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    products = result.scalars().all()

    return ProductListResponse(
        products=[product_to_response(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> ProductResponse:
    images_json = json.dumps(request.images) if request.images else None

    product = Product(
        name=request.name,
        model_number=request.model_number,
        type=request.type.value,
        wattage=request.wattage,
        efficiency=request.efficiency,
        length_mm=request.length_mm,
        width_mm=request.width_mm,
        thickness_mm=request.thickness_mm,
        weight_kg=request.weight_kg,
        price_inr=request.price_inr,
        warranty_years=request.warranty_years,
        manufacturer=request.manufacturer,
        manufacturer_country=request.manufacturer_country,
        description=request.description,
        technical_specifications=request.technical_specifications,
        images=images_json,
        is_active=True,
    )

    db.add(product)
    await db.flush()
    await db.refresh(product)

    return product_to_response(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.is_active == True))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product_to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    request: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    update_data = request.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "images" and value is not None:
            value = json.dumps(value)
        elif field == "type" and value is not None:
            value = value.value
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)

    return product_to_response(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    product.is_active = False
    await db.flush()


@router.post("/upload-image", response_model=dict)
async def upload_product_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_manager),
) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed",
        )

    upload_dir = settings.recordings_dir

    filename = f"product_{file.filename}"
    path = f"{upload_dir}/{filename}"

    contents = await file.read()

    with open(path, "wb") as f:
        f.write(contents)

    return {"url": f"/static/{filename}"}

