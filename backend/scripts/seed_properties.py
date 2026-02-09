"""Seed database with sample properties for testing."""

import asyncio
import json
from sqlalchemy import select

from app.database import async_session_maker, MongoDB
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User, UserRole
from app.utils.security import get_password_hash


SAMPLE_PROPERTIES = [
    {
        "title": "Spacious 2BHK Apartment in Whitefield",
        "description": "Beautiful 2BHK apartment with modern amenities, close to schools and IT parks.",
        "property_type": PropertyType.APARTMENT.value,
        "address": "123 Tech Park Road, Whitefield",
        "city": "Bangalore",
        "state": "Karnataka",
        "country": "India",
        "pincode": "560066",
        "locality": "Whitefield",
        "landmark": "Near ITPL",
        "price": 4500000,  # 45 lakhs
        "price_per_sqft": 3750,
        "size_sqft": 1200,
        "bedrooms": 2,
        "bathrooms": 2,
        "parking_spaces": 1,
        "amenities": json.dumps(["Gym", "Swimming Pool", "24/7 Security", "Power Backup"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": True,
    },
    {
        "title": "Luxury 3BHK Villa in Sarjapur",
        "description": "Premium villa with private garden, perfect for families.",
        "property_type": PropertyType.VILLA.value,
        "address": "456 Green Valley, Sarjapur Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560035",
        "locality": "Sarjapur",
        "landmark": "Sarjapur-Marathahalli Road",
        "price": 8500000,  # 85 lakhs
        "price_per_sqft": 4250,
        "size_sqft": 2000,
        "bedrooms": 3,
        "bathrooms": 3,
        "parking_spaces": 2,
        "amenities": json.dumps(["Private Garden", "Clubhouse", "Security", "Kids Play Area"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": True,
    },
    {
        "title": "Commercial Office Space in ORR",
        "description": "Prime office space on Outer Ring Road, ideal for IT companies.",
        "property_type": PropertyType.OFFICE.value,
        "address": "789 Business Hub, Outer Ring Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560103",
        "locality": "Marathahalli",
        "landmark": "Near Marathahalli Bridge",
        "price": 12000000,  # 1.2 crores
        "price_per_sqft": 4000,
        "size_sqft": 3000,
        "bedrooms": None,
        "bathrooms": 4,
        "parking_spaces": 10,
        "amenities": json.dumps(["Conference Rooms", "Cafeteria", "24/7 Access", "High-speed Internet"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
    },
    {
        "title": "Affordable 1BHK Flat in Electronic City",
        "description": "Perfect starter home for young professionals.",
        "property_type": PropertyType.APARTMENT.value,
        "address": "321 Tech Valley, Electronic City Phase 1",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560100",
        "locality": "Electronic City",
        "landmark": "Phase 1",
        "price": 2800000,  # 28 lakhs
        "price_per_sqft": 3500,
        "size_sqft": 800,
        "bedrooms": 1,
        "bathrooms": 1,
        "parking_spaces": 1,
        "amenities": json.dumps(["Lift", "Security", "Power Backup"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
    },
    {
        "title": "Premium 4BHK Penthouse in Koramangala",
        "description": "Luxury penthouse with terrace garden and city views.",
        "property_type": PropertyType.APARTMENT.value,
        "address": "555 Skyline Heights, Koramangala 1st Block",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560034",
        "locality": "Koramangala",
        "landmark": "Forum Mall",
        "price": 18000000,  # 1.8 crores
        "price_per_sqft": 7200,
        "size_sqft": 2500,
        "bedrooms": 4,
        "bathrooms": 4,
        "parking_spaces": 2,
        "amenities": json.dumps(["Terrace Garden", "Jacuzzi", "Home Theater", "Smart Home"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": True,
    },
    {
        "title": "Industrial Warehouse in Peenya",
        "description": "Large warehouse with loading bay, suitable for manufacturing.",
        "property_type": PropertyType.WAREHOUSE.value,
        "address": "888 Industrial Area, Peenya 2nd Stage",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560058",
        "locality": "Peenya",
        "landmark": "Peenya Industrial Area",
        "price": 25000000,  # 2.5 crores
        "price_per_sqft": 2500,
        "size_sqft": 10000,
        "bedrooms": None,
        "bathrooms": 2,
        "parking_spaces": 5,
        "amenities": json.dumps(["Loading Bay", "High Ceiling", "24/7 Security", "Power Backup"]),
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
    },
]


async def seed_properties():
    """Add sample properties to database."""
    async with async_session_maker() as db:
        # Get or create admin user
        result = await db.execute(select(User).where(User.email == "admin@abc-realestate.com"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = User(
                email="admin@abc-realestate.com",
                full_name="Admin User",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(admin)
            await db.flush()
        
        # Check if properties already exist
        result = await db.execute(select(Property))
        existing_count = len(result.scalars().all())
        
        if existing_count > 0:
            print(f"Database already has {existing_count} properties. Skipping seed.")
            return
        
        # Add sample properties
        for prop_data in SAMPLE_PROPERTIES:
            property_obj = Property(
                **prop_data,
                created_by=admin.id,
                is_active=True,
            )
            db.add(property_obj)
        
        await db.commit()
        print(f"✅ Successfully added {len(SAMPLE_PROPERTIES)} sample properties!")


async def main():
    """Run the seed script."""
    await MongoDB.connect()
    await seed_properties()
    await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
