from sqlalchemy import select

from app.database import async_session_maker
from app.models.property import Property, PropertyStatus


class RAGService:
    async def get_available_locations(self) -> str:
        """
        Fetch distinct available locations (Country, State, City) from DB.
        """
        try:
            async with async_session_maker() as db:
                # Fetch available properties
                result = await db.execute(
                    select(Property).where(Property.status == PropertyStatus.AVAILABLE.value)
                )
                properties = result.scalars().all()
                
                if not properties:
                    return "No locations currently available."

                # Aggregate locations
                locations = {}
                for p in properties:
                    country = p.country or "India"
                    state = p.state
                    city = p.city
                    
                    if country not in locations:
                        locations[country] = {}
                    if state not in locations[country]:
                        locations[country][state] = set()
                    locations[country][state].add(city)
                
                # Format output
                lines = ["AVAILABLE LOCATIONS:"]
                for country, states in locations.items():
                    lines.append(f"- Country: {country}")
                    for state, cities in states.items():
                        lines.append(f"  - State: {state}: {', '.join(sorted(cities))}")
                
                return "\n".join(lines)
        except Exception as e:
            print(f"Location Retrieval Error: {e}")
            return "Error retrieving location data."

    async def retrieve(self, query: str) -> str:
        """
        Dynamically fetch available properties from SQLite and format as context.
        """
        try:
            async with async_session_maker() as db:
                # Fetch available properties
                result = await db.execute(
                    select(Property).where(Property.status == PropertyStatus.AVAILABLE.value)
                )
                properties = result.scalars().all()
                
                if not properties:
                    return "No properties currently available in the database."

                # Format property list for the AI
                context_lines = []
                for p in properties:
                    price_lakhs = p.price / 100000 if p.price else 0
                    context_lines.append(
                        f"- {p.title}: {p.property_type} in {p.address} ({p.city}). "
                        f"Price: ₹{price_lakhs:.1f} Lakhs. "
                        f"Size: {p.size_sqft} sqft. "
                        f"Bedrooms: {p.bedrooms or 'N/A'}. "
                    )
                
                return "AVAILABLE INVENTORY FROM DATABASE:\n" + "\n".join(context_lines)
        except Exception as e:
            print(f"RAG Retrieval Error: {e}")
            return "Error retrieving property data."
