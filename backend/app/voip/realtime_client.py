"""
OpenAI / Azure Realtime voice client
(HALF-DUPLEX + ADAPTIVE NOISE + RAG SAFE)
"""

import asyncio
import json
import base64
import time
from typing import Optional, Callable

import websockets

try:
    import audioop
except ImportError:
    import audioop_lts as audioop

from app.config import settings
from app.utils.logging import get_logger
from app.services.rag_service import RAGService
from app.voip.prompts import REAL_ESTATE_ASSISTANT_PROMPT

logger = get_logger("voip.realtime_client")

PING_INTERVAL = 20
PING_TIMEOUT = 10

MIN_SPEECH_FRAMES = 10
SILENCE_COMMIT_DELAY = 0.8
NOISE_LEARN_FRAMES = 40
NOISE_MULTIPLIER = 3.0
ABSOLUTE_MIN_RMS = 150
NOISE_ADAPTATION_RATE = 0.01


class RealtimeClient:
    def __init__(self, call_sid: str):
        self.call_sid = call_sid

        self.socket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

        self.send_audio_callback: Optional[Callable[[str], None]] = None

        self.assistant_speaking = False
        self.last_audio_rx_ts = 0.0
        self.buffer_committed = True
        self.speech_frame_count = 0

        self.noise_floor = 0.0
        self.noise_samples = 0

        self._resample_up = None
        self._resample_down = None

        self.transcript: list[dict] = []
        self.rag = RAGService()

    # -------------------------------------------------
    async def connect(self):
        headers = {}
        subprotocols = ["realtime"]

        if settings.azure_realtime_openai_endpoint and settings.azure_realtime_openai_api_key:
            endpoint = settings.azure_realtime_openai_endpoint.rstrip("/").replace(
                "https://", "wss://"
            )
            url = (
                f"{endpoint}/openai/realtime"
                f"?api-version={settings.azure_openai_realtime_api_version}"
                f"&deployment={settings.azure_openai_realtime_deployment}"
            )
            headers = {"api-key": settings.azure_realtime_openai_api_key}
        else:
            url = f"wss://api.openai.com/v1/realtime?model={settings.openai_realtime_model}"
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            }

        self.socket = await websockets.connect(
            url,
            additional_headers=headers,
            subprotocols=subprotocols,
            ping_interval=PING_INTERVAL,
            ping_timeout=PING_TIMEOUT,
            max_size=None,
        )

        self.is_connected = True

        asyncio.create_task(self._receive_loop())
        asyncio.create_task(self._silence_watcher())

        logger.info("realtime_connected", call_sid=self.call_sid)

    # -------------------------------------------------
    async def update_session(self, instructions: str):
        await self.socket.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["audio"],
                "instructions": instructions,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": int(SILENCE_COMMIT_DELAY * 1000),
                    "create_response": False,
                },
                "input_audio_transcription": {"model": "whisper-1"},
            },
        }))

    # -------------------------------------------------
    async def send_assistant_message(self, text: str):
        await self.socket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            },
        }))
        await self.socket.send(json.dumps({
            "type": "response.create",
            "response": {"modalities": ["audio"]},
        }))

    # -------------------------------------------------
    async def send_audio(self, audio_b64: str):
        if not self.is_connected or self.assistant_speaking:
            return

        ulaw = base64.b64decode(audio_b64)
        pcm8k = audioop.ulaw2lin(ulaw, 2)
        rms = audioop.rms(pcm8k, 2)

        if self.noise_samples < NOISE_LEARN_FRAMES:
            self.noise_floor = (
                (self.noise_floor * self.noise_samples) + rms
            ) / (self.noise_samples + 1)
            self.noise_samples += 1
            return

        threshold = max(self.noise_floor * NOISE_MULTIPLIER, ABSOLUTE_MIN_RMS)

        if rms < threshold:
            # Slowly adapt the noise floor downward or slightly upward if it's pure noise
            self.noise_floor = (
                (self.noise_floor * (1 - NOISE_ADAPTATION_RATE)) + (rms * NOISE_ADAPTATION_RATE)
            )
            self.speech_frame_count = 0
            return

        self.speech_frame_count += 1
        if self.speech_frame_count < MIN_SPEECH_FRAMES:
            return

        self.last_audio_rx_ts = time.time()
        self.buffer_committed = False

        pcm24k, self._resample_up = audioop.ratecv(
            pcm8k, 2, 1, 8000, 24000, self._resample_up
        )

        await self.socket.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm24k).decode(),
        }))

    # -------------------------------------------------
    async def _silence_watcher(self):
        while self.is_connected:
            await asyncio.sleep(0.15)

            if self.assistant_speaking or self.buffer_committed:
                continue

            if time.time() - self.last_audio_rx_ts > SILENCE_COMMIT_DELAY:
                logger.info("user_turn_committed", call_sid=self.call_sid)

                await self.socket.send(json.dumps({
                    "type": "input_audio_buffer.commit"
                }))

                self.buffer_committed = True
                self.speech_frame_count = 0

    # -------------------------------------------------
    async def _receive_loop(self):
        try:
            async for msg in self.socket:
                try:
                    await self._handle_event(json.loads(msg))
                except Exception as e:
                    logger.exception("event_handling_error", error=str(e))
        except Exception as e:
            if self.is_connected:
                logger.exception("receive_loop_fatal_error", error=str(e))

    async def _handle_event(self, data: dict):
        etype = data.get("type")

        if etype == "response.created":
            self.assistant_speaking = True

        elif etype == "response.audio.delta":
            pcm24k = base64.b64decode(data["delta"])
            pcm8k, self._resample_down = audioop.ratecv(
                pcm24k, 2, 1, 24000, 8000, self._resample_down
            )
            ulaw = audioop.lin2ulaw(pcm8k, 2)

            if self.send_audio_callback:
                await self.send_audio_callback(base64.b64encode(ulaw).decode())

        elif etype == "response.done":
            self.assistant_speaking = False
            # Capture assistant transcript
            response = data.get("response", {})
            for item in response.get("output", []):
                if item.get("type") == "message" and item.get("role") == "assistant":
                    content = item.get("content", [])
                    for part in content:
                        if part.get("type") == "audio":
                            transcript = part.get("transcript")
                            if transcript:
                                self.transcript.append({"role": "assistant", "content": transcript})

        elif etype == "response.audio.done":
            self.assistant_speaking = False

        elif etype == "conversation.item.input_audio_transcription.completed":
            user_text = data.get("transcript", "").strip()
            if not user_text:
                return

            self.transcript.append({"role": "user", "content": user_text})

            context = await self.rag.retrieve(user_text)

            await self.socket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{
                        "type": "text",
                        "text": f"{REAL_ESTATE_ASSISTANT_PROMPT}\n\nContext:\n{context}\n\nUser: {user_text}"
                    }],
                },
            }))

            await self.socket.send(json.dumps({
                "type": "response.create",
                "response": {"modalities": ["audio"]},
            }))

    # -------------------------------------------------
    def set_on_audio_delta(self, cb: Callable[[str], None]):
        self.send_audio_callback = cb

    def get_transcript(self) -> Optional[str]:
        """Get formatted transcript from the conversation."""
        if not self.transcript:
            return None
        
        formatted = []
        for msg in self.transcript:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)

    async def close(self):
        self.is_connected = False
        if self.socket:
            await self.socket.close()
