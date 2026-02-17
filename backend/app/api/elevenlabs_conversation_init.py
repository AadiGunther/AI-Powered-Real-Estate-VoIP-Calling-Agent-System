from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from pydantic import AliasChoices, Field

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.services.elevenlabs_conversation_init_service import build_dynamic_context
from app.utils.logging import get_logger


router = APIRouter(prefix="/elevenlabs", tags=["ElevenLabs"])
logger = get_logger("api.elevenlabs_conversation_init")


class ConversationInitRequest(BaseModel):
    call_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("call_id", "call_sid", "conversation_id", "id"),
    )
    from_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("from_number", "caller_id", "from", "caller"),
    )
    to_number: str = Field(
        validation_alias=AliasChoices("to_number", "called_number", "to", "callee"),
    )
    call_direction: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("call_direction", "direction"),
    )
    model_config = ConfigDict(extra="allow")


class ConversationInitiationClientData(BaseModel):
    dynamic_context: str


class ConversationInitResponse(BaseModel):
    conversation_initiation_client_data: ConversationInitiationClientData


@router.post("/conversation-init", response_model=ConversationInitResponse)
async def conversation_init(request: Request) -> ConversationInitResponse:
    try:
        data: Any
        try:
            data = await request.json()
        except Exception:
            form = await request.form()
            data = dict(form)
        payload = ConversationInitRequest.model_validate(data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation-init payload.",
        )

    try:
        dynamic_context = await build_dynamic_context(to_number=payload.to_number)
    except NotImplementedError:
        logger.error("conversation_init_db_not_implemented", to_number=payload.to_number)
        dynamic_context = (
            "Company name: Unknown Company\n"
            "Product catalog:\n"
            "-\n"
            "Subsidy information:\n"
            "-\n"
            "EMI policy:\n"
            "-\n"
            "Active offers:\n"
            "-\n"
        )
    except Exception as e:
        logger.error(
            "conversation_init_failed",
            error=str(e),
            to_number=payload.to_number,
            call_id=payload.call_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build dynamic context.",
        )

    return ConversationInitResponse(
        conversation_initiation_client_data=ConversationInitiationClientData(
            dynamic_context=dynamic_context,
        )
    )
