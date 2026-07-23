import asyncio
import websockets
import json
import uuid

UE_WEBSOCKET_URI = "ws://127.0.0.1:30020"

async def test_simple():
    print(f"Connecting to {UE_WEBSOCKET_URI}...")
    try:
        async with websockets.connect(UE_WEBSOCKET_URI) as websocket:
            print("Connected!")
            
            # The most basic test possible
            command = "print('MCU TEST SUCCESS')"
            
            payload = {
                "MessageName": "http",
                "Parameters": {
                    "Url": "/remote/object/call",
                    "Verb": "PUT",
                    "Body": {
                        "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
                        "functionName": "ExecuteConsoleCommand",
                        "parameters": {
                             "WorldContextObject": "/Engine/Transient.World_0",
                             "Command": f"py \"{command}\""
                        },
                        "generateTransaction": True
                    }
                },
                "Id": str(uuid.uuid4())
            }
            
            print("Sending SIMPLE command...")
            await websocket.send(json.dumps(payload))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Response: {response}")
            print("\nCheck Output Log for: 'MCU TEST SUCCESS' (white text) or 'LogPython: MCU TEST SUCCESS'")

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple())
