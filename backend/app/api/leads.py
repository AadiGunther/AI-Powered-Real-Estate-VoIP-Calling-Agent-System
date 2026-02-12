"""Leads API endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadQualityUpdate,
    LeadStatusUpdate,
    LeadAssign,
)
from app.utils.security import get_current_user, require_manager

router = APIRouter()


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    quality: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    assigned_agent_id: Optional[int] = None,
    unassigned: Optional[bool] = None,
    phone: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadListResponse:
    """List leads with optional filters. Agents see assigned and unassigned leads."""
    query = select(Lead)
    
    # Role-based filtering
    if current_user.role == UserRole.AGENT.value:
        query = query.where(
            or_(
                Lead.assigned_agent_id == current_user.id,
                Lead.assigned_agent_id == None,
            )
        )
    elif current_user.role == UserRole.MANAGER.value:
        # Managers see leads assigned to their agents (simplified: see unassigned + own assignments)
        pass  # Can see all for now
    
    # Apply filters
    if quality:
        query = query.where(Lead.quality == quality)
    if status:
        query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    if assigned_agent_id is not None:
        query = query.where(Lead.assigned_agent_id == assigned_agent_id)
    if unassigned:
        query = query.where(Lead.assigned_agent_id == None)
    if phone:
        query = query.where(Lead.phone.contains(phone))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Lead.created_at.desc())
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    request: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    """Create a new lead."""
    # Check if lead with same phone exists
    result = await db.execute(select(Lead).where(Lead.phone == request.phone))
    existing_lead = result.scalar_one_or_none()
    
    if existing_lead:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead with this phone number already exists",
        )
    
    lead = Lead(
        name=request.name,
        phone=request.phone,
        email=request.email,
        source=request.source.value,
        quality=LeadQuality.COLD.value,
        status=LeadStatus.NEW.value,
        preferred_location=request.preferred_location,
        preferred_property_type=request.preferred_property_type,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        notes=request.notes,
    )
    
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    
    return lead


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    """Get lead details by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    
    # Agents can only view their assigned leads
    if current_user.role == UserRole.AGENT.value and lead.assigned_agent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this lead",
        )
    
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    request: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    """Update lead information."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    
    # Agents can only update their assigned leads
    if current_user.role == UserRole.AGENT.value and lead.assigned_agent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this lead",
        )
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    await db.flush()
    await db.refresh(lead)
    
    return lead


@router.put("/{lead_id}/quality", response_model=LeadResponse)
async def update_lead_quality(
    lead_id: int,
    request: LeadQualityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    """Update lead quality classification."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    
    lead.quality = request.quality.value
    await db.flush()
    await db.refresh(lead)
    
    return lead


@router.put("/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: int,
    request: LeadStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    """Update lead lifecycle status."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    
    lead.status = request.status.value
    
    # Mark conversion time if converted
    if request.status == LeadStatus.CONVERTED:
        lead.converted_at = datetime.now(timezone.utc)
    
    await db.flush()
    await db.refresh(lead)
    
    return lead


@router.put("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(
    lead_id: int,
    request: LeadAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Lead:
    """Assign lead to an agent. Requires Manager or Admin role."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    
    # Verify agent exists
    result = await db.execute(select(User).where(User.id == request.agent_id))
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    lead.assigned_agent_id = request.agent_id
    lead.assigned_at = datetime.now(timezone.utc)
    
    await db.flush()
    await db.refresh(lead)
    
    return lead
