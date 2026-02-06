"""
Twilio Media Stream WebSocket handler
(HALF-DUPLEX SAFE + BARGE-IN READY)
"""

import asyncio
import json
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.voip.realtime_client import RealtimeClient
from app.voip.prompts import REAL_ESTATE_ASSISTANT_PROMPT, GREETING_MESSAGE
from app.services.report_service import ReportService
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

                logger.info("twilio_stream_started", call_sid=call_sid)

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
                await client.update_session(REAL_ESTATE_ASSISTANT_PROMPT)

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
            active_calls.pop(call_sid, None)

        logger.info("call_cleanup_complete", call_sid=call_sid)