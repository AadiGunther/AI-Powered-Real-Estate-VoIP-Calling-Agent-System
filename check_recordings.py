
import asyncio
import os
import sys
from sqlalchemy import select
from app.database import async_session_maker
from app.models.call import Call

# Ensure backend directory is in python path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def main():
    async with async_session_maker() as session:
        # Find calls with recording_url
        query = select(Call).where(Call.recording_url.is_not(None)).limit(5)
        result = await session.execute(query)
        calls = result.scalars().all()
        
        print(f"Found {len(calls)} calls with recordings:")
        for call in calls:
            print(f"ID: {call.id}, URL: {call.recording_url}, SID: {call.call_sid}")

if __name__ == "__main__":
    asyncio.run(main())
