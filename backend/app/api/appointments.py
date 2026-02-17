from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.appointment import Appointment
from app.models.lead import Lead
from app.models.user import User, UserRole
from app.schemas.appointment import (
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdate,
    AppointmentRescheduleRequest,
)
from app.utils.security import get_current_user

router = APIRouter()


def _appointment_to_response(
    appointment: Appointment,
    lead: Optional[Lead],
    staff: Optional[User],
) -> AppointmentResponse:
    client_name = lead.name if lead else None
    contact_phone = lead.phone if lead else None
    contact_email = lead.email if lead else None
    assigned_staff_id = lead.assigned_agent_id if lead else None
    assigned_staff_name = staff.full_name if staff else None

    return AppointmentResponse(
        id=appointment.id,
        call_id=appointment.call_id,
        lead_id=appointment.lead_id,
        scheduled_for=appointment.scheduled_for,
        address=appointment.address,
        notes=appointment.notes,
        status=appointment.status,
        client_name=client_name,
        duration_minutes=60,
        assigned_staff_id=assigned_staff_id,
        assigned_staff_name=assigned_staff_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


@router.get("/", response_model=AppointmentListResponse)
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    staff_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = Query("scheduled_for"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentListResponse:
    appt_query = (
        select(Appointment, Lead, User)
        .join(Lead, Lead.id == Appointment.lead_id)
        .outerjoin(User, User.id == Lead.assigned_agent_id)
    )

    if current_user.role == UserRole.AGENT.value:
        appt_query = appt_query.where(Lead.assigned_agent_id == current_user.id)

    filters = []
    if date_from:
        filters.append(Appointment.scheduled_for >= date_from)
    if date_to:
        filters.append(Appointment.scheduled_for <= date_to)
    if status_filter:
        filters.append(Appointment.status == status_filter)
    if staff_id is not None:
        filters.append(Lead.assigned_agent_id == staff_id)
    if search:
        s = f"%{search.strip()}%"
        filters.append(
            or_(
                Lead.name.ilike(s),
                Lead.phone.ilike(s),
                Lead.email.ilike(s),
                Appointment.address.ilike(s),
                Appointment.notes.ilike(s),
            )
        )
    if filters:
        appt_query = appt_query.where(and_(*filters))

    count_query = (
        select(func.count())
        .select_from(Appointment)
        .join(Lead, Lead.id == Appointment.lead_id)
    )
    if current_user.role == UserRole.AGENT.value:
        count_query = count_query.where(Lead.assigned_agent_id == current_user.id)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = (await db.execute(count_query)).scalar() or 0

    sort_columns = {
        "scheduled_for": Appointment.scheduled_for,
        "status": Appointment.status,
        "client_name": Lead.name,
        "staff": User.full_name,
        "created_at": Appointment.created_at,
    }
    sort_col = sort_columns.get(sort_by, Appointment.scheduled_for)
    sort_expr = asc(sort_col) if sort_order.lower() == "asc" else desc(sort_col)
    appt_query = appt_query.order_by(sort_expr)

    appt_query = appt_query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(appt_query)
    rows = result.all()

    appointments: List[AppointmentResponse] = []
    for appt, lead, staff in rows:
        appointments.append(_appointment_to_response(appt, lead, staff))

    return AppointmentListResponse(
        appointments=appointments,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentResponse:
    query = (
        select(Appointment, Lead, User)
        .join(Lead, Lead.id == Appointment.lead_id)
        .outerjoin(User, User.id == Lead.assigned_agent_id)
        .where(Appointment.id == appointment_id)
    )
    if current_user.role == UserRole.AGENT.value:
        query = query.where(Lead.assigned_agent_id == current_user.id)

    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    appointment, lead, staff = row
    return _appointment_to_response(appointment, lead, staff)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentResponse:
    query = (
        select(Appointment, Lead)
        .join(Lead, Lead.id == Appointment.lead_id)
        .where(Appointment.id == appointment_id)
    )
    if current_user.role == UserRole.AGENT.value:
        query = query.where(Lead.assigned_agent_id == current_user.id)

    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    appointment, lead = row

    update_data = payload.model_dump(exclude_unset=True)
    assigned_staff_id = update_data.pop("assigned_staff_id", None)

    for field, value in update_data.items():
        setattr(appointment, field, value)

    if assigned_staff_id is not None:
        if current_user.role not in {UserRole.ADMIN.value, UserRole.MANAGER.value}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only managers can reassign staff.")
        lead.assigned_agent_id = assigned_staff_id

    await db.flush()

    staff = None
    if lead.assigned_agent_id:
        staff_result = await db.execute(select(User).where(User.id == lead.assigned_agent_id))
        staff = staff_result.scalar_one_or_none()

    await db.refresh(appointment)
    await db.refresh(lead)

    return _appointment_to_response(appointment, lead, staff)


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentResponse:
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    lead_result = await db.execute(select(Lead).where(Lead.id == appointment.lead_id))
    lead = lead_result.scalar_one_or_none()
    if current_user.role == UserRole.AGENT.value and (not lead or lead.assigned_agent_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this appointment")

    appointment.status = "cancelled"
    await db.flush()
    await db.refresh(appointment)

    staff = None
    if lead and lead.assigned_agent_id:
        staff_result = await db.execute(select(User).where(User.id == lead.assigned_agent_id))
        staff = staff_result.scalar_one_or_none()

    return _appointment_to_response(appointment, lead, staff)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentResponse:
    query = (
        select(Appointment, Lead)
        .join(Lead, Lead.id == Appointment.lead_id)
        .where(Appointment.id == appointment_id)
    )
    if current_user.role == UserRole.AGENT.value:
        query = query.where(Lead.assigned_agent_id == current_user.id)

    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    appointment, lead = row
    appointment.scheduled_for = payload.scheduled_for
    appointment.status = "scheduled"

    await db.flush()
    await db.refresh(appointment)

    staff = None
    if lead.assigned_agent_id:
        staff_result = await db.execute(select(User).where(User.id == lead.assigned_agent_id))
        staff = staff_result.scalar_one_or_none()

    return _appointment_to_response(appointment, lead, staff)

