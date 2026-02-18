import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.api.calls import list_calls
from app.api.dashboard import get_recent_calls
from app.database import async_session_maker
from app.models.call import Call, CallStatus
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_calls_list_returns_exact_calls_table_from_to_numbers():
    async with async_session_maker() as db:
        call_sid = f"TEST_CALLS_LIST_NUMBERS_{int(time.time() * 1000)}"
        expected_from = "+10000000001"
        expected_to = "+20000000001"

        call = Call(
            call_sid=call_sid,
            from_number=expected_from,
            to_number=expected_to,
            direction="outbound",
            status=CallStatus.IN_PROGRESS.value,
            started_at=datetime.now(timezone.utc),
            handled_by_ai=True,
        )
        db.add(call)
        await db.commit()
        await db.refresh(call)

        current_user = User(
            email=f"test_{call_sid}@example.com",
            hashed_password="unused",
            full_name="Test Admin",
            role=UserRole.ADMIN.value,
            is_active=True,
            is_verified=True,
        )

        response = await list_calls(
            page=1,
            page_size=50,
            direction=None,
            status=None,
            outcome=None,
            handled_by_ai=None,
            escalated=None,
            from_number=None,
            lead_id=None,
            date_from=None,
            date_to=None,
            db=db,
            current_user=current_user,
        )

        returned = next((c for c in response.calls if c.call_sid == call_sid), None)
        assert returned is not None
        assert returned.from_number == expected_from
        assert returned.to_number == expected_to


@pytest.mark.asyncio
async def test_dashboard_recent_calls_returns_exact_calls_table_from_to_numbers():
    async with async_session_maker() as db:
        call_sid = f"TEST_DASH_RECENT_NUMBERS_{int(time.time() * 1000)}"
        expected_from = "+10000000002"
        expected_to = "+20000000002"

        call = Call(
            call_sid=call_sid,
            from_number=expected_from,
            to_number=expected_to,
            direction="inbound",
            status=CallStatus.RINGING.value,
            started_at=datetime.now(timezone.utc),
            handled_by_ai=True,
        )
        db.add(call)
        await db.commit()

    recent = await get_recent_calls(limit=50)
    returned = next((c for c in recent if c.call_sid == call_sid), None)
    assert returned is not None
    assert returned.from_number == expected_from
    assert returned.to_number == expected_to


@pytest.mark.asyncio
async def test_calls_table_values_are_not_rewritten_by_api_layer():
    async with async_session_maker() as db:
        call_sid = f"TEST_CALLS_FROM_TO_INTEGRITY_{int(time.time() * 1000)}"
        expected_from = "+10000000003"
        expected_to = "+20000000003"

        call = Call(
            call_sid=call_sid,
            from_number=expected_from,
            to_number=expected_to,
            direction="outbound",
            status=CallStatus.COMPLETED.value,
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            duration_seconds=1,
            handled_by_ai=False,
        )
        db.add(call)
        await db.commit()

        current_user = User(
            email=f"test_{call_sid}@example.com",
            hashed_password="unused",
            full_name="Test Admin",
            role=UserRole.ADMIN.value,
            is_active=True,
            is_verified=True,
        )

        _ = await list_calls(
            page=1,
            page_size=50,
            direction=None,
            status=None,
            outcome=None,
            handled_by_ai=None,
            escalated=None,
            from_number=None,
            lead_id=None,
            date_from=None,
            date_to=None,
            db=db,
            current_user=current_user,
        )

        persisted = (await db.execute(select(Call).where(Call.call_sid == call_sid))).scalar_one()
        assert persisted.from_number == expected_from
        assert persisted.to_number == expected_to
