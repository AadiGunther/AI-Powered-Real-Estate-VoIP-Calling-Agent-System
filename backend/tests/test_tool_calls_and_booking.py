import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.calls import (
    ToolBookAppointmentRequest,
    tool_book_appointment,
)
from app.config import settings
from app.database import async_session_maker
from app.models.appointment import Appointment
from app.models.call import Call, CallDirection, CallStatus
from app.models.enquiry import Enquiry, EnquiryType
from app.models.lead import Lead, LeadQuality, LeadSource, LeadStatus


@pytest.mark.asyncio
async def test_tool_book_appointment_creates_records_and_returns_success():
    async with async_session_maker() as db:  # type: AsyncSession
        ts = int(time.time() * 1000)
        lead = Lead(
            name="Test Lead",
            phone=f"+1555{ts % 10000000000:010d}",
            email=f"lead_{ts}@example.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(lead)
        await db.flush()

        call = Call(
            call_sid=f"TEST_BOOK_APPOINTMENT_CALL_{ts}",
            from_number=settings.twilio_phone_number,
            to_number=lead.phone,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.COMPLETED.value,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ended_at=datetime.now(timezone.utc),
            duration_seconds=300,
        )
        db.add(call)
        await db.commit()

        scheduled_for = datetime.now(timezone.utc) + timedelta(days=1)

        payload = ToolBookAppointmentRequest(
            lead_id=lead.id,
            scheduled_for=scheduled_for,
            address="123 Test Street",
            notes="Test site visit",
            call_id=call.id,
            external_call_id=None,
        )

        response = await tool_book_appointment(payload=payload, db=db, api_key="test-key")

        assert response.success is True
        assert response.lead_id == lead.id
        assert response.enquiry_id is not None

        result_appt = await db.execute(
            select(Appointment).where(
                Appointment.call_id == call.id,
                Appointment.lead_id == lead.id,
            )
        )
        appointment = result_appt.scalar_one()

        appt_dt = appointment.scheduled_for
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=timezone.utc)
        assert appt_dt == scheduled_for
        assert appointment.address == "123 Test Street"

        result_enquiry = await db.execute(
            select(Enquiry).where(
                Enquiry.call_id == call.id,
                Enquiry.lead_id == lead.id,
                Enquiry.enquiry_type == EnquiryType.SITE_VISIT.value,
            )
        )
        enquiry = result_enquiry.scalar_one()

        assert enquiry.id == response.enquiry_id
        assert enquiry.response_successful is True


@pytest.mark.asyncio
async def test_tool_book_appointment_creates_call_when_external_id_provided():
    async with async_session_maker() as db:  # type: AsyncSession
        ts = int(time.time() * 1000)
        lead = Lead(
            name="Test Lead",
            phone=f"+1555{(ts + 1) % 10000000000:010d}",
            email=f"lead2_{ts}@example.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(lead)
        await db.flush()

        external_call_id = f"TEST_BOOK_APPOINTMENT_CREATE_CALL_{ts}"
        scheduled_for = datetime.now(timezone.utc) + timedelta(days=2)

        payload = ToolBookAppointmentRequest(
            lead_id=lead.id,
            scheduled_for=scheduled_for,
            address="456 Another Street",
            notes="Auto-create call test",
            call_id=None,
            external_call_id=external_call_id,
        )

        response = await tool_book_appointment(payload=payload, db=db, api_key="test-key")

        assert response.success is True
        assert response.lead_id == lead.id
        assert response.enquiry_id is not None

        result_call = await db.execute(select(Call).where(Call.call_sid == external_call_id))
        created_call = result_call.scalar_one()

        result_appt = await db.execute(
            select(Appointment).where(
                Appointment.call_id == created_call.id,
                Appointment.lead_id == lead.id,
            )
        )
        appointment = result_appt.scalar_one()
        appt_dt = appointment.scheduled_for
        if appt_dt.tzinfo is None:
            appt_dt = appt_dt.replace(tzinfo=timezone.utc)
        assert appt_dt == scheduled_for
        assert appointment.address == "456 Another Street"

        result_enquiry = await db.execute(
            select(Enquiry).where(
                Enquiry.call_id == created_call.id,
                Enquiry.lead_id == lead.id,
                Enquiry.enquiry_type == EnquiryType.SITE_VISIT.value,
            )
        )
        enquiry = result_enquiry.scalar_one()

        assert enquiry.id == response.enquiry_id
