import io
from typing import Optional

from openai import AsyncAzureOpenAI, AsyncOpenAI

from app.config import settings
from app.utils.logging import get_logger


logger = get_logger("services.stt_service")


class STTService:
    def __init__(self):
        if settings.azure_openai_api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_whisper_deployment or "gpt-4o-transcribe"
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o-transcribe"

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        file_name: str = "audio.wav",
    ) -> Optional[str]:
        if not audio_bytes:
            logger.warning("stt_empty_audio")
            return None

        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = file_name

            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
            )
            text = getattr(response, "text", None)
            if not text:
                logger.warning("stt_no_text_returned")
                return None

            logger.info("stt_transcription_success")
            return text

        except Exception as e:
            logger.exception("stt_transcription_failed", error=str(e))
            return None

