#!/usr/bin/env python3
"""Seed script for populating database with dummy data."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker, init_db, MongoDB
from app.models.user import User, UserRole
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.lead import Lead, LeadSource, LeadQuality, LeadStatus
from app.utils.security import get_password_hash


async def seed_users():
    """Create default users."""
    async with async_session_maker() as db:
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
            db.add(user)
        
        await db.commit()
        print(f"✓ Created {len(users)} users")


async def seed_properties():
    """Create sample properties."""
    async with async_session_maker() as db:
        properties = [
            # Apartments
            Property(
                title="Luxury 3BHK Apartment in Whitefield",
                description="Premium apartment with modern amenities, clubhouse, swimming pool, and 24/7 security.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=8500000,
                price_per_sqft=6500,
                size_sqft=1308,
                bedrooms=3,
                bathrooms=2,
                address="Brigade Meadows, Whitefield",
                city="Bangalore",
                state="Karnataka",
                pincode="560066",
                latitude=12.9716,
                longitude=77.7500,
                amenities=json.dumps(["Swimming Pool", "Gym", "Clubhouse", "24/7 Security", "Power Backup", "Parking"]),
                images=json.dumps(["property1.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="Affordable 2BHK in Electronic City",
                description="Well-connected apartment near IT parks with good public transport access.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=4500000,
                price_per_sqft=5000,
                size_sqft=900,
                bedrooms=2,
                bathrooms=2,
                address="Prestige Tech Park Road, Electronic City Phase 1",
                city="Bangalore",
                state="Karnataka",
                pincode="560100",
                latitude=12.8399,
                longitude=77.6770,
                amenities=json.dumps(["Gym", "24/7 Security", "Power Backup", "Parking"]),
                images=json.dumps(["property2.jpg"]),
                created_by=1,
            ),
            Property(
                title="Spacious 4BHK Villa in Sarjapur",
                description="Independent villa with private garden, modern kitchen, and premium interiors.",
                property_type=PropertyType.VILLA.value,
                status=PropertyStatus.AVAILABLE.value,
                price=25000000,
                price_per_sqft=8000,
                size_sqft=3125,
                bedrooms=4,
                bathrooms=4,
                address="Sarjapur Main Road",
                city="Bangalore",
                state="Karnataka",
                pincode="562125",
                latitude=12.8594,
                longitude=77.7870,
                amenities=json.dumps(["Private Garden", "Home Theater", "Modular Kitchen", "4 Car Parking", "Servant Quarter"]),
                images=json.dumps(["property3.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="1BHK Studio Apartment HSR Layout",
                description="Perfect for young professionals. Fully furnished with modern appliances.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.AVAILABLE.value,
                price=3200000,
                price_per_sqft=5800,
                size_sqft=552,
                bedrooms=1,
                bathrooms=1,
                address="HSR Layout Sector 7",
                city="Bangalore",
                state="Karnataka",
                pincode="560102",
                latitude=12.9116,
                longitude=77.6389,
                amenities=json.dumps(["Fully Furnished", "24/7 Security", "Power Backup"]),
                images=json.dumps(["property4.jpg"]),
                created_by=1,
            ),
            Property(
                title="Commercial Office Space - 2000 sqft",
                description="Prime location office space suitable for IT companies. Plug and play.",
                property_type=PropertyType.COMMERCIAL.value,
                status=PropertyStatus.AVAILABLE.value,
                price=15000000,
                price_per_sqft=7500,
                size_sqft=2000,
                address="Outer Ring Road, Marathahalli",
                city="Bangalore",
                state="Karnataka",
                pincode="560037",
                latitude=12.9537,
                longitude=77.7003,
                amenities=json.dumps(["Conference Room", "Cafeteria", "24/7 Access", "High Speed Internet", "100 Car Parking"]),
                images=json.dumps(["property5.jpg"]),
                created_by=1,
            ),
            Property(
                title="Office Space in Indiranagar",
                description="Ground floor commercial space in high footfall area. Ideal for business.",
                property_type=PropertyType.OFFICE.value,
                status=PropertyStatus.AVAILABLE.value,
                price=8000000,
                price_per_sqft=12000,
                size_sqft=667,
                address="100 Feet Road, Indiranagar",
                city="Bangalore",
                state="Karnataka",
                pincode="560038",
                latitude=12.9784,
                longitude=77.6408,
                amenities=json.dumps(["Street Facing", "Parking", "Power Backup"]),
                images=json.dumps(["property6.jpg"]),
                created_by=1,
            ),
            Property(
                title="Premium 3BHK in Koramangala",
                description="Walking distance to Forum Mall. Modern construction with excellent ventilation.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.RESERVED.value,
                price=12000000,
                price_per_sqft=8500,
                size_sqft=1412,
                bedrooms=3,
                bathrooms=3,
                address="Koramangala 5th Block",
                city="Bangalore",
                state="Karnataka",
                pincode="560095",
                latitude=12.9352,
                longitude=77.6245,
                amenities=json.dumps(["Swimming Pool", "Gym", "Clubhouse", "Jogging Track", "Children Play Area"]),
                images=json.dumps(["property7.jpg"]),
                is_featured=True,
                created_by=1,
            ),
            Property(
                title="2BHK Near Metro - Yeshwanthpur",
                description="Just 500m from metro station. Under construction - ready by Dec 2025.",
                property_type=PropertyType.APARTMENT.value,
                status=PropertyStatus.UNDER_CONSTRUCTION.value,
                price=5500000,
                price_per_sqft=5500,
                size_sqft=1000,
                bedrooms=2,
                bathrooms=2,
                address="Tumkur Road, Yeshwanthpur",
                city="Bangalore",
                state="Karnataka",
                pincode="560022",
                latitude=13.0299,
                longitude=77.5392,
                amenities=json.dumps(["Near Metro", "Gym", "24/7 Security", "Vastu Compliant"]),
                images=json.dumps(["property8.jpg"]),
                created_by=1,
            ),
        ]
        
        for prop in properties:
            db.add(prop)
        
        await db.commit()
        print(f"✓ Created {len(properties)} properties")


async def seed_leads():
    """Create sample leads."""
    async with async_session_maker() as db:
        leads = [
            Lead(
                name="Amit Kumar",
                email="amit.kumar@email.com",
                phone="+917878787878",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.HOT.value,
                status=LeadStatus.CONTACTED.value,
                budget_min=5000000,
                budget_max=8000000,
                preferred_location="Whitefield, Electronic City",
                property_type_interest="2BHK, 3BHK Apartment",
                notes="Looking for immediate possession. Prefers gated community.",
            ),
            Lead(
                name="Sneha Reddy",
                email="sneha.r@email.com",
                phone="+919898989898",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.WARM.value,
                status=LeadStatus.NEW.value,
                budget_min=20000000,
                budget_max=30000000,
                preferred_location="Sarjapur, Bannerghatta",
                property_type_interest="Villa",
                notes="Investor. Looking for properties with good appreciation.",
            ),
            Lead(
                name="Rajesh Menon",
                phone="+918787878787",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.COLD.value,
                status=LeadStatus.NEW.value,
                budget_min=3000000,
                budget_max=4000000,
                preferred_location="Electronic City",
                property_type_interest="1BHK, 2BHK",
            ),
            Lead(
                name="Sarah Johnson",
                email="sarah.j@company.com",
                phone="+919191919191",
                source=LeadSource.OUTBOUND_CALL.value,
                quality=LeadQuality.HOT.value,
                status=LeadStatus.SITE_VISIT_SCHEDULED.value,
                budget_min=10000000,
                budget_max=15000000,
                preferred_location="Indiranagar, Koramangala",
                property_type_interest="Commercial Office",
                notes="Tech startup looking for office space. Need by Q1 2026.",
                assigned_agent_id=3,
            ),
            Lead(
                name="Mohammed Ali",
                email="mali@business.com",
                phone="+917171717171",
                source=LeadSource.INBOUND_CALL.value,
                quality=LeadQuality.WARM.value,
                status=LeadStatus.IN_NEGOTIATION.value,
                budget_min=7000000,
                budget_max=9000000,
                preferred_location="HSR Layout, BTM Layout",
                property_type_interest="3BHK Apartment",
                notes="Has seen 3 properties. Interested in Brigade Meadows.",
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
