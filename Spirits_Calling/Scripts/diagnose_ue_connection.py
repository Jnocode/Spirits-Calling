import asyncio
import websockets
import json
import uuid

UE_WEBSOCKET_URI = "ws://127.0.0.1:30020"

async def run_command(name, command_str):
    print(f"\n--- Testing: {name} ---")
    print(f"Command: {command_str}")
    
    try:
        async with websockets.connect(UE_WEBSOCKET_URI) as websocket:
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
                "Id": str(uuid.uuid4())
            }
            
            await websocket.send(json.dumps(payload))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"Error: {e}")

async def main():
    print("Starting Diagnostic...")
    
    # Test 1: Stat FPS (Non-Python)
    # If this doesn't show "FPS" on your viewport, then ExecuteConsoleCommand is not working at all.
    await run_command("1. Native Command (Stat FPS)", "Stat FPS")
    
    # Test 2: Python Print with Single Quotes wrapper
    # py 'print("Test 2 Success")'
    await run_command("2. Python (Single Quotes)", "py 'print(\"Test 2 Success\")'")
    
    # Test 3: Python Print with Double Quotes wrapper
    # py "print('Test 3 Success')"
    await run_command("3. Python (Double Quotes)", "py \"print('Test 3 Success')\"")

    print("\nDiagnostic Complete.")
    print("Please check your Unreal Viewport (for FPS) and Output Log (for text).")

if __name__ == "__main__":
    asyncio.run(main())
