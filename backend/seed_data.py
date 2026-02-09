
import asyncio
import json
from datetime import datetime

from app.database import async_session_maker, init_db
from app.models.user import User, UserRole
from app.models.property import Property, PropertyType, PropertyStatus
from app.utils.security import get_password_hash
from sqlalchemy import func

# Sample Data
PROPERTIES = [
    {
        "title": "Luxury 3BHK Apartment in Whitefield",
        "description": "Premium 3BHK apartment with modern amenities, swimming pool view, and easy access to IT parks.",
        "property_type": PropertyType.APARTMENT.value,
        "address": "Prestige Shantiniketan, Whitefield Main Rd",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560048",
        "locality": "Whitefield",
        "price": 12500000.0,  # 1.25 Cr
        "size_sqft": 1850.0,
        "bedrooms": 3,
        "bathrooms": 3,
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": True,
        "images": json.dumps(["https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&q=80"]),
        "amenities": json.dumps(["Pool", "Gym", "Clubhouse", "Security"])
    },
    {
        "title": "Spacious 4BHK Villa in Sarjapur",
        "description": "Gated community villa with private garden and terrace.",
        "property_type": PropertyType.VILLA.value,
        "address": "Villa 45, Sobha Lifestyle",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "562125",
        "locality": "Sarjapur Road",
        "price": 35000000.0,  # 3.5 Cr
        "size_sqft": 3200.0,
        "bedrooms": 4,
        "bathrooms": 4,
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": True,
        "images": json.dumps(["https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&q=80"]),
        "amenities": json.dumps(["Private Garden", "Servant Quarters", "Power Backup"])
    },
    {
        "title": "Affordable 2BHK in Electronic City",
        "description": "Compact and cozy 2BHK perfect for young professionals.",
        "property_type": PropertyType.APARTMENT.value,
        "address": "Neeladri Nagar, Electronic City Phase 1",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560100",
        "locality": "Electronic City",
        "price": 4500000.0,  # 45 L
        "size_sqft": 1100.0,
        "bedrooms": 2,
        "bathrooms": 2,
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
        "images": json.dumps(["https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&q=80"]),
        "amenities": json.dumps(["Lift", "Parking", "CCTV"])
    },
    {
        "title": "Commercial Office Space in Koramangala",
        "description": "Furnished office space suitable for startups and small teams.",
        "property_type": PropertyType.OFFICE.value,
        "address": "80 Feet Road, 4th Block",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560034",
        "locality": "Koramangala",
        "price": 25000000.0,  # 2.5 Cr
        "size_sqft": 1500.0,
        "bedrooms": 0,
        "bathrooms": 2,
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
        "images": json.dumps(["https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80"]),
        "amenities": json.dumps(["AC", "Cafeteria", "Meeting Rooms"])
    },
    {
        "title": "Premium Plot in Devanahalli",
        "description": "Investment ready plot near International Airport.",
        "property_type": PropertyType.PLOT.value,
        "address": "IVC Road, Devanahalli",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "562110",
        "locality": "Devanahalli",
        "price": 6000000.0,  # 60 L
        "size_sqft": 1200.0,
        "bedrooms": 0,
        "bathrooms": 0,
        "status": PropertyStatus.AVAILABLE.value,
        "is_featured": False,
        "images": json.dumps(["https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&q=80"]),
        "amenities": json.dumps(["Gated", "Water Connection", "Electricity"])
    }
]

async def seed_data():
    print("Initializing database...")
    await init_db()
    
    async with async_session_maker() as session:
        # 1. Ensure a User Exists
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("Creating Admin User...")
            user = User(
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Admin User",
                role=UserRole.ADMIN.value,
                is_active=True,
                is_verified=True
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created user: {user.email}")
        else:
            print(f"Found user: {user.email}")

        # 2. Check and Seed Properties
        result = await session.execute(select(func.count()).select_from(Property))
        count = result.scalar()
        
        if count == 0:
            print("Seeding Properties...")
            for prop_data in PROPERTIES:
                prop = Property(
                    created_by=user.id,
                    **prop_data
                )
                session.add(prop)
            await session.commit()
            print(f"Added {len(PROPERTIES)} properties.")
        else:
            print(f"Database already has {count} properties. Skipping seed.")

if __name__ == "__main__":
    asyncio.run(seed_data())
