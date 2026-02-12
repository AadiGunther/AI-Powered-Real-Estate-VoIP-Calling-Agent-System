import base64
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings
from app.utils.logging import get_logger


logger = get_logger("services.elevenlabs_tts")


class ElevenLabsTTS:
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.elevenlabs_api_key
        self.voice_id = voice_id or settings.elevenlabs_voice_id
        self.base_url = base_url or settings.elevenlabs_base_url

    async def synthesize_ulaw_stream(
        self,
        text: str,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key or not self.voice_id:
            logger.error("elevenlabs_tts_disabled_missing_config")
            return

        url = f"{self.base_url.rstrip('/')}/v1/text-to-speech/{self.voice_id}?output_format=ulaw_8000"

        headers = {
            "xi-api-key": self.api_key,
            "Accept": "application/octet-stream",
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "voice_settings": {
                "stability": 0.6,
                "similarity_boost": 0.9,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            logger.error("elevenlabs_tts_request_failed", error=str(e))
            return

        if resp.status_code != 200:
            logger.error(
                "elevenlabs_tts_bad_status",
                status=resp.status_code,
            )
            return

        ulaw_bytes = resp.content

        chunk_size = 160
        for i in range(0, len(ulaw_bytes), chunk_size):
            chunk = ulaw_bytes[i : i + chunk_size]
            if not chunk:
                continue
            encoded = base64.b64encode(chunk).decode("ascii")
            yield encoded
