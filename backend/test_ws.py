
import asyncio
import websockets
import sys

async def test_ws(url):
    print(f"Connecting to {url}...")
    try:
        async with websockets.connect(url) as websocket:
            print("Connected!")
            await websocket.send("hello")
            print("Sent greeting")
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ws.py <url>")
    else:
        asyncio.run(test_ws(sys.argv[1]))
