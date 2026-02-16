"""Leads API endpoints."""

from datetime import datetime, timezone
import json
from typing import Optional, Dict
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.models.call import Call
from app.models.notification import NotificationType
from app.models.audit_log import AuditLog, AuditAction
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadQualityUpdate,
    LeadStatusUpdate,
    LeadAssign,
    LeadBulkAssign,
)
from app.services.notification_service import NotificationService
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

    lead_ids = [lead.id for lead in leads]
    last_call_notes_map: Dict[int, Optional[str]] = {}
    if lead_ids:
        calls_query = (
            select(Call.lead_id, Call.outcome_notes)
            .where(Call.lead_id.in_(lead_ids))
            .order_by(Call.lead_id, Call.created_at.desc())
        )
        calls_result = await db.execute(calls_query)
        for lead_id, outcome_notes in calls_result.all():
            if lead_id not in last_call_notes_map:
                last_call_notes_map[lead_id] = outcome_notes
    
    lead_responses: list[LeadResponse] = []
    for lead in leads:
        response = LeadResponse.model_validate(lead)
        response.last_call_notes = last_call_notes_map.get(lead.id)
        lead_responses.append(response)
    
    return LeadListResponse(
        leads=lead_responses,
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

    notification_service = NotificationService(db)
    result_users = await db.execute(
        select(User).where(
            User.role.in_([UserRole.ADMIN.value, UserRole.MANAGER.value])
        )
    )
    managers = result_users.scalars().all()
    for manager in managers:
        await notification_service.create_notification(
            user_id=manager.id,
            message=f"New lead created with phone {lead.phone}",
            notification_type=NotificationType.LEAD_CREATED,
            related_lead_id=lead.id,
        )

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

    old_status = lead.status
    lead.status = request.status.value
    
    # Mark conversion time if converted
    if request.status == LeadStatus.CONVERTED:
        lead.converted_at = datetime.now(ZoneInfo("Asia/Kolkata"))

    await db.flush()
    await db.refresh(lead)

    if lead.assigned_agent_id is not None and old_status != lead.status:
        notification_service = NotificationService(db)
        await notification_service.create_notification(
            user_id=lead.assigned_agent_id,
            message=(
                f"Lead {lead.phone} status changed from "
                f"{old_status} to {lead.status}"
            ),
            notification_type=NotificationType.LEAD_STATUS_CHANGED,
            related_lead_id=lead.id,
        )

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
    
    result = await db.execute(select(User).where(User.id == request.agent_id))
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign leads to inactive agents",
        )

    if agent.role != UserRole.AGENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only assign leads to agents",
        )

    if lead.assigned_agent_id == request.agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead is already assigned to this agent",
        )

    previous_agent_id = lead.assigned_agent_id
    lead.assigned_agent_id = request.agent_id
    lead.assigned_at = datetime.now(ZoneInfo("Asia/Kolkata"))

    await db.flush()
    await db.refresh(lead)

    notification_service = NotificationService(db)
    await notification_service.create_notification(
        user_id=agent.id,
        message=f"You have been assigned lead {lead.phone}",
        notification_type=NotificationType.LEAD_ASSIGNED,
        related_lead_id=lead.id,
    )

    audit_payload = json.dumps(
        {
            "previous_agent_id": previous_agent_id,
            "new_agent_id": request.agent_id,
        }
    )
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.LEAD_ASSIGNED.value,
        entity_type="lead",
        entity_id=lead.id,
        payload=audit_payload,
    )
    db.add(audit)

    return lead


@router.put("/assign/bulk", response_model=LeadListResponse)
async def bulk_assign_leads(
    request: LeadBulkAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> LeadListResponse:
    result = await db.execute(select(User).where(User.id == request.agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign leads to inactive agents",
        )

    if agent.role != UserRole.AGENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only assign leads to agents",
        )

    if not request.lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leads provided for assignment",
        )

    result = await db.execute(select(Lead).where(Lead.id.in_(request.lead_ids)))
    leads = result.scalars().all()

    found_ids = {lead.id for lead in leads}
    requested_ids = set(request.lead_ids)
    missing_ids = requested_ids - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leads not found: {sorted(missing_ids)}",
        )

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    notification_service = NotificationService(db)

    for lead in leads:
        if lead.assigned_agent_id == request.agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead {lead.id} is already assigned to this agent",
            )

    for lead in leads:
        previous_agent_id = lead.assigned_agent_id
        lead.assigned_agent_id = request.agent_id
        lead.assigned_at = now

        await notification_service.create_notification(
            user_id=agent.id,
            message=f"You have been assigned lead {lead.phone}",
            notification_type=NotificationType.LEAD_ASSIGNED,
            related_lead_id=lead.id,
        )

        audit_payload = json.dumps(
            {
                "previous_agent_id": previous_agent_id,
                "new_agent_id": request.agent_id,
            }
        )
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.LEAD_ASSIGNED.value,
            entity_type="lead",
            entity_id=lead.id,
            payload=audit_payload,
        )
        db.add(audit)

    await db.flush()

    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=len(leads),
        page=1,
        page_size=len(leads),
    )
