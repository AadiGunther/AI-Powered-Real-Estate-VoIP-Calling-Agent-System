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

        self.assistant_speaking = False
        self.buffer_committed = True
        self.last_audio_rx_ts = 0.0

        self.speech_frame_count = 0
        self.barge_frames = 0

        self.noise_floor = 0.0
        self.noise_samples = 0

        self._resample_up = None
        self._resample_down = None

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
        asyncio.create_task(self._silence_watcher())

        logger.info("realtime_connected", call_sid=self.call_sid)

    # -------------------------
    async def update_session(self, instructions: str):
        await self.socket.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["audio"],
                "instructions": instructions,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "interruptible": True,
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.65,
                    "silence_duration_ms": 1100,
                    "create_response": True,
                },
                "input_audio_transcription": {"model": "whisper-1"},
            },
        }))

    # -------------------------
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

    # -------------------------
    async def send_audio(self, audio_b64: str):
        if not self.is_connected:
            return

        ulaw = base64.b64decode(audio_b64)
        pcm8k = audioop.ulaw2lin(ulaw, 2)
        rms = audioop.rms(pcm8k, 2)

        # -------------------------
        # AI speaking → barge-in only
        # -------------------------
        if self.assistant_speaking:
            threshold = max(self.noise_floor * NOISE_MULTIPLIER, ABSOLUTE_MIN_RMS)
            if rms > threshold * BARGE_IN_MULTIPLIER:
                self.barge_frames += 1
            else:
                self.barge_frames = 0

            if self.barge_frames >= BARGE_IN_FRAMES:
                await self._interrupt_assistant()
            return

        # -------------------------
        # Noise learning
        # -------------------------
        if self.noise_samples < NOISE_LEARN_FRAMES and rms < ABSOLUTE_MIN_RMS * 1.2:
            self.noise_floor = (
                (self.noise_floor * self.noise_samples) + rms
            ) / (self.noise_samples + 1)
            self.noise_samples += 1
            return

        threshold = max(self.noise_floor * NOISE_MULTIPLIER, ABSOLUTE_MIN_RMS)

        if rms < threshold:
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

    # -------------------------
    async def _interrupt_assistant(self):
        logger.info("barge_in", call_sid=self.call_sid)

        self.assistant_speaking = False
        self.barge_frames = 0
        self.buffer_committed = True

        await self.socket.send(json.dumps({"type": "response.cancel"}))

    # -------------------------
    async def _silence_watcher(self):
        while self.is_connected:
            await asyncio.sleep(0.15)

            if self.assistant_speaking or self.buffer_committed:
                continue

            if time.time() - self.last_audio_rx_ts > SILENCE_COMMIT_DELAY:
                await self.socket.send(json.dumps({
                    "type": "input_audio_buffer.commit"
                }))
                self.buffer_committed = True
                self.speech_frame_count = 0

    # -------------------------
    async def _receive_loop(self):
        async for msg in self.socket:
            await self._handle_event(json.loads(msg))

    async def _handle_event(self, data: dict):
        etype = data.get("type")

        if etype == "response.audio.delta":
            if not self.assistant_speaking:
                self.assistant_speaking = True

            pcm24k = base64.b64decode(data["delta"])
            pcm8k, self._resample_down = audioop.ratecv(
                pcm24k, 2, 1, 24000, 8000, self._resample_down
            )
            ulaw = audioop.lin2ulaw(pcm8k, 2)

            if self.send_audio_callback:
                await self.send_audio_callback(base64.b64encode(ulaw).decode())

        elif etype in ("response.done", "response.audio.done"):
            self._reset_after_ai()

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
                        "text": f"{context}\n\nUser: {user_text}"
                    }],
                },
            }))

            await self.socket.send(json.dumps({
                "type": "response.create",
                "response": {"modalities": ["audio"]},
            }))

    # -------------------------
    def _reset_after_ai(self):
        self.assistant_speaking = False
        self.buffer_committed = True
        self.speech_frame_count = 0
        self.last_audio_rx_ts = 0

    # -------------------------
    def set_on_audio_delta(self, cb: Callable[[str], None]):
        self.send_audio_callback = cb

    def get_transcript(self):
        if not self.transcript:
            return None
        return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in self.transcript)

    async def close(self):
        self.is_connected = False
        if self.socket:
            await self.socket.close()