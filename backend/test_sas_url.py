import asyncio
import httpx
import os
import sys

# Add backend directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables BEFORE importing app modules
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

# Import token generation
from app.utils.security import create_access_token

# Define base URL
base_url = "http://localhost:8000"

async def test_get_recording_url():
    # 1. Generate a valid token
    # We need a secret key. In app/utils/security.py it uses settings.SECRET_KEY.
    # We should ensure settings are loaded or mock them if needed.
    # But create_access_token imports settings, so it should work if .env is loaded.
    
    token = create_access_token(user_id=1, email="admin@example.com", role="admin")
    
    # 2. Test Call ID 7 (known to exist)
    call_id = 7
    url = f"{base_url}/calls/{call_id}/recording-url"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Testing GET {url}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            if "recording_url" in data and data["recording_url"].startswith("https://"):
                print("SUCCESS: Received valid SAS URL")
            else:
                print("FAILURE: Invalid response format")
        else:
            print(f"FAILURE: Error response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_get_recording_url())
