import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.elevenlabs_webhook import _upsert_call_by_sid
from app.database import async_session_maker
from app.models.call import Call, CallStatus


@pytest.mark.asyncio
async def test_status_does_not_downgrade_from_completed_to_in_progress():
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"TEST_COMPLETED_{int(time.time() * 1000)}"
        call = Call(
            call_sid=call_sid,
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

        await _upsert_call_by_sid(
            db,
            {
                "call_sid": call_sid,
                "status": CallStatus.IN_PROGRESS.value,
            },
        )
        await db.commit()

        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
        updated = result.scalar_one()
        assert updated.status == CallStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_status_moves_to_completed_and_sets_end_fields():
    async with async_session_maker() as db:  # type: AsyncSession
        call_sid = f"TEST_TO_COMPLETE_{int(time.time() * 1000)}"
        start = datetime.now(timezone.utc) - timedelta(seconds=42)
        call = Call(
            call_sid=call_sid,
            from_number="+10000000001",
            to_number="+20000000001",
            direction="outbound",
            status=CallStatus.IN_PROGRESS.value,
            started_at=start,
        )
        db.add(call)
        await db.commit()

        await _upsert_call_by_sid(
            db,
            {
                "call_sid": call_sid,
                "status": CallStatus.COMPLETED.value,
                "ended_at": datetime.now(timezone.utc),
                "duration_seconds": 42,
            },
        )
        await db.commit()

        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
        updated = result.scalar_one()
        assert updated.status == CallStatus.COMPLETED.value
        assert updated.ended_at is not None
        assert updated.duration_seconds == 42
