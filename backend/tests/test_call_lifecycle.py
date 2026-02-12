import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import async_session_maker
from app.models.call import Call, CallStatus
from app.api.twilio_webhook import handle_call_status


@pytest.mark.asyncio
async def test_status_does_not_downgrade_from_completed_to_in_progress():
    async with async_session_maker() as db:  # type: AsyncSession
        call = Call(
            call_sid="TEST_COMPLETED",
            from_number="+10000000000",
            to_number="+20000000000",
            direction="outbound",
            status=CallStatus.COMPLETED.value,
            started_at=datetime.now(timezone.utc) - timedelta(seconds=30),
            ended_at=datetime.now(timezone.utc),
            duration_seconds=30,
        )
        db.add(call)
        await db.commit()

        await handle_call_status(
            CallSid="TEST_COMPLETED",
            CallStatusParam="in-progress",
            CallDuration=None,
            RecordingUrl=None,
            RecordingSid=None,
            RecordingDuration=None,
            db=db,
        )

        result = await db.execute(select(Call).where(Call.call_sid == "TEST_COMPLETED"))
        updated = result.scalar_one()
        assert updated.status == CallStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_status_moves_to_completed_and_sets_end_fields():
    async with async_session_maker() as db:  # type: AsyncSession
        start = datetime.now(timezone.utc) - timedelta(seconds=42)
        call = Call(
            call_sid="TEST_TO_COMPLETE",
            from_number="+10000000001",
            to_number="+20000000001",
            direction="outbound",
            status=CallStatus.IN_PROGRESS.value,
            started_at=start,
        )
        db.add(call)
        await db.commit()

        await handle_call_status(
            CallSid="TEST_TO_COMPLETE",
            CallStatusParam="completed",
            CallDuration="42",
            RecordingUrl=None,
            RecordingSid=None,
            RecordingDuration=None,
            db=db,
        )

        result = await db.execute(select(Call).where(Call.call_sid == "TEST_TO_COMPLETE"))
        updated = result.scalar_one()
        assert updated.status == CallStatus.COMPLETED.value
        assert updated.ended_at is not None
        assert updated.duration_seconds == 42

