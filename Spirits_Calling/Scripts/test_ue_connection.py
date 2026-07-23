import asyncio
import websockets
import json
import uuid
import base64

UE_WEBSOCKET_URI = "ws://127.0.0.1:30020"

async def test_connection():
    print(f"Connecting to {UE_WEBSOCKET_URI}...")
    try:
        async with websockets.connect(UE_WEBSOCKET_URI) as websocket:
            print("Connected!")
            
            # Test 1: Simple Print using Base64
            print_code = 'import unreal; unreal.log_warning("TEST: Hello from Python Script via WebSocket!")'
            b64_code = base64.b64encode(print_code.encode('utf-8')).decode('utf-8')
            command = f"import base64; exec(base64.b64decode(b'{b64_code}').decode('utf-8'))"
            
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
            
            print("Sending test command...")
            await websocket.send(json.dumps(payload))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Response: {response}")
            print("\nPlease check your Unreal Engine Output Log for a YELLOW warning: 'TEST: Hello from Python Script via WebSocket!'")

    except Exception as e:
        print(f"Connection Failed: {e}")
        print("Ensure 'Remote Control API' plugin is enabled and 'Enable Web Server' is checked in Project Settings -> Remote Control.")

if __name__ == "__main__":
    asyncio.run(test_connection())
