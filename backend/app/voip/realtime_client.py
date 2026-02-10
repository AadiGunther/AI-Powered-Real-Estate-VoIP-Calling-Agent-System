import asyncio
import json
import base64
import time
from typing import Optional, Callable

import websockets
import audioop
from twilio.rest import Client as TwilioClient

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
BARGE_IN_FRAMES = 8
BARGE_IN_MULTIPLIER = 2.5

SILENCE_COMMIT_DELAY = 1.1
PING_INTERVAL = 20
PING_TIMEOUT = 10


class RealtimeClient:
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.socket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self._noise_floor_rms: Optional[float] = None
        self._noise_frames_collected = 0

        self.send_audio_callback: Optional[Callable[[str], None]] = None
        self.send_json_callback: Optional[Callable[[dict], None]] = None

        self.assistant_speaking = False
        self.last_assistant_item: Optional[str] = None
        self._assistant_speech_started_at: Optional[float] = None
        self._barge_in_frames: int = 0
        
        self.transcript = []
        self.rag = RAGService()
        self.preferred_language: Optional[str] = None
        self.active_question: bool = False
        self._closing_timer: Optional[asyncio.Task] = None
        self._closing_started_at: Optional[float] = None
        self._last_user_speech_at: Optional[float] = None
        self.awaiting_budget_answer: bool = False
        self.budget_value: Optional[str] = None
        self._last_user_utterance: Optional[str] = None

    # -------------------------
    async def connect(self):
        # Handle both full URL from .env or base endpoint
        endpoint = settings.azure_realtime_openai_endpoint
        
        if "openai/realtime" in endpoint:
            # Full URL provided
            url = endpoint.replace("https://", "wss://")
        else:
            # Base endpoint provided
            base_url = endpoint.rstrip("/").replace("https://", "wss://")
            url = (
                f"{base_url}/openai/realtime"
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
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.6,
                    "silence_duration_ms": 900,
                    "create_response": False,
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "end_call",
                        "description": "End the call immediately. Use this ONLY when the caller clearly says goodbye, asks to end the call, or indicates they want to disconnect.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "type": "function",
                        "name": "transfer_call",
                        "description": "Transfer the call to a human agent when the user is unsatisfied or asks for an executive.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Reason for transfer"}
                            },
                            "required": ["reason"]
                        }
                    }
                ],
                "tool_choice": "auto",
                "input_audio_transcription": {"model": "whisper-1"},
            },
        }))

    # -------------------------
    async def send_initial_greeting(self, greeting_text: str):
        await self.socket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"As Riya, a Hindi-speaking solar sales consultant for Ujjwal Energies, greet the caller by saying: '{greeting_text}'. Then pause and wait for their response."
                    }
                ]
            }
        }))
        await self.socket.send(json.dumps({
            "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                },
        }))
        self.active_question = True

    # -------------------------
    async def send_audio(self, audio_b64: str):
        if not self.is_connected or self.assistant_speaking:
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
                self._assistant_speech_started_at = time.time()
                self._barge_in_frames = 0

            if data.get("item_id"):
                self.last_assistant_item = data["item_id"]

            if self.send_audio_callback:
                await self.send_audio_callback(data["delta"])

        elif etype == "response.audio.done":
             self.assistant_speaking = False
             self._assistant_speech_started_at = None
             self._barge_in_frames = 0

        elif etype == "response.audio_transcript.done":
            transcript = data.get("transcript", "").strip()
            if transcript:
                logger.info("assistant_speech_transcribed", text=transcript)
                self.transcript.append({"role": "assistant", "content": transcript})
                lower = transcript.lower()
                if "budget" in lower and ("what" in lower or "approximate" in lower or "range" in lower):
                    self.awaiting_budget_answer = True

        elif etype == "response.done":
            # Overall response done
            self.assistant_speaking = False
            
            # Check for function calls in the response items
            output = data.get("response", {}).get("output", [])
            for item in output:
                if item.get("type") == "function_call":
                    name = item.get("name")
                    args = item.get("arguments", "{}")
                    try:
                        args_dict = json.loads(args)
                        await self._handle_tool_call(name, args_dict)
                    except json.JSONDecodeError:
                        logger.error("tool_call_args_error", args=args)

        elif etype == "input_audio_buffer.speech_started":
            logger.info("speech_started")
            await self._handle_speech_started()

        elif etype == "conversation.item.input_audio_transcription.completed":
            user_text = data.get("transcript", "").strip()
            if not user_text:
                return

            logger.info("user_speech_transcribed", text=user_text)
            self._last_user_utterance = user_text.lower()
            self.transcript.append({"role": "user", "content": user_text})
            now = time.time()
            self._last_user_speech_at = now
            if self._closing_started_at is not None and now > self._closing_started_at:
                self._closing_started_at = None
                if self._closing_timer and not self._closing_timer.done():
                    self._closing_timer.cancel()

            if self.awaiting_budget_answer:
                self.budget_value = user_text
                self.awaiting_budget_answer = False

            if self.active_question:
                augmented_text = f"This is my answer to your previous question: {user_text}"
                self.active_question = False
            else:
                augmented_text = user_text

            try:
                context = await asyncio.wait_for(self.rag.retrieve(user_text), timeout=0.7)
            except Exception:
                context = ""

            if self.budget_value:
                memory_text = (
                    f"The user has already provided their budget as: {self.budget_value}. "
                    f"Do not ask for the budget again unless the user explicitly changes it. "
                    f"If properties are above or below this budget, suggest suitable alternatives "
                    f"while keeping this budget as the reference."
                )
                await self.socket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "system",
                        "content": [{
                            "type": "input_text",
                            "text": memory_text,
                        }],
                    },
                }))

            # 1. Send RAG Context (if any) as a System/Assistant injection invisible to user
            if context:
                await self.socket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "system",
                        "content": [{
                            "type": "input_text",
                            "text": (
                                "You are Riya, a Hindi-speaking solar energy sales consultant for Ujjwal Energies. "
                                "Your voice and tone must always sound like a soft, clearly feminine, friendly young woman, and you must not change away from this feminine style at any point in the call. "
                                "Speak in a calm, gentle voice in Hindi or natural Hinglish, sounding warm, respectful, and patient, never rushed or aggressive. "
                                "You must never stay silent after the customer speaks: for every user message, always reply with at least a short acknowledgement in Hindi and, when appropriate, the next relevant question from your checklist. "
                                "Whenever the customer asks a question, first answer it clearly in Hindi or Hinglish before asking your next question. "
                                f"Use this additional context when answering: {context}"
                            )
                        }],
                    },
                }))

            # 2. Send User Message proper
            await self.socket.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": augmented_text
                    }],
                },
            }))

            await self.socket.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                },
            }))
            self.active_question = True

    async def _schedule_call_end(self):
        start_time = time.time()
        self._closing_started_at = start_time
        if self._closing_timer and not self._closing_timer.done():
            self._closing_timer.cancel()

        async def wait_and_end(expected_start: float):
            try:
                await asyncio.sleep(3)
                if self._closing_started_at != expected_start:
                    return
                if self._last_user_speech_at and self._last_user_speech_at > expected_start:
                    return
                await self._end_twilio_call()
            except asyncio.CancelledError:
                return

        self._closing_timer = asyncio.create_task(wait_and_end(start_time))

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

    # -------------------------
    # TOOL HANDLING
    # -------------------------
    async def _handle_tool_call(self, name: str, args: dict):
        logger.info("tool_call_triggered", name=name, args=args)
        
        if name == "end_call":
            logger.info("end_call_ignored_temporarily", reason="auto_call_cutoff_disabled")
            return
        elif name == "transfer_call":
            await self._transfer_twilio_call()

    async def _end_twilio_call(self):
        try:
            client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            await asyncio.to_thread(
                client.calls(self.call_sid).update, status="completed"
            )
            logger.info("call_ended_via_tool")
        except Exception as e:
            logger.error("end_call_failed", error=str(e))

    async def _transfer_twilio_call(self):
        try:
            # Transfer to the configured phone number or fallback to default
            target_number = settings.twilio_phone_number
            twiml = f"<Response><Say>Please wait while we connect you with our executive.</Say><Dial>{target_number}</Dial></Response>"
            
            client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            await asyncio.to_thread(
                client.calls(self.call_sid).update, twiml=twiml
            )
            logger.info("call_transferred_via_tool")
        except Exception as e:
            logger.error("transfer_call_failed", error=str(e))

    def _calculate_rms(self, audio_bytes: bytes) -> int:
        return audioop.rms(self._mulaw_to_pcm(audio_bytes), 2)

    def _mulaw_to_pcm(self, audio_bytes: bytes) -> bytes:
        return audioop.ulaw2lin(audio_bytes, 2)

    def _reset_noise_floor(self):
        self._noise_floor_rms = None
        self._noise_frames_collected = 0

    def _update_noise_floor(self, rms: int):
        if rms <= 0:
            return
        if self._noise_floor_rms is None:
            self._noise_floor_rms = rms
            self._noise_frames_collected = 1
            return
        if self._noise_frames_collected >= NOISE_LEARN_FRAMES:
            alpha = 0.1
            self._noise_floor_rms = int(self._noise_floor_rms * (1 - alpha) + rms * alpha)
        else:
            total = self._noise_floor_rms * self._noise_frames_collected + rms
            self._noise_frames_collected += 1
            self._noise_floor_rms = int(total / self._noise_frames_collected)

    def _can_end_call_from_tool(self) -> bool:
        if not self._last_user_utterance:
            return False
        text = self._last_user_utterance
        goodbye_markers = [
            "thank you",
            "thanks",
            "goodbye",
            "good bye",
            "bye",
            "bye bye",
            "theek hai",
            "thik hai",
            "rakhta hoon",
            "rakhti hoon",
            "rakhte hain",
            "call cut",
            "band kar",
            "shukriya",
            "dhanyavaad",
        ]
        return any(marker in text for marker in goodbye_markers)
