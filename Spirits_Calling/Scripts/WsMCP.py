import asyncio
import websockets
import json
import uuid

async def mcp_connect_and_exec(script_path):
    # Unreal Web Remote Control WebSocket Port
    # From logs: "LogRemoteControl: Web Remote Control WebSocket server started on port 30020"
    uri = "ws://127.0.0.1:30020"
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
    except Exception as e:
        print(f"Error reading script: {e}")
        return

    print(f"Connecting to MCP/WebSocket at {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Sending MCP/Remote Command...")
            
            # Construct the Web Remote Control "Call" payload wrapped in WebSocket message
            # The format typically mimics the HTTP REST body but with a MessagePreset or Function Call
            # For "ExecuteConsoleCommand"
            
            # Note: WebSocket messages in Unreal Remote Control usually need a specific "MessageName"
            # referencing a Preset or a raw 'http' style wrapper.
            # Let's try the "http" tunnel format if supported, OR a direct execution call.
            
            # Common WS format for RC API:
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
                             "Command": f"py \"{script_content.replace(chr(10), '; ')}\""
                        },
                        "generateTransaction": True
                    }
                },
                "Id": msg_id
            }
            
            await websocket.send(json.dumps(payload))
            print("Message sent. Waiting for response...")
            
            # Wait for reply
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Response: {response}")
            except asyncio.TimeoutError:
                print("No response received within timeout.")
                
    except Exception as e:
        print(f"WebSocket Error: {e}")
        print("Note: You may need to install 'websockets' lib: pip install websockets")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        asyncio.run(mcp_connect_and_exec("TempWsTest.py")) 
    else:
        asyncio.run(mcp_connect_and_exec(sys.argv[1]))
