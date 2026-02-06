"""API endpoints for conversation summaries."""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import get_mongodb
from app.utils.logging import get_logger

router = APIRouter(prefix="/api/summaries", tags=["summaries"])
logger = get_logger("api.summaries")


class ConversationSummaryResponse(BaseModel):
    """Response model for conversation summary."""
    call_sid: str
    summary: str
    customer_name: Optional[str]
    phone_number: str
    preferred_language: Optional[str]
    requirements: dict
    properties_discussed: List[int]
    lead_quality: str
    key_points: List[str]
    next_steps: Optional[str]
    created_at: datetime


@router.get("", response_model=List[ConversationSummaryResponse])
async def get_summaries(
    phone_number: Optional[str] = Query(None),
    lead_quality: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    skip: int = Query(0, ge=0),
):
    """Get list of conversation summaries with optional filters."""
    try:
        mongo = get_mongodb()
        
        # Build query filter
        query_filter = {}
        if phone_number:
            query_filter["phone_number"] = phone_number
        if lead_quality:
            query_filter["lead_quality"] = lead_quality
        
        # Query MongoDB
        cursor = mongo.conversation_summaries.find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
        summaries = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string for response
        for summary in summaries:
            summary.pop("_id", None)
        
        return summaries
    except Exception as e:
        logger.error("get_summaries_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{call_sid}", response_model=ConversationSummaryResponse)
async def get_summary_by_call(call_sid: str):
    """Get conversation summary by call SID."""
    try:
        mongo = get_mongodb()
        
        summary = await mongo.conversation_summaries.find_one({"call_sid": call_sid})
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        summary.pop("_id", None)
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_summary_failed", error=str(e), call_sid=call_sid)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead/{lead_id}", response_model=List[ConversationSummaryResponse])
async def get_summaries_by_lead(lead_id: int):
    """Get all conversation summaries for a specific lead."""
    try:
        from app.database import async_session_maker
        from app.models.lead import Lead
        from sqlalchemy import select
        
        # Get lead's phone number from SQLite
        async with async_session_maker() as db:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            phone_number = lead.phone
        
        # Get summaries from MongoDB
        mongo = get_mongodb()
        cursor = mongo.conversation_summaries.find({"phone_number": phone_number}).sort("created_at", -1)
        summaries = await cursor.to_list(length=None)
        
        for summary in summaries:
            summary.pop("_id", None)
        
        return summaries
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_summaries_by_lead_failed", error=str(e), lead_id=lead_id)
        raise HTTPException(status_code=500, detail=str(e))
