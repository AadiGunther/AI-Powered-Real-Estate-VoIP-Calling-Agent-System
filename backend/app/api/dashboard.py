"""API endpoints for dashboard statistics and metrics."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, and_, case

from app.database import async_session_maker
from app.models.call import Call, CallStatus, CallOutcome
from app.models.lead import Lead, LeadQuality, LeadStatus
from app.models.product import Product
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = get_logger("api.dashboard")
_ist_tz = ZoneInfo("Asia/Kolkata")


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
    total_products: int
    active_products: int
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
    def created_at_to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            logger.info(
                "recent_call_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


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


class SolarPerformanceMetrics(BaseModel):
    current_power_kw: float
    daily_energy_kwh: float
    monthly_energy_kwh: float
    performance_ratio: float
    system_efficiency_pct: float
    total_capacity_kw: float


class EnvironmentMetrics(BaseModel):
    temperature_c: float
    weather_condition: str
    solar_irradiance_w_m2: float
    wind_speed_m_s: float


class FinancialMetrics(BaseModel):
    daily_savings_inr: float
    monthly_savings_inr: float
    lifetime_savings_inr: float
    roi_percent: float
    payback_years: float
    carbon_offset_kg: float
    trees_equivalent: float


class OperationalStatus(BaseModel):
    overall_status: str
    active_alarms: int
    uptime_percent: float
    last_update: datetime

    @field_validator("last_update", mode="after")
    @classmethod
    def last_update_to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            logger.info(
                "operational_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class SolarAlert(BaseModel):
    id: str
    severity: str
    message: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def alert_created_to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            logger.info(
                "solar_alert_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class EnergyTrendPoint(BaseModel):
    timestamp: datetime
    energy_kwh: float

    @field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_to_ist(cls, v: datetime, info) -> datetime:
        original = v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        ist_value = v.astimezone(_ist_tz)
        try:
            logger.info(
                "energy_trend_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


class SolarDashboardResponse(BaseModel):
    performance: SolarPerformanceMetrics
    environment: EnvironmentMetrics
    financial: FinancialMetrics
    operational: OperationalStatus
    alerts: List[SolarAlert]
    energy_trend: List[EnergyTrendPoint]


class SolarTelemetryUpdate(BaseModel):
    performance: SolarPerformanceMetrics
    environment: EnvironmentMetrics
    financial: FinancialMetrics


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


@router.get("/solar-realtime", response_model=SolarDashboardResponse)
async def get_solar_realtime():
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        perf_data: Dict[str, Any] = {}
        env_data: Dict[str, Any] = {}
        fin_data: Dict[str, Any] = {}
        op_data: Dict[str, Any] = {}
        trend_data: List[Dict[str, Any]] = []

        performance = SolarPerformanceMetrics(
            current_power_kw=float(perf_data.get("current_power_kw", 4.2)),
            daily_energy_kwh=float(perf_data.get("daily_energy_kwh", 18.5)),
            monthly_energy_kwh=float(perf_data.get("monthly_energy_kwh", 540.0)),
            performance_ratio=float(perf_data.get("performance_ratio", 0.82)),
            system_efficiency_pct=float(perf_data.get("system_efficiency_pct", 92.0)),
            total_capacity_kw=float(perf_data.get("total_capacity_kw", 5.0)),
        )

        environment = EnvironmentMetrics(
            temperature_c=float(env_data.get("temperature_c", 32.0)),
            weather_condition=str(env_data.get("weather_condition", "Sunny")),
            solar_irradiance_w_m2=float(env_data.get("solar_irradiance_w_m2", 820.0)),
            wind_speed_m_s=float(env_data.get("wind_speed_m_s", 2.4)),
        )

        financial = FinancialMetrics(
            daily_savings_inr=float(fin_data.get("daily_savings_inr", 220.0)),
            monthly_savings_inr=float(fin_data.get("monthly_savings_inr", 6500.0)),
            lifetime_savings_inr=float(fin_data.get("lifetime_savings_inr", 325000.0)),
            roi_percent=float(fin_data.get("roi_percent", 18.5)),
            payback_years=float(fin_data.get("payback_years", 4.5)),
            carbon_offset_kg=float(fin_data.get("carbon_offset_kg", 120.0)),
            trees_equivalent=float(fin_data.get("trees_equivalent", 5.0)),
        )

        last_update_value = op_data.get("last_update") or telemetry.get("created_at") if telemetry else now
        if isinstance(last_update_value, str):
            last_update_dt = datetime.fromisoformat(last_update_value)
        else:
            last_update_dt = last_update_value or now
        if last_update_dt.tzinfo is None:
            last_update_dt = last_update_dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        overall_status = str(op_data.get("overall_status", "ok"))
        active_alarms = int(op_data.get("active_alarms", 0))
        uptime_percent = float(op_data.get("uptime_percent", 99.5))

        operational = OperationalStatus(
            overall_status=overall_status,
            active_alarms=active_alarms,
            uptime_percent=uptime_percent,
            last_update=last_update_dt,
        )

        alerts_cursor = None
        alerts_docs: List[Dict[str, Any]] = []
        try:
            alerts_cursor = mongo.solar_alerts.find().sort("created_at", -1).limit(5)
            alerts_docs = await alerts_cursor.to_list(length=5)
        except Exception as e:
            logger.error("get_solar_alerts_failed", error=str(e))

        alerts: List[SolarAlert] = []
        for doc in alerts_docs:
            created_at_value = doc.get("created_at", now)
            if isinstance(created_at_value, str):
                created_at_dt = datetime.fromisoformat(created_at_value)
            else:
                created_at_dt = created_at_value or now
            if created_at_dt.tzinfo is None:
                created_at_dt = created_at_dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            alerts.append(
                SolarAlert(
                    id=str(doc.get("id") or doc.get("_id")),
                    severity=str(doc.get("severity", "info")),
                    message=str(doc.get("message", "")),
                    created_at=created_at_dt,
                )
            )

        if not trend_data:
            trend_points: List[EnergyTrendPoint] = []
            for i in range(6, -1, -1):
                ts = now - timedelta(days=i)
                energy_value = 12.0 + (6 - i) * 1.2
                trend_points.append(EnergyTrendPoint(timestamp=ts, energy_kwh=energy_value))
        else:
            trend_points = []
            for item in trend_data:
                ts_value = item.get("timestamp", now)
                if isinstance(ts_value, str):
                    ts_dt = datetime.fromisoformat(ts_value)
                else:
                    ts_dt = ts_value or now
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                trend_points.append(
                    EnergyTrendPoint(
                        timestamp=ts_dt,
                        energy_kwh=float(item.get("energy_kwh", 0.0)),
                    )
                )

        return SolarDashboardResponse(
            performance=performance,
            environment=environment,
            financial=financial,
            operational=operational,
            alerts=alerts,
            energy_trend=trend_points,
        )
    except Exception as e:
        logger.error("get_solar_realtime_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solar-telemetry")
async def update_solar_telemetry(payload: SolarTelemetryUpdate):
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        overall_status = "ok"
        active_alarms = 0
        alerts: List[Dict[str, Any]] = []

        if payload.performance.system_efficiency_pct < 75.0:
            overall_status = "warning"
            active_alarms += 1
            alerts.append(
                {
                    "severity": "warning",
                    "message": "System efficiency below expected threshold.",
                    "created_at": now,
                }
            )

        if payload.environment.solar_irradiance_w_m2 > 800.0 and payload.performance.current_power_kw < payload.performance.total_capacity_kw * 0.5:
            overall_status = "warning"
            active_alarms += 1
            alerts.append(
                {
                    "severity": "warning",
                    "message": "High irradiance but low power output detected.",
                    "created_at": now,
                }
            )

        return {"success": True}
    except Exception as e:
        logger.error("update_solar_telemetry_failed", error=str(e))
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
            
            # Products stats (solar inventory)
            total_products = await db.scalar(select(func.count(Product.id)))
            active_products = await db.scalar(
                select(func.count(Product.id)).where(Product.is_active == True)
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
                total_products=total_products or 0,
                active_products=active_products or 0,
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
