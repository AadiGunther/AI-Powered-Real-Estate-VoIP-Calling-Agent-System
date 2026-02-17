"""Leads API endpoints."""

from datetime import datetime, timezone, timedelta
import json
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

import anyio
from openai import OpenAI, AzureOpenAI

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.models.call import Call
from app.models.appointment import Appointment
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
    LeadAiSummaryResponse,
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
    """List leads with optional filters. Agents see only their assigned leads."""
    query = select(Lead)
    
    # Role-based filtering
    if current_user.role == UserRole.AGENT.value:
        query = query.where(Lead.assigned_agent_id == current_user.id)
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

    for lead in leads:
        await db.refresh(lead)

    return LeadListResponse(
        leads=[LeadResponse.model_validate(lead) for lead in leads],
        total=len(leads),
        page=1,
        page_size=len(leads),
    )


def _clamp_int(value: float, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(round(value))))


def _build_heuristic_ai_summary(lead: Lead, calls: List[Call], has_future_appointment: bool) -> LeadAiSummaryResponse:
    base_score_map = {
        LeadQuality.COLD.value: 30,
        LeadQuality.WARM.value: 60,
        LeadQuality.HOT.value: 85,
    }
    score = float(base_score_map.get(lead.quality, 40))

    status_boost = {
        LeadStatus.NEW.value: 0,
        LeadStatus.CONTACTED.value: 5,
        LeadStatus.QUALIFIED.value: 12,
        LeadStatus.NEGOTIATING.value: 18,
        LeadStatus.CONVERTED.value: 35,
        LeadStatus.LOST.value: -25,
    }
    score += float(status_boost.get(lead.status, 0))

    if lead.last_contacted_at:
        days = (datetime.now(timezone.utc) - lead.last_contacted_at).days
        if days <= 2:
            score += 6
        elif days <= 7:
            score += 3
        elif days >= 30:
            score -= 6

    recent_calls = calls[:5]
    sentiment_values = [c.sentiment_score for c in recent_calls if c.sentiment_score is not None]
    satisfaction_values = [c.customer_satisfaction for c in recent_calls if c.customer_satisfaction is not None]
    if sentiment_values:
        score += float(sum(sentiment_values) / len(sentiment_values)) * 10.0
    if satisfaction_values:
        score += (float(sum(satisfaction_values) / len(satisfaction_values)) - 3.0) * 4.0

    if has_future_appointment:
        score += 10

    lead_quality_score = _clamp_int(score, 0, 100)
    likelihood_to_convert = _clamp_int(lead_quality_score * 0.95 + (5 if has_future_appointment else 0), 0, 100)

    engagement_level = "low"
    if len(recent_calls) >= 2 or lead.follow_up_count >= 2:
        engagement_level = "medium"
    if lead_quality_score >= 70 or (sentiment_values and sum(sentiment_values) / len(sentiment_values) > 0.25):
        engagement_level = "high"

    recommended_next_actions: List[str] = []
    if lead.status in {LeadStatus.NEW.value, LeadStatus.CONTACTED.value}:
        recommended_next_actions.append("Call within 24 hours and confirm needs.")
    if lead.status in {LeadStatus.QUALIFIED.value, LeadStatus.NEGOTIATING.value} and not has_future_appointment:
        recommended_next_actions.append("Propose a site visit and share 2–3 matching options.")
    if has_future_appointment:
        recommended_next_actions.append("Confirm appointment details and send location/address.")
    if lead.status == LeadStatus.LOST.value:
        recommended_next_actions.append("Mark reason for loss and set a re-engagement reminder.")
    if not recommended_next_actions:
        recommended_next_actions.append("Review recent interactions and plan the next touchpoint.")

    key_conversation_points: List[str] = []
    for c in recent_calls:
        if c.transcript_summary:
            chunks = [p.strip() for p in c.transcript_summary.split(".") if p.strip()]
            for chunk in chunks[:2]:
                if chunk not in key_conversation_points:
                    key_conversation_points.append(chunk)
        if len(key_conversation_points) >= 5:
            break
    if not key_conversation_points:
        if lead.preferred_location:
            key_conversation_points.append(f"Preferred location: {lead.preferred_location}")
        if lead.budget_max:
            key_conversation_points.append(f"Budget up to: ₹{lead.budget_max}")

    patterns: List[str] = []
    if len(recent_calls) >= 3:
        patterns.append("Multiple touchpoints recorded; follow up consistency matters.")
    if sentiment_values and sum(sentiment_values) / len(sentiment_values) < -0.2:
        patterns.append("Negative sentiment trend; address objections directly.")
    if lead.follow_up_count >= 3:
        patterns.append("High follow-up count; consider escalation or alternative channel.")
    if not patterns:
        patterns.append("No strong patterns detected yet.")

    return LeadAiSummaryResponse(
        lead_id=lead.id,
        lead_quality_score=lead_quality_score,
        engagement_level=engagement_level,
        likelihood_to_convert=likelihood_to_convert,
        recommended_next_actions=recommended_next_actions,
        key_conversation_points=key_conversation_points,
        patterns=patterns,
        generated_at=datetime.now(ZoneInfo("Asia/Kolkata")),
        source_call_ids=[c.id for c in recent_calls],
    )


def _try_build_openai_client() -> Optional[tuple[Any, str]]:
    if (
        settings.azure_openai_api_key
        and settings.azure_openai_endpoint
        and settings.azure_openai_deployment
        and settings.azure_openai_api_version
    ):
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        return client, settings.azure_openai_deployment

    if settings.openai_api_key:
        client = OpenAI(api_key=settings.openai_api_key)
        return client, "gpt-4o-mini"

    return None


async def _generate_ai_summary_via_llm(lead: Lead, calls: List[Call], has_future_appointment: bool) -> Optional[LeadAiSummaryResponse]:
    client_and_model = _try_build_openai_client()
    if not client_and_model:
        return None

    client, model = client_and_model

    call_payload = []
    for c in calls[:5]:
        call_payload.append(
            {
                "id": c.id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "direction": c.direction,
                "status": c.status,
                "outcome": c.outcome,
                "outcome_notes": c.outcome_notes,
                "sentiment_score": c.sentiment_score,
                "customer_satisfaction": c.customer_satisfaction,
                "transcript_summary": c.transcript_summary,
            }
        )

    system_text = (
        "You generate concise, actionable lead insights for a sales CRM. "
        "Return ONLY valid JSON. Do not include markdown."
    )

    user_text = json.dumps(
        {
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "quality": lead.quality,
                "status": lead.status,
                "source": lead.source,
                "preferred_location": lead.preferred_location,
                "preferred_property_type": lead.preferred_property_type,
                "budget_min": lead.budget_min,
                "budget_max": lead.budget_max,
                "follow_up_count": lead.follow_up_count,
                "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            },
            "recent_calls": call_payload,
            "has_future_appointment": has_future_appointment,
            "required_output_schema": {
                "lead_quality_score": "integer 0-100",
                "engagement_level": "one of: low, medium, high",
                "likelihood_to_convert": "integer 0-100",
                "recommended_next_actions": "array of strings",
                "key_conversation_points": "array of strings",
                "patterns": "array of strings",
            },
        },
        ensure_ascii=False,
    )

    def _call_openai() -> LeadAiSummaryResponse:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return LeadAiSummaryResponse(
            lead_id=lead.id,
            lead_quality_score=_clamp_int(parsed.get("lead_quality_score", 50), 0, 100),
            engagement_level=str(parsed.get("engagement_level", "medium")),
            likelihood_to_convert=_clamp_int(parsed.get("likelihood_to_convert", 50), 0, 100),
            recommended_next_actions=[str(x) for x in (parsed.get("recommended_next_actions") or [])],
            key_conversation_points=[str(x) for x in (parsed.get("key_conversation_points") or [])],
            patterns=[str(x) for x in (parsed.get("patterns") or [])],
            generated_at=datetime.now(ZoneInfo("Asia/Kolkata")),
            source_call_ids=[c.id for c in calls[:5]],
        )

    try:
        return await anyio.to_thread.run_sync(_call_openai)
    except Exception:
        return None


@router.get("/{lead_id}/ai-summary", response_model=LeadAiSummaryResponse)
async def get_lead_ai_summary(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadAiSummaryResponse:
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    if current_user.role == UserRole.AGENT.value and lead.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this lead")

    calls_result = await db.execute(
        select(Call)
        .where(Call.lead_id == lead.id)
        .order_by(Call.created_at.desc())
        .limit(5)
    )
    calls = list(calls_result.scalars().all())

    now_utc = datetime.now(timezone.utc)
    appointment_result = await db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            and_(
                Appointment.lead_id == lead.id,
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.scheduled_for >= now_utc - timedelta(minutes=1),
            )
        )
    )
    has_future_appointment = (appointment_result.scalar() or 0) > 0

    llm_summary = await _generate_ai_summary_via_llm(lead, calls, has_future_appointment)
    if llm_summary:
        return llm_summary

    return _build_heuristic_ai_summary(lead, calls, has_future_appointment)
