"""
Twilio Media Stream WebSocket handler
(HALF-DUPLEX SAFE + BARGE-IN READY)
"""

import asyncio
import json
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import async_session_maker
from app.models.call import Call, CallStatus
from app.voip.realtime_client import RealtimeClient
from app.voip.prompts import REAL_ESTATE_ASSISTANT_PROMPT, GREETING_MESSAGE
from app.services.report_service import ReportService
from app.services.rag_service import RAGService
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger("voip.media_stream")

active_calls: Dict[str, RealtimeClient] = {}

SESSION_INIT_WAIT_SECONDS = 0.3


@router.websocket("/media-stream")
async def media_stream_websocket(websocket: WebSocket):
    await websocket.accept()

    client: Optional[RealtimeClient] = None
    stream_sid: Optional[str] = None
    call_sid: Optional[str] = None

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event = data.get("event")

            # ---------------------------
            # CALL START
            # ---------------------------
            if event == "start":
                stream_sid = data["streamSid"]
                call_sid = data["start"]["callSid"]

                # Step 0: Mark call as in-progress in DB
                try:
                    async with async_session_maker() as db:
                        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
                        call = result.scalar_one_or_none()
                        if call:
                            call.status = CallStatus.IN_PROGRESS.value
                            if not call.started_at:
                                call.started_at = datetime.now(timezone.utc)
                            await db.commit()
                except Exception as e:
                    logger.error("call_start_update_failed", error=str(e), call_sid=call_sid)

                client = RealtimeClient(call_sid)
                active_calls[call_sid] = client

                async def send_audio(audio_b64: str):
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": audio_b64},
                    })

                client.set_on_audio_delta(send_audio)

                async def send_json(data: dict):
                    await websocket.send_json({
                        "event": data["event"],
                        "streamSid": stream_sid,
                        **data
                    })
                
                client.set_on_json_event(send_json)

                await client.connect()
                
                # Fetch available locations and inject into prompt
                rag = RAGService()
                locations_text = await rag.get_available_locations()
                full_prompt = f"{REAL_ESTATE_ASSISTANT_PROMPT}\n\n# CONTEXT: DATABASE INVENTORY\n{locations_text}"
                
                await client.update_session(full_prompt)

                # Step 1: Proactive greeting and question
                await client.send_initial_greeting(GREETING_MESSAGE)

            # ---------------------------
            # AUDIO FROM TWILIO
            # ---------------------------
            elif event == "media":
                if client and client.is_connected:
                    # logger.debug("audio_from_twilio", call_sid=call_sid)
                    await client.send_audio(data["media"]["payload"])

            # ---------------------------
            # CALL END
            # ---------------------------
            elif event == "stop":
                logger.info("twilio_stream_stopped", call_sid=call_sid)
                break

    except WebSocketDisconnect:
        logger.info("twilio_ws_disconnected", call_sid=call_sid)

    finally:
        if client:
            transcript = client.get_transcript()
            if transcript:
                asyncio.create_task(
                    ReportService().generate_report(
                        call_sid=call_sid,
                        transcript=transcript,
                        transcript_messages=client.transcript,
                    )
                )
            await client.close()

        if call_sid:
            # Force update call status to completed if it ended
            try:
                async with async_session_maker() as db:
                    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
                    call = result.scalar_one_or_none()
                    if call and call.status not in [CallStatus.COMPLETED.value, CallStatus.FAILED.value]:
                        call.status = CallStatus.COMPLETED.value
                        call.ended_at = datetime.now(timezone.utc)
                        if call.started_at:
                            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
                        await db.commit()
            except Exception as e:
                logger.error("call_status_update_failed", error=str(e), call_sid=call_sid)
            
            active_calls.pop(call_sid, None)

        logger.info("call_cleanup_complete", call_sid=call_sid)