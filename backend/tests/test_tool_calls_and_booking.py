import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.config import settings
from app.models.call import Call, CallDirection, CallStatus
from app.models.lead import Lead, LeadSource, LeadQuality, LeadStatus
from app.models.appointment import Appointment
from app.models.enquiry import Enquiry, EnquiryType
from app.api.calls import (
    tool_log_call,
    ToolLogCallRequest,
    tool_book_appointment,
    ToolBookAppointmentRequest,
    tool_start_call,
    ToolStartCallRequest,
)


@pytest.mark.asyncio
async def test_tool_log_call_outbound_from_and_to_numbers():
    async with async_session_maker() as db:  # type: AsyncSession
        external_call_id = "TEST_TOOL_LOG_OUTBOUND"
        start_payload = ToolStartCallRequest(
            external_call_id=external_call_id,
            direction=CallDirection.OUTBOUND,
            from_number=settings.twilio_phone_number,
            to_number="+19998887777",
        )
        start_response = await tool_start_call(payload=start_payload, db=db, api_key="test-key")
        assert start_response.success is True

        payload = ToolLogCallRequest(
            external_call_id=external_call_id,
            phone="+19998887777",
            direction=CallDirection.OUTBOUND,
            status=CallStatus.COMPLETED,
            duration_seconds=60,
        )

        response = await tool_log_call(payload=payload, db=db, api_key="test-key")
        assert response.success is True

        result = await db.execute(select(Call).where(Call.call_sid == external_call_id))
        call = result.scalar_one()

        assert call.from_number == settings.twilio_phone_number
        assert call.to_number == "+19998887777"
        assert call.direction == CallDirection.OUTBOUND.value


@pytest.mark.asyncio
async def test_tool_log_call_inbound_from_and_to_numbers():
    async with async_session_maker() as db:  # type: AsyncSession
        external_call_id = "TEST_TOOL_LOG_INBOUND"
        start_payload = ToolStartCallRequest(
            external_call_id=external_call_id,
            direction=CallDirection.INBOUND,
            from_number="+18887776666",
            to_number=settings.twilio_phone_number,
        )
        start_response = await tool_start_call(payload=start_payload, db=db, api_key="test-key")
        assert start_response.success is True

        payload = ToolLogCallRequest(
            external_call_id=external_call_id,
            phone="+18887776666",
            direction=CallDirection.INBOUND,
            status=CallStatus.COMPLETED,
            duration_seconds=45,
        )

        response = await tool_log_call(payload=payload, db=db, api_key="test-key")
        assert response.success is True

        result = await db.execute(select(Call).where(Call.call_sid == external_call_id))
        call = result.scalar_one()

        assert call.from_number == "+18887776666"
        assert call.to_number == settings.twilio_phone_number
        assert call.direction == CallDirection.INBOUND.value


@pytest.mark.asyncio
async def test_tool_book_appointment_creates_records_and_returns_success():
    async with async_session_maker() as db:  # type: AsyncSession
        lead = Lead(
            name="Test Lead",
            phone="+15550000000",
            email="lead@example.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(lead)
        await db.flush()

        call = Call(
            call_sid="TEST_BOOK_APPOINTMENT_CALL",
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
        assert response.enquiry_id is not None

        result_appt = await db.execute(
            select(Appointment).where(
                Appointment.call_id == call.id,
                Appointment.lead_id == lead.id,
            )
        )
        appointment = result_appt.scalar_one()

        assert appointment.scheduled_for == scheduled_for
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
async def test_tool_book_appointment_requires_existing_call_when_external_id_provided():
    async with async_session_maker() as db:  # type: AsyncSession
        lead = Lead(
            name="Test Lead",
            phone="+15551112222",
            email="lead2@example.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(lead)
        await db.flush()

        external_call_id = "TEST_BOOK_APPOINTMENT_CREATE_CALL"
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

        assert response.success is False
        assert response.enquiry_id is None
