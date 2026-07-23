import asyncio
import websockets
import json
import uuid
import sys
import os

async def mcp_exec(script_path):
    uri = "ws://127.0.0.1:30020"
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
    except Exception as e:
        print(f"Error reading script: {e}")
        return False

    print(f"Broadcasting script execution for {script_path} to {uri}...")
    
    # Get absolute path
    abs_path = os.path.abspath(script_path).replace("\\", "/")
    
    try:
        async with websockets.connect(uri) as websocket:
            # We use the "ExecuteConsoleCommand" and pass the file path
            # This is robust because it avoids string escaping issues
            
            command_str = f'py "{abs_path}"'
            print(f"Command: {command_str}")
            
            # Construct Payload
            msg_id = str(uuid.uuid4())
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
                             "Command": command_str
                        },
                        "generateTransaction": True
                    }
                },
                "Id": msg_id
            }
            
            await websocket.send(json.dumps(payload))
            
            # Wait for reply
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                resp_json = json.loads(response)
                code = resp_json.get("ResponseCode")
                if code == 200:
                    print("SUCCESS: Command executed.")
                    return True
                else:
                    print(f"FAILED: {response}")
                    return False
            except asyncio.TimeoutError:
                print("Output: (No immediate response, likely running async)")
                return True
                
    except Exception as e:
        print(f"Connection Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: Python MCP.py <script_path>")
    else:
        asyncio.run(mcp_exec(sys.argv[1]))
