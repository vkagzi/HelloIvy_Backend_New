
import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8000/ws/voice/realtime/?feature=domain-discovery&session_id=test-session"
    print(f"Connecting to {uri}...")
    headers = {"Origin": "http://localhost:3000"}
    try:
        async with websockets.connect(uri, additional_headers=headers) as websocket:
            print("Connected!")
            # Wait for any initial message
            msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Received: {msg}")
    except Exception as e:
        print(f"Connection failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_ws())
