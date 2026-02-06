import asyncio
import json
import base64
import time
from typing import Optional, Callable

import websockets
import audioop

from app.config import settings
from app.utils.logging import get_logger
from app.services.rag_service import RAGService

logger = get_logger("voip.realtime_client")

# -------------------------
# INDIA-TUNED CONSTANTS
# -------------------------
NOISE_LEARN_FRAMES = 30
NOISE_MULTIPLIER = 3.0
ABSOLUTE_MIN_RMS = 180

MIN_SPEECH_FRAMES = 10
BARGE_IN_FRAMES = 4
BARGE_IN_MULTIPLIER = 1.8

SILENCE_COMMIT_DELAY = 1.1
PING_INTERVAL = 20
PING_TIMEOUT = 10


class RealtimeClient:
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.socket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

        self.send_audio_callback: Optional[Callable[[str], None]] = None
        self.send_json_callback: Optional[Callable[[dict], None]] = None

        self.assistant_speaking = False
        self.last_assistant_item: Optional[str] = None
        
        self.transcript = []
        self.rag = RAGService()

    # -------------------------
    async def connect(self):
        endpoint = settings.azure_realtime_openai_endpoint.rstrip("/").replace(
            "https://", "wss://"
        )

        url = (
            f"{endpoint}/openai/realtime"
            f"?api-version={settings.azure_openai_realtime_api_version}"
            f"&deployment={settings.azure_openai_realtime_deployment}"
        )

        self.socket = await websockets.connect(
            url,
            additional_headers={"api-key": settings.azure_realtime_openai_api_key},
            subprotocols=["realtime"],
            ping_interval=PING_INTERVAL,
            ping_timeout=PING_TIMEOUT,
            max_size=None,
        )

        self.is_connected = True
        asyncio.create_task(self._receive_loop())

        logger.info("realtime_connected", call_sid=self.call_sid)

    # -------------------------
    async def update_session(self, instructions: str):
        # Azure-specific session update matching reference logic where possible
        await self.socket.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": "alloy",
                "input_audio_format": "g711_ulaw",  # Direct from Twilio
                "output_audio_format": "g711_ulaw", # Direct for Twilio
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.6,
                    "silence_duration_ms": 1000,
                    "create_response": False, # Manual trigger after RAG
                },
                "input_audio_transcription": {"model": "whisper-1"},
            },
        }))

    # -------------------------
    async def send_initial_greeting(self, greeting_text: str):
        """Send the initial greeting as if it were a user instruction to the AI."""
        await self.socket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Greet the user with: '{greeting_text}'. Then wait for them to respond."
                    }
                ]
            }
        }))
        await self.socket.send(json.dumps({
            "type": "response.create",
            "response": {"modalities": ["text", "audio"]},
        }))

    # -------------------------
    async def send_audio(self, audio_b64: str):
        if not self.is_connected:
            return

        # Half-duplex turn taking: ignore user while AI speaks
        if self.assistant_speaking:
            return

        await self.socket.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }))

    # -------------------------
    async def _handle_speech_started(self):
        """Handle interruption when user starts speaking."""
        # Even in half-duplex, we want to clear Twilio's buffers if something triggered
        # though our 'ignore' logic in send_audio prevents actual interruption of flow.
        if self.send_json_callback:
            await self.send_json_callback({"event": "clear"})

    # -------------------------
    async def _receive_loop(self):
        async for msg in self.socket:
            await self._handle_event(json.loads(msg))

    async def _handle_event(self, data: dict):
        etype = data.get("type")

        if etype == "error":
            logger.error("realtime_error", error=data.get("error"))
            return

        if etype == "response.audio.delta":
            if not self.assistant_speaking:
                self.assistant_speaking = True
            
            if data.get("item_id"):
                self.last_assistant_item = data["item_id"]

            if self.send_audio_callback:
                await self.send_audio_callback(data["delta"])

        elif etype in ("response.done", "response.audio.done"):
            self.assistant_speaking = False

        elif etype == "input_audio_buffer.speech_started":
            logger.info("speech_started")
            await self._handle_speech_started()

        elif etype == "conversation.item.input_audio_transcription.completed":
            user_text = data.get("transcript", "").strip()
            if not user_text:
                return

            logger.info("user_speech_transcribed", text=user_text)
            self.transcript.append({"role": "user", "content": user_text})

            context = await self.rag.retrieve(user_text)

            await self.socket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{
                        "type": "text",
                        "text": f"{context}\n\nUser: {user_text}"
                    }],
                },
            }))

            await self.socket.send(json.dumps({
                "type": "response.create",
                "response": {"modalities": ["text", "audio"]},
            }))

    # -------------------------
    def set_on_audio_delta(self, cb: Callable[[str], None]):
        self.send_audio_callback = cb

    def set_on_json_event(self, cb: Callable[[dict], None]):
        self.send_json_callback = cb

    def get_transcript(self):
        if not self.transcript:
            return None
        return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in self.transcript)

    async def close(self):
        self.is_connected = False
        if self.socket:
            await self.socket.close()