"""API endpoints for dashboard statistics and metrics."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, and_, case

from app.database import async_session_maker
from app.models.call import Call, CallStatus, CallOutcome
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.models.property import Property
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = get_logger("api.dashboard")


class DashboardStats(BaseModel):
    """Dashboard statistics response."""
    total_calls_today: int
    total_calls_week: int
    total_calls_month: int
    active_calls: int
    total_leads: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    total_properties: int
    available_properties: int
    conversion_rate: float


class RecentCallResponse(BaseModel):
    """Recent call response model."""
    id: int
    call_sid: str
    from_number: str
    status: str
    duration_seconds: Optional[int]
    handled_by_ai: bool
    transcript_summary: Optional[str]
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def force_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class AgentPerformance(BaseModel):
    """Agent performance metrics."""
    agent_id: int
    agent_name: str
    total_calls: int
    answered_calls: int
    average_duration: float
    leads_assigned: int


class ChartDataPoint(BaseModel):
    """Chart data point."""
    name: str
    calls: int
    leads: int


@router.get("/charts", response_model=List[ChartDataPoint])
async def get_dashboard_charts():
    """Get chart data for the last 7 days."""
    try:
        async with async_session_maker() as db:
            now = datetime.utcnow()
            days = []
            data = []
            
            # Generate last 7 days
            for i in range(6, -1, -1):
                date = now - timedelta(days=i)
                days.append(date.date())
                
            for day in days:
                # Count calls for this day
                # SQLite-specific date handling
                calls_count = await db.scalar(
                    select(func.count(Call.id)).where(
                        func.date(Call.created_at) == day.isoformat()
                    )
                )
                
                # Count leads for this day
                leads_count = await db.scalar(
                    select(func.count(Lead.id)).where(
                        func.date(Lead.created_at) == day.isoformat()
                    )
                )
                
                data.append(
                    ChartDataPoint(
                        name=day.strftime("%a"), # Mon, Tue, etc.
                        calls=calls_count or 0,
                        leads=leads_count or 0
                    )
                )
            
            return data
    except Exception as e:
        logger.error("get_charts_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get overall dashboard statistics."""
    try:
        async with async_session_maker() as db:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=now.weekday())
            month_start = today_start.replace(day=1)
            
            # Calls stats
            calls_today = await db.scalar(
                select(func.count(Call.id)).where(Call.created_at >= today_start)
            )
            calls_week = await db.scalar(
                select(func.count(Call.id)).where(Call.created_at >= week_start)
            )
            calls_month = await db.scalar(
                select(func.count(Call.id)).where(Call.created_at >= month_start)
            )
            active_calls = await db.scalar(
                select(func.count(Call.id)).where(Call.status == CallStatus.IN_PROGRESS.value)
            )
            
            # Leads stats
            total_leads = await db.scalar(select(func.count(Lead.id)))
            hot_leads = await db.scalar(
                select(func.count(Lead.id)).where(Lead.quality == LeadQuality.HOT.value)
            )
            warm_leads = await db.scalar(
                select(func.count(Lead.id)).where(Lead.quality == LeadQuality.WARM.value)
            )
            cold_leads = await db.scalar(
                select(func.count(Lead.id)).where(Lead.quality == LeadQuality.COLD.value)
            )
            
            # Properties stats
            total_properties = await db.scalar(select(func.count(Property.id)))
            available_properties = await db.scalar(
                select(func.count(Property.id)).where(Property.status == "available")
            )
            
            # Conversion rate (converted leads / total leads)
            converted_leads = await db.scalar(
                select(func.count(Lead.id)).where(Lead.status == LeadStatus.CONVERTED.value)
            )
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0
            
            return DashboardStats(
                total_calls_today=calls_today or 0,
                total_calls_week=calls_week or 0,
                total_calls_month=calls_month or 0,
                active_calls=active_calls or 0,
                total_leads=total_leads or 0,
                hot_leads=hot_leads or 0,
                warm_leads=warm_leads or 0,
                cold_leads=cold_leads or 0,
                total_properties=total_properties or 0,
                available_properties=available_properties or 0,
                conversion_rate=round(conversion_rate, 2),
            )
    except Exception as e:
        logger.error("get_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-calls", response_model=List[RecentCallResponse])
async def get_recent_calls(limit: int = Query(10, le=50)):
    """Get recent call activity."""
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Call)
                .order_by(Call.created_at.desc())
                .limit(limit)
            )
            calls = result.scalars().all()
            
            return [
                RecentCallResponse(
                    id=call.id,
                    call_sid=call.call_sid,
                    from_number=call.from_number,
                    status=call.status,
                    duration_seconds=call.duration_seconds,
                    handled_by_ai=call.handled_by_ai,
                    transcript_summary=call.transcript_summary,
                    created_at=call.created_at,
                )
                for call in calls
            ]
    except Exception as e:
        logger.error("get_recent_calls_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


class PendingFollowUp(BaseModel):
    """Pending follow-up lead."""
    id: int
    name: Optional[str]
    phone: str
    quality: str
    last_contact: Optional[datetime]
    notes: Optional[str]

    @field_validator("last_contact", mode="after")
    @classmethod
    def force_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


@router.get("/pending-followups", response_model=List[PendingFollowUp])
async def get_pending_followups(limit: int = Query(5, le=20)):
    """Get all leads needing attention (Hot/Warm or New/Contacted)."""
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Lead)
                .where(
                    Lead.status.in_([
                        LeadStatus.NEW.value, 
                        LeadStatus.CONTACTED.value,
                        LeadStatus.QUALIFIED.value
                    ])
                )
                .order_by(
                    # Prioritize Hot > Warm > Cold, then by recency
                    case(
                        (Lead.quality == LeadQuality.HOT.value, 1),
                        (Lead.quality == LeadQuality.WARM.value, 2),
                        (Lead.quality == LeadQuality.COLD.value, 3),
                        else_=4
                    ),
                    Lead.updated_at.desc()
                )
                .limit(limit)
            )
            leads = result.scalars().all()
            
            return [
                PendingFollowUp(
                    id=lead.id,
                    name=lead.name,
                    phone=lead.phone,
                    quality=lead.quality,
                    last_contact=lead.updated_at,
                    notes=lead.ai_summary or lead.notes
                )
                for lead in leads
            ]
    except Exception as e:
        logger.error("get_pending_followups_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-performance", response_model=List[AgentPerformance])
async def get_agent_performance():
    """Get agent performance metrics."""
    try:
        async with async_session_maker() as db:
            # Get agents who have assigned leads
            from app.models.user import User
            result = await db.execute(
                select(User,func.count(Lead.id).label("leads_count"))
                .outerjoin(Lead, User.id == Lead.assigned_agent_id)
                .group_by(User.id)
            )
            
            agents_data = result.all()
            
            performance = []
            for user, leads_count in agents_data:
                # Get call stats for this agent (through their assigned leads)
                calls_result = await db.execute(
                    select(
                        func.count(Call.id).label("total_calls"),
                        func.avg(Call.duration_seconds).label("avg_duration")
                    )
                    .join(Lead, Call.lead_id == Lead.id)
                    .where(Lead.assigned_agent_id == user.id)
                )
                call_stats = calls_result.one_or_none()
                
                total_calls = call_stats.total_calls if call_stats else 0
                avg_duration = call_stats.avg_duration if call_stats and call_stats.avg_duration else 0
                
                performance.append(
                    AgentPerformance(
                        agent_id=user.id,
                        agent_name=user.full_name or user.email,
                        total_calls=total_calls or 0,
                        answered_calls=total_calls or 0,  # Simplified
                        average_duration=round(avg_duration, 2),
                        leads_assigned=leads_count or 0,
                    )
                )
            
            return performance
    except Exception as e:
        logger.error("get_agent_performance_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
