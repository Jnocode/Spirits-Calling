import asyncio
import websockets
import json
import uuid
import base64

UE_WEBSOCKET_URI = "ws://127.0.0.1:30020"

async def test_payload():
    print(f"Connecting to {UE_WEBSOCKET_URI}...")
    async with websockets.connect(UE_WEBSOCKET_URI) as websocket:
        
        # The exact Python code we are trying to run in MCP
        python_code = """
import unreal
unreal.log_warning("MCP DEBUG: The Base64 Payload is WORKING!")
try:
    x, y, z = 0, 0, 0
    count = 1
    unreal.log_warning(f"MCP DEBUG: Spawning {count} enemies at ({x}, {y}, {z})")
except Exception as e:
    unreal.log_error(f"MCP DEBUG EXCEPTION: {e}")
"""
        
        # 1. Base64 Encode
        b64_bytes = base64.b64encode(python_code.encode('utf-8'))
        b64_str = b64_bytes.decode('utf-8')
        
        # 2. Wrapper
        wrapper_code = f"import base64; exec(base64.b64decode(b'{b64_str}').decode('utf-8'))"
        
        # 3. Escape for JSON
        safe_command = wrapper_code.replace('"', '\\"')
        
        print(f"Sending Command Wrapper: py \"{safe_command}\"")

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
                            "Command": f"py \"{safe_command}\""
                    },
                    "generateTransaction": True
                }
            },
            "Id": str(uuid.uuid4())
        }
        
        await websocket.send(json.dumps(payload))
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(test_payload())
