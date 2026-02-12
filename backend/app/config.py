"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- DATABASE ----------------
    database_url: str
    mongodb_url: str
    mongodb_db: str

    # ---------------- TWILIO ----------------
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    twilio_application_sid: str

    # ---------------- OPENAI (fallback / reports) ----------------
    openai_api_key: str = ""  # Optional fallback
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = ""

    # ---------------- AZURE REALTIME (voice agent) ----------------
    azure_realtime_openai_api_key: str
    azure_realtime_openai_endpoint: str
    azure_openai_realtime_deployment: str
    azure_openai_realtime_api_version: str

    # ---------------- AUTH ----------------
    jwt_secret: str
    jwt_algorithm: str
    jwt_expire_minutes: int

    # ---------------- APP ----------------
    app_name: str
    app_version: str
    debug: bool
    base_url: str
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-10-01"

    cors_origins: List[str] = []
    recordings_dir: str

    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "call-recordings"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    use_elevenlabs_tts: bool = False

    @computed_field
    @property
    def websocket_url(self) -> str:
        if not self.base_url:
            return ""
        # Replace http/https with ws/wss and append /media-stream
        ws_base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_base}/media-stream"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
