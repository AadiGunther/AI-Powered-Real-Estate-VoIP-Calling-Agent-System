from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ElevenLabsEventLog(Base):
    __tablename__ = "elevenlabs_event_log"
    __table_args__ = (
        UniqueConstraint("call_sid", "event_type", "event_timestamp", name="uq_call_event_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_sid: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processed")
    error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

