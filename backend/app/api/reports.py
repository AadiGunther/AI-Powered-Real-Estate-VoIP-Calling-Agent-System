"""Reports API endpoints."""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.call import Call, CallOutcome, CallStatus
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.models.product import Product
from app.models.user import User, UserRole
from app.utils.security import get_current_user, require_manager

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get dashboard summary statistics."""
    today = datetime.now(ZoneInfo("Asia/Kolkata")).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_ago = today - timedelta(days=7)
    
    # Total calls today
    calls_today = await db.execute(
        select(func.count(Call.id)).where(Call.created_at >= today)
    )
    
    # Total calls this week
    calls_week = await db.execute(
        select(func.count(Call.id)).where(Call.created_at >= week_ago)
    )
    
    # Total leads
    total_leads = await db.execute(select(func.count(Lead.id)))
    hot_leads = await db.execute(
        select(func.count(Lead.id)).where(Lead.quality == LeadQuality.HOT.value)
    )
    
    # Active products
    active_products = await db.execute(
        select(func.count(Product.id)).where(Product.is_active.is_(True))
    )
    
    # Conversion rate (leads converted / total leads)
    converted_leads = await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.CONVERTED.value)
    )
    
    total_leads_count = total_leads.scalar() or 0
    converted_count = converted_leads.scalar() or 0
    conversion_rate = (converted_count / total_leads_count * 100) if total_leads_count > 0 else 0
    
    # Average call duration
    avg_duration = await db.execute(
        select(func.avg(Call.duration_seconds)).where(Call.duration_seconds.is_not(None))
    )
    
    return {
        "calls": {
            "today": calls_today.scalar() or 0,
            "this_week": calls_week.scalar() or 0,
        },
        "leads": {
            "total": total_leads_count,
            "hot": hot_leads.scalar() or 0,
        },
        "products": {
            "active": active_products.scalar() or 0,
        },
        "metrics": {
            "conversion_rate": round(conversion_rate, 2),
            "avg_call_duration_seconds": round(avg_duration.scalar() or 0, 2),
        }
    }


@router.get("/calls")
async def get_call_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> dict:
    """Get call analytics report."""
    if not date_from:
        date_from = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=30)
    if not date_to:
        date_to = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    date_filter = and_(Call.created_at >= date_from, Call.created_at <= date_to)
    
    # Total calls
    total_calls = await db.execute(
        select(func.count(Call.id)).where(date_filter)
    )
    
    # Calls by status
    completed_calls = await db.execute(
        select(func.count(Call.id)).where(
            and_(date_filter, Call.status == CallStatus.COMPLETED.value)
        )
    )
    
    missed_calls = await db.execute(
        select(func.count(Call.id)).where(
            and_(date_filter, Call.status == CallStatus.NO_ANSWER.value)
        )
    )
    
    # AI vs Human handled
    ai_handled = await db.execute(
        select(func.count(Call.id)).where(
            and_(
                date_filter,
                Call.handled_by_ai.is_(True),
                Call.escalated_to_human.is_(False),
            )
        )
    )
    
    escalated = await db.execute(
        select(func.count(Call.id)).where(
            and_(date_filter, Call.escalated_to_human.is_(True))
        )
    )
    
    # Average duration
    avg_duration = await db.execute(
        select(func.avg(Call.duration_seconds)).where(
            and_(date_filter, Call.duration_seconds.is_not(None))
        )
    )
    
    # Calls by outcome
    outcome_counts = {}
    for outcome in CallOutcome:
        count = await db.execute(
            select(func.count(Call.id)).where(
                and_(date_filter, Call.outcome == outcome.value)
            )
        )
        outcome_counts[outcome.value] = count.scalar() or 0
    
    return {
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        },
        "totals": {
            "total_calls": total_calls.scalar() or 0,
            "completed": completed_calls.scalar() or 0,
            "missed": missed_calls.scalar() or 0,
        },
        "handling": {
            "ai_only": ai_handled.scalar() or 0,
            "escalated_to_human": escalated.scalar() or 0,
        },
        "metrics": {
            "avg_duration_seconds": round(avg_duration.scalar() or 0, 2),
        },
        "outcomes": outcome_counts,
    }


@router.get("/agents")
async def get_agent_performance(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> dict:
    """Get agent performance report."""
    if not date_from:
        date_from = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=30)
    if not date_to:
        date_to = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    # Get all agents
    agents_result = await db.execute(
        select(User).where(User.role == UserRole.AGENT.value)
    )
    agents = agents_result.scalars().all()
    
    agent_stats = []
    
    for agent in agents:
        # Assigned leads
        assigned_leads = await db.execute(
            select(func.count(Lead.id)).where(Lead.assigned_agent_id == agent.id)
        )
        
        # Converted leads
        converted = await db.execute(
            select(func.count(Lead.id)).where(
                and_(
                    Lead.assigned_agent_id == agent.id,
                    Lead.status == LeadStatus.CONVERTED.value
                )
            )
        )
        
        # Escalated calls
        escalated_calls = await db.execute(
            select(func.count(Call.id)).where(
                and_(
                    Call.escalated_to_agent_id == agent.id,
                    Call.created_at >= date_from,
                    Call.created_at <= date_to,
                )
            )
        )
        
        assigned_count = assigned_leads.scalar() or 0
        converted_count = converted.scalar() or 0
        
        agent_stats.append({
            "agent_id": agent.id,
            "agent_name": agent.full_name,
            "assigned_leads": assigned_count,
            "converted_leads": converted_count,
            "conversion_rate": round(
                (converted_count / assigned_count * 100) if assigned_count > 0 else 0,
                2,
            ),
            "escalated_calls": escalated_calls.scalar() or 0,
        })
    
    return {
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        },
        "agents": agent_stats,
    }


@router.get("/leads")
async def get_lead_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> dict:
    """Get lead analytics report."""
    if not date_from:
        date_from = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=30)
    if not date_to:
        date_to = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    date_filter = and_(Lead.created_at >= date_from, Lead.created_at <= date_to)
    
    # Leads by quality
    quality_counts = {}
    for quality in LeadQuality:
        count = await db.execute(
            select(func.count(Lead.id)).where(
                and_(date_filter, Lead.quality == quality.value)
            )
        )
        quality_counts[quality.value] = count.scalar() or 0
    
    # Leads by status
    status_counts = {}
    for status in LeadStatus:
        count = await db.execute(
            select(func.count(Lead.id)).where(
                and_(date_filter, Lead.status == status.value)
            )
        )
        status_counts[status.value] = count.scalar() or 0
    
    # Unassigned leads
    unassigned = await db.execute(
        select(func.count(Lead.id)).where(
            and_(date_filter, Lead.assigned_agent_id.is_(None))
        )
    )
    
    # Average time to conversion
    converted_leads = await db.execute(
        select(Lead).where(
            and_(
                Lead.converted_at.is_not(None),
                Lead.created_at >= date_from,
            )
        )
    )
    
    conversion_times = []
    for lead in converted_leads.scalars().all():
        if lead.converted_at and lead.created_at:
            delta = lead.converted_at - lead.created_at
            conversion_times.append(delta.total_seconds() / 86400)  # Days
    
    avg_conversion_days = sum(conversion_times) / len(conversion_times) if conversion_times else 0
    
    return {
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        },
        "by_quality": quality_counts,
        "by_status": status_counts,
        "unassigned": unassigned.scalar() or 0,
        "metrics": {
            "avg_conversion_days": round(avg_conversion_days, 2),
        }
    }
