import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.user import User, UserRole
from app.models.lead import Lead, LeadSource, LeadQuality, LeadStatus
from app.models.notification import Notification, NotificationType
from app.models.audit_log import AuditLog, AuditAction
from app.api.leads import assign_lead, bulk_assign_leads
from app.schemas.lead import LeadAssign, LeadBulkAssign


@pytest.mark.asyncio
async def test_assign_lead_happy_path():
    async with async_session_maker() as db:  # type: AsyncSession
        manager = User(
            email="manager_assign@test.com",
            full_name="Manager Assign",
            phone="+10000000001",
            role=UserRole.MANAGER.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        agent = User(
            email="agent_assign@test.com",
            full_name="Agent Assign",
            phone="+10000000002",
            role=UserRole.AGENT.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        lead = Lead(
            name="Assign Lead",
            phone="+19990000000",
            email="assign.lead@test.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(manager)
        db.add(agent)
        db.add(lead)
        await db.commit()
        await db.refresh(manager)
        await db.refresh(agent)
        await db.refresh(lead)

        payload = LeadAssign(agent_id=agent.id)
        result = await assign_lead(
            lead_id=lead.id,
            request=payload,
            db=db,
            current_user=manager,
        )

        assert result.assigned_agent_id == agent.id
        assert result.assigned_at is not None

        notif_result = await db.execute(
            select(Notification).where(
                Notification.user_id == agent.id,
                Notification.type == NotificationType.LEAD_ASSIGNED.value,
                Notification.related_lead_id == lead.id,
            )
        )
        notification = notif_result.scalar_one_or_none()
        assert notification is not None

        audit_result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_id == lead.id,
                AuditLog.action == AuditAction.LEAD_ASSIGNED.value,
            )
        )
        audit = audit_result.scalar_one_or_none()
        assert audit is not None


@pytest.mark.asyncio
async def test_assign_lead_rejects_inactive_agent():
    async with async_session_maker() as db:  # type: AsyncSession
        manager = User(
            email="manager_inactive@test.com",
            full_name="Manager Inactive",
            phone="+10000000003",
            role=UserRole.MANAGER.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        agent = User(
            email="agent_inactive@test.com",
            full_name="Agent Inactive",
            phone="+10000000004",
            role=UserRole.AGENT.value,
            hashed_password="x",
            is_active=False,
            is_verified=True,
        )
        lead = Lead(
            name="Inactive Agent Lead",
            phone="+19990000001",
            email="inactive.lead@test.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(manager)
        db.add(agent)
        db.add(lead)
        await db.commit()
        await db.refresh(manager)
        await db.refresh(agent)
        await db.refresh(lead)

        payload = LeadAssign(agent_id=agent.id)

        with pytest.raises(Exception):
            await assign_lead(
                lead_id=lead.id,
                request=payload,
                db=db,
                current_user=manager,
            )


@pytest.mark.asyncio
async def test_bulk_assign_leads_happy_path():
    async with async_session_maker() as db:  # type: AsyncSession
        manager = User(
            email="manager_bulk@test.com",
            full_name="Manager Bulk",
            phone="+10000000005",
            role=UserRole.MANAGER.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        agent = User(
            email="agent_bulk@test.com",
            full_name="Agent Bulk",
            phone="+10000000006",
            role=UserRole.AGENT.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        leads = [
            Lead(
                name=f"Bulk Lead {i}",
                phone=f"+1888000000{i}",
                email=f"bulk{i}@test.com",
                source=LeadSource.OUTBOUND_CALL.value,
                quality=LeadQuality.COLD.value,
                status=LeadStatus.NEW.value,
            )
            for i in range(3)
        ]

        db.add(manager)
        db.add(agent)
        for lead in leads:
            db.add(lead)
        await db.commit()
        for lead in leads:
            await db.refresh(lead)

        payload = LeadBulkAssign(
            agent_id=agent.id,
            lead_ids=[lead.id for lead in leads],
        )

        result = await bulk_assign_leads(
            request=payload,
            db=db,
            current_user=manager,
        )

        assert result.total == len(leads)
        for lead in result.leads:
            assert lead.assigned_agent_id == agent.id


@pytest.mark.asyncio
async def test_bulk_assign_leads_rejects_missing_leads():
    async with async_session_maker() as db:  # type: AsyncSession
        manager = User(
            email="manager_bulk_missing@test.com",
            full_name="Manager Bulk Missing",
            phone="+10000000007",
            role=UserRole.MANAGER.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        agent = User(
            email="agent_bulk_missing@test.com",
            full_name="Agent Bulk Missing",
            phone="+10000000008",
            role=UserRole.AGENT.value,
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        lead = Lead(
            name="Existing Lead",
            phone="+17770000000",
            email="existing@test.com",
            source=LeadSource.OUTBOUND_CALL.value,
            quality=LeadQuality.COLD.value,
            status=LeadStatus.NEW.value,
        )
        db.add(manager)
        db.add(agent)
        db.add(lead)
        await db.commit()
        await db.refresh(manager)
        await db.refresh(agent)
        await db.refresh(lead)

        payload = LeadBulkAssign(
            agent_id=agent.id,
            lead_ids=[lead.id, 999999],
        )

        with pytest.raises(Exception):
            await bulk_assign_leads(
                request=payload,
                db=db,
                current_user=manager,
            )

