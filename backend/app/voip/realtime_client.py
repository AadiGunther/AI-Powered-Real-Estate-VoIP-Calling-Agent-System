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
        self.preferred_language: Optional[str] = None
        self.active_question: bool = False

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
                "voice": "shimmer",
                "input_audio_format": "g711_ulaw",  # Direct from Twilio
                "output_audio_format": "g711_ulaw", # Direct for Twilio
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.6,
                    "silence_duration_ms": 1000,
                    "create_response": False, # Manual trigger after RAG
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "end_call",
                        "description": "End the call immediately after the user says goodbye or when the conversation is finished.",
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
        """Send the initial greeting as if it were a user instruction to the AI."""
        await self.socket.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"As Sophia, greet the caller by saying: '{greeting_text}'. Then pause and wait for their response."
                    }
                ]
            }
        }))
        await self.socket.send(json.dumps({
            "type": "response.create",
            "response": {"modalities": ["text", "audio"]},
        }))
        self.active_question = True

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

        elif etype == "response.audio.done":
             # End of audio stream for this item
             self.assistant_speaking = False

        elif etype == "response.audio_transcript.done":
            # Capture assistant's spoken response
            transcript = data.get("transcript", "").strip()
            if transcript:
                logger.info("assistant_speech_transcribed", text=transcript)
                self.transcript.append({"role": "assistant", "content": transcript})

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
            self.transcript.append({"role": "user", "content": user_text})

            if self.active_question:
                augmented_text = f"This is my answer to your previous question: {user_text}"
                self.active_question = False
            else:
                augmented_text = user_text

            context = await self.rag.retrieve(user_text)

            # 1. Send RAG Context (if any) as a System/Assistant injection invisible to user
            if context:
                await self.socket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "system",
                        "content": [{
                            "type": "input_text",
                            "text": f"You are Sophia from ABC Real Estate. Stay warm, professional, and consistent in tone. Use this additional context when answering: {context}"
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
                "response": {"modalities": ["text", "audio"]},
            }))
            self.active_question = True

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
            await self._end_twilio_call()
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
