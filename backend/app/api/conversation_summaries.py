"""API endpoints for conversation summaries."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.call import Call
from app.models.lead import Lead
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/summaries", tags=["summaries"])
logger = get_logger("api.summaries")
_ist_tz = ZoneInfo("Asia/Kolkata")


class ConversationSummaryResponse(BaseModel):
    call_sid: str
    summary: str
    customer_name: Optional[str]
    phone_number: str
    preferred_language: Optional[str]
    requirements: Dict[str, Any]
    properties_discussed: List[int]
    lead_quality: str
    key_points: List[str]
    next_steps: Optional[str]
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
                "summary_datetime_converted_to_ist",
                field=info.field_name,
                original_iso=original.isoformat(),
                original_tz=str(original.tzinfo),
                ist_iso=ist_value.isoformat(),
            )
        except Exception:
            pass
        return ist_value


def _build_summary(call: Call, lead: Optional[Lead]) -> ConversationSummaryResponse:
    requirements: Dict[str, Any] = {}
    if lead:
        requirements = {
            "location": lead.preferred_location,
            "property_type": lead.preferred_property_type,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "size_min": lead.preferred_size_min,
            "size_max": lead.preferred_size_max,
        }
    properties_discussed: List[int] = []
    if call.properties_discussed:
        try:
            properties_discussed = json.loads(call.properties_discussed)
        except Exception:
            properties_discussed = []
    summary_text = ""
    if lead and lead.ai_summary:
        summary_text = lead.ai_summary
    elif call.transcript_summary:
        summary_text = call.transcript_summary
    phone = call.from_number
    name: Optional[str] = None
    quality = "cold"
    if lead:
        phone = lead.phone
        name = lead.name
        quality = lead.quality
    return ConversationSummaryResponse(
        call_sid=call.call_sid,
        summary=summary_text,
        customer_name=name,
        phone_number=phone,
        preferred_language=None,
        requirements=requirements,
        properties_discussed=properties_discussed,
        lead_quality=quality,
        key_points=[],
        next_steps=call.outcome_notes,
        created_at=call.created_at,
    )


@router.get("", response_model=List[ConversationSummaryResponse])
async def get_summaries(
    phone_number: Optional[str] = Query(None),
    lead_quality: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(Call, Lead).join(Lead, Call.lead_id == Lead.id, isouter=True)
        if phone_number:
            stmt = stmt.where(Lead.phone == phone_number)
        if lead_quality:
            stmt = stmt.where(Lead.quality == lead_quality)
        stmt = stmt.order_by(Call.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        rows = result.all()
        summaries: List[ConversationSummaryResponse] = []
        for call, lead in rows:
            summaries.append(_build_summary(call, lead))
        return summaries
    except Exception as e:
        logger.error("get_summaries_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{call_sid}", response_model=ConversationSummaryResponse)
async def get_summary_by_call(call_sid: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Call, Lead).join(Lead, Call.lead_id == Lead.id, isouter=True).where(
            Call.call_sid == call_sid
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Summary not found")
        call, lead = row
        return _build_summary(call, lead)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_summary_failed", error=str(e), call_sid=call_sid)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead/{lead_id}", response_model=List[ConversationSummaryResponse])
async def get_summaries_by_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(Call, Lead).join(Lead, Call.lead_id == Lead.id, isouter=True).where(
            Lead.id == lead_id
        )
        stmt = stmt.order_by(Call.created_at.desc())
        result = await db.execute(stmt)
        rows = result.all()
        if not rows:
            raise HTTPException(status_code=404, detail="Lead not found or no calls")
        summaries: List[ConversationSummaryResponse] = []
        for call, lead in rows:
            summaries.append(_build_summary(call, lead))
        return summaries
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_summaries_by_lead_failed", error=str(e), lead_id=lead_id)
        raise HTTPException(status_code=500, detail=str(e))
