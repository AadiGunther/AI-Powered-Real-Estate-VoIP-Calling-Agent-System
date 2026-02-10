#!/usr/bin/env python3
"""Seed script for populating database with dummy data."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select

from app.database import async_session_maker, init_db, MongoDB
from app.models.user import User, UserRole
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.lead import Lead, LeadSource, LeadQuality, LeadStatus
from app.utils.security import get_password_hash


async def seed_users():
    """Create default users."""
    async with async_session_maker() as db:
        result = await db.execute(select(User.email))
        existing_emails = {row[0] for row in result.all()}

        users = [
            User(
                email="admin@abcrealestate.com",
                full_name="Admin User",
                phone="+919876543210",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN.value,
                is_active=True,
                is_verified=True,
            ),
            User(
                email="manager@abcrealestate.com",
                full_name="Sales Manager",
                phone="+919876543211",
                hashed_password=get_password_hash("manager123"),
                role=UserRole.MANAGER.value,
                is_active=True,
                is_verified=True,
            ),
            User(
                email="agent1@abcrealestate.com",
                full_name="Rahul Sharma",
                phone="+919876543212",
                hashed_password=get_password_hash("agent123"),
                role=UserRole.AGENT.value,
                is_active=True,
                is_verified=True,
            ),
            User(
                email="agent2@abcrealestate.com",
                full_name="Priya Patel",
                phone="+919876543213",
                hashed_password=get_password_hash("agent123"),
                role=UserRole.AGENT.value,
                is_active=True,
                is_verified=True,
            ),
        ]
        
        for user in users:
            if user.email in existing_emails:
                continue
            db.add(user)
        
        await db.commit()
        print(f"✓ Created {len(users)} users")


async def seed_properties():
    """Create sample solar-focused products (not tied to specific cities)."""
    async with async_session_maker() as db:
        await db.execute(delete(Property))
        await db.commit()

        properties = [
            Property(
                title="2kW Residential Starter Rooftop Solar Plan",
                description="2kW on-grid residential rooftop solar system suitable for small homes with light to moderate daytime usage.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=110000,
                price_per_sqft=5500,
                size_sqft=200,
                bedrooms=0,
                bathrooms=0,
                address="Standard 2kW Residential Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "2kW Rooftop Solar",
                    "On-grid System",
                    "Mono PERC Panels",
                    "String Inverter",
                    "Basic Monitoring",
                    "Eligible for Residential Subsidy (as per policy)",
                ]),
                images=json.dumps(["solar_residential_2kw.jpg"]),
                is_featured=False,
                created_by=1,
            ),
            Property(
                title="3kW Residential Value Rooftop Solar Plan",
                description="3kW on-grid rooftop solar system for typical 2–3 BHK homes, designed to offset a major part of monthly electricity bills.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=165000,
                price_per_sqft=5500,
                size_sqft=300,
                bedrooms=0,
                bathrooms=0,
                address="Standard 3kW Residential Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "3kW Rooftop Solar",
                    "On-grid System",
                    "High Efficiency Panels",
                    "String Inverter",
                    "Net Metering Ready",
                    "Approximate Payback 4–5 Years (varies by usage and tariff)",
                ]),
                images=json.dumps(["solar_residential_3kw.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="5kW Residential Premium Rooftop Solar Plan",
                description="5kW on-grid rooftop solar system for larger independent homes with higher consumption, suitable for heavy appliance usage.",
                property_type=PropertyType.VILLA.value,
                status=PropertyStatus.AVAILABLE.value,
                price=260000,
                price_per_sqft=5200,
                size_sqft=450,
                bedrooms=0,
                bathrooms=0,
                address="Standard 5kW Residential Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "5kW Rooftop Solar",
                    "On-grid System",
                    "Mono PERC Panels",
                    "String Inverter",
                    "Net Metering Ready",
                    "Optional Battery Integration",
                ]),
                images=json.dumps(["solar_residential_5kw.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="10kW Small Commercial Rooftop Solar Plan",
                description="10kW rooftop solar system for small offices, shops, and showrooms operating mainly during daytime business hours.",
                property_type=PropertyType.COMMERCIAL.value,
                status=PropertyStatus.AVAILABLE.value,
                price=480000,
                price_per_sqft=4800,
                size_sqft=900,
                bedrooms=0,
                bathrooms=0,
                address="Standard 10kW Commercial Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "10kW Rooftop Solar",
                    "Commercial Net Metering",
                    "Remote Monitoring",
                    "String Inverters",
                    "Designed for Small Commercial Loads",
                ]),
                images=json.dumps(["solar_commercial_10kw.jpg"]),
                is_featured=False,
                created_by=1,
            ),
            Property(
                title="15kW–20kW Medium Commercial Rooftop Solar Plan",
                description="15–20kW rooftop solar system for mid-size offices, showrooms, and coaching institutes with consistent daytime load.",
                property_type=PropertyType.OFFICE.value,
                status=PropertyStatus.AVAILABLE.value,
                price=900000,
                price_per_sqft=4500,
                size_sqft=1500,
                bedrooms=0,
                bathrooms=0,
                address="Standard 15–20kW Commercial Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "15–20kW Rooftop Solar",
                    "Commercial Net Metering",
                    "Remote Monitoring",
                    "Tier-1 Panels",
                    "String Inverters",
                ]),
                images=json.dumps(["solar_commercial_20kw.jpg"]),
                is_featured=False,
                created_by=1,
            ),
            Property(
                title="25kW Industrial Rooftop Solar Plant",
                description="25kW rooftop solar plant for small industrial units and factories to reduce peak daytime demand and energy cost.",
                property_type=PropertyType.WAREHOUSE.value,
                status=PropertyStatus.AVAILABLE.value,
                price=1150000,
                price_per_sqft=4600,
                size_sqft=2500,
                bedrooms=0,
                bathrooms=0,
                address="Standard 25kW Industrial Rooftop Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "25kW Rooftop Solar",
                    "Industrial Grade Mounting",
                    "String Inverters",
                    "Remote Monitoring",
                    "Designed for Small Industrial Loads",
                ]),
                images=json.dumps(["solar_industrial_25kw.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="3kW Hybrid Residential Solar Plan with Battery Ready",
                description="3kW rooftop solar system designed for hybrid or future battery integration, suitable for areas with frequent power cuts.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=210000,
                price_per_sqft=6000,
                size_sqft=320,
                bedrooms=0,
                bathrooms=0,
                address="Standard 3kW Hybrid-Ready Residential Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "3kW Rooftop Solar",
                    "Hybrid Inverter Ready",
                    "Battery Ready",
                    "Net Metering Compatible",
                ]),
                images=json.dumps(["solar_residential_hybrid_3kw.jpg"]),
                is_featured=False,
                created_by=1,
            ),
            Property(
                title="Rooftop Solar Maintenance & AMC Plan",
                description="Annual maintenance contract for existing rooftop solar plants, including scheduled cleaning, inspection, and performance checks.",
                property_type=PropertyType.COMMERCIAL.value,
                status=PropertyStatus.AVAILABLE.value,
                price=15000,
                price_per_sqft=None,
                size_sqft=0,
                bedrooms=0,
                bathrooms=0,
                address="Rooftop Solar AMC Service Package",
                city="PAN India",
                state="All States",
                pincode="000000",
                latitude=None,
                longitude=None,
                amenities=json.dumps([
                    "Periodic Cleaning",
                    "Performance Inspection",
                    "Inverter Health Check",
                    "Basic Service Support",
                ]),
                images=json.dumps(["solar_amc_service.jpg"]),
                is_featured=False,
                created_by=1,
            ),
        ]
        
        for prop in properties:
            db.add(prop)
        
        await db.commit()
        print(f"✓ Created {len(properties)} properties")


async def seed_leads():
    """Create sample solar leads."""
    async with async_session_maker() as db:
        await db.execute(delete(Lead))
        await db.commit()

        leads = [
            Lead(
                name="Rohan Verma",
                email="rohan.verma@example.com",
                phone="+919876500001",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.HOT.value,
                status=LeadStatus.CONTACTED.value,
                budget_min=150000,
                budget_max=250000,
                preferred_location="Whitefield, Bangalore",
                preferred_property_type="3kW Residential Rooftop Solar",
                notes="Wants to reduce monthly electricity bill and is asking about government subsidy.",
            ),
            Lead(
                name="Priya Nair",
                email="priya.nair@example.com",
                phone="+919876500002",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.WARM.value,
                status=LeadStatus.NEW.value,
                budget_min=250000,
                budget_max=400000,
                preferred_location="Sarjapur Road, Bangalore",
                preferred_property_type="5kW–6kW Residential Solar",
                notes="Exploring options for independent villa. Interested in EMI and subsidy details.",
            ),
            Lead(
                name="Rajesh Menon",
                phone="+919876500003",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.COLD.value,
                status=LeadStatus.NEW.value,
                budget_min=120000,
                budget_max=180000,
                preferred_location="Electronic City, Bangalore",
                preferred_property_type="2kW Starter Solar",
                notes="Very early stage, just collecting information. Wants to know payback period.",
            ),
            Lead(
                name="Sarah Johnson",
                email="sarah.j@startup.com",
                phone="+919876500004",
                source=LeadSource.OUTBOUND_CALL.value,
                quality=LeadQuality.HOT.value,
                status=LeadStatus.QUALIFIED.value,
                budget_min=500000,
                budget_max=700000,
                preferred_location="Indiranagar, Koramangala",
                preferred_property_type="10kW–15kW Commercial Solar",
                notes="Tech startup planning to install solar on office rooftop. Site visit scheduled next week.",
                assigned_agent_id=3,
            ),
            Lead(
                name="Mohammed Ali",
                email="m.ali@factory.com",
                phone="+919876500005",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.WARM.value,
                status=LeadStatus.NEGOTIATING.value,
                budget_min=800000,
                budget_max=1200000,
                preferred_location="Peenya Industrial Area",
                preferred_property_type="25kW Industrial Rooftop Solar",
                notes="Discussed 25kW system for small manufacturing unit. Evaluating ROI and subsidy benefits.",
                assigned_agent_id=4,
            ),
        ]
        
        for lead in leads:
            db.add(lead)
        
        await db.commit()
        print(f"✓ Created {len(leads)} leads")


async def main():
    """Run all seed functions."""
    print("🌱 Starting database seeding...")
    print("-" * 40)
    
    # Initialize database
    await init_db()
    await MongoDB.connect()
    
    try:
        await seed_users()
        await seed_properties()
        await seed_leads()
        
        print("-" * 40)
        print("✅ Database seeding completed successfully!")
        print("\nDefault login credentials:")
        print("  Admin:   admin@abcrealestate.com / admin123")
        print("  Manager: manager@abcrealestate.com / manager123")
        print("  Agents:  agent1@abcrealestate.com / agent123")
        print("           agent2@abcrealestate.com / agent123")
        
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
