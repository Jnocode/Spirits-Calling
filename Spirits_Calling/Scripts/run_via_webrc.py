# removed asyncio
import websockets
import json
import uuid
import sys
import os

import urllib.request
import json
import uuid
import sys
import os

UE_HTTP_URI = "http://127.0.0.1:30010/remote/object/call"

def run_script_in_ue(script_path):
    abs_path = os.path.abspath(script_path).replace('\\', '/')
    print(f"Triggering script in Unreal Editor: {abs_path}")
    
    command_str = f'py "{abs_path}"'
    
    # In UE5, relying on KismetSystemLibrary.ExecuteConsoleCommand often drops in PIE
    # because Transient.World_0 is not always the active PIE world. 
    # An alternative is to use Python directly via the 'python' process if UE exposes it,
    # but the simplest reliable REST approach is to ask UnrealEditorSubsystem or Python script execution directly.
    # We will try the standard REST approach on 30010 (default WebRC HTTP port)
    
    payload = {
        "objectPath": "/Script/Engine.Default__KismetSystemLibrary",
        "functionName": "ExecuteConsoleCommand",
        "parameters": {
             "WorldContextObject": "/Engine/Transient.World_0",
             "Command": command_str
        },
        "generateTransaction": True
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(UE_HTTP_URI, data=data, headers={'Content-Type': 'application/json'}, method='PUT')
    
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            res_body = response.read()
            print(f"Raw HTTP Response: {res_body.decode('utf-8')}")
            
            res_dict = json.loads(res_body)
            if res_dict.get("OutCommandPerformed"):
                print("[SUCCESS] Script execution command was sent and acknowledged by Unreal Engine.")
            else:
                print(f"[ERROR] Command not acknowledged properly (OutCommandPerformed is False).")
            
    except urllib.error.URLError as e:
         print(f"[ERROR] Connection refused on HTTP 30010: {e.reason}. Is the 'Web Remote Control' plugin enabled and server running?")
    except Exception as e:
        print(f"[ERROR] {e}")
            
    except ConnectionRefusedError:
         print("[ERROR] Connection refused. Is the 'Web Remote Control' plugin enabled in UE5?")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py run_via_webrc.py <path_to_script.py>")
    else:
        run_script_in_ue(sys.argv[1])
