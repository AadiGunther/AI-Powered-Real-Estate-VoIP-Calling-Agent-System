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

# ---------------- TUNING CONSTANTS ----------------
PING_INTERVAL = 20
PING_TIMEOUT = 10

MIN_SPEECH_FRAMES = 3          # ~60–90 ms
SILENCE_COMMIT_DELAY = 0.6     # seconds
NOISE_LEARN_FRAMES = 50        # initial calibration frames
NOISE_MULTIPLIER = 2.5         # speech must exceed noise floor
ABSOLUTE_MIN_RMS = 120         # safety lower bound
# -------------------------------------------------


class RealtimeClient:
    def __init__(self, call_sid: str):
        self.call_sid = call_sid

        self.socket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

        self.send_audio_callback: Optional[Callable[[str], None]] = None

        # Turn / speech state
        self.assistant_speaking = False
        self.last_audio_rx_ts = 0.0
        self.buffer_committed = True
        self.speech_frame_count = 0

        # Adaptive noise model
        self.noise_floor = 0.0
        self.noise_samples = 0

        # Audio resampling state
        self._resample_up = None
        self._resample_down = None

        # Memory
        self.transcript: list[dict] = []
        self.rag = RAGService()

    # -------------------------------------------------
    # CONNECTION
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
    # SESSION
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
    # GREETING
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
    # AUDIO INPUT
    # -------------------------------------------------
    async def send_audio(self, audio_b64: str):
        if not self.is_connected or self.assistant_speaking:
            return

        ulaw = base64.b64decode(audio_b64)
        pcm8k = audioop.ulaw2lin(ulaw, 2)
        rms = audioop.rms(pcm8k, 2)

        # --- Learn background noise first ---
        if self.noise_samples < NOISE_LEARN_FRAMES:
            self.noise_floor = (
                (self.noise_floor * self.noise_samples) + rms
            ) / (self.noise_samples + 1)
            self.noise_samples += 1
            return

        speech_threshold = max(
            self.noise_floor * NOISE_MULTIPLIER,
            ABSOLUTE_MIN_RMS
        )

        # --- Silence / noise ---
        if rms < speech_threshold:
            self.speech_frame_count = 0
            return

        # --- Speech detected ---
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
    # SILENCE WATCHER
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
    # RECEIVE LOOP
    # -------------------------------------------------
    async def _receive_loop(self):
        async for msg in self.socket:
            await self._handle_event(json.loads(msg))

    async def _handle_event(self, data: dict):
        etype = data.get("type")

        if etype == "response.created":
            self.assistant_speaking = True
            self.speech_frame_count = 0

        elif etype == "response.audio.delta":
            pcm24k = base64.b64decode(data["delta"])
            pcm8k, self._resample_down = audioop.ratecv(
                pcm24k, 2, 1, 24000, 8000, self._resample_down
            )
            ulaw = audioop.lin2ulaw(pcm8k, 2)

            if self.send_audio_callback:
                await self.send_audio_callback(base64.b64encode(ulaw).decode())

        elif etype in ("response.done", "response.audio.done"):
            self.assistant_speaking = False

        elif etype == "conversation.item.input_audio_transcription.completed":
            user_text = data.get("transcript", "").strip()
            if not user_text:
                return

            self.transcript.append({"role": "user", "content": user_text})

            context = await self.rag.retrieve(user_text)

            prompt = f"""
{REAL_ESTATE_ASSISTANT_PROMPT}

Context:
{context}

User: {user_text}
"""

            await self.socket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "text", "text": prompt}],
                },
            }))

            await self.socket.send(json.dumps({
                "type": "response.create",
                "response": {"modalities": ["audio"]},
            }))

    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------
    def set_on_audio_delta(self, cb: Callable[[str], None]):
        self.send_audio_callback = cb

    async def close(self):
        self.is_connected = False
        if self.socket:
            await self.socket.close()

    def get_transcript(self) -> str:
        return "\n".join(
            f"{m['role']}: {m['content']}"
            for m in self.transcript
            if m.get("content")
        )
