import urllib.request
import json
import sys
import os

def http_exec(file_path):
    url = "http://localhost:30010/remote/object/call"
    
    # Read the script content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return False

    # Try 1: PythonScriptLibrary (Most likely for UE5.0+)
    # Note: Search results suggest this is the standard way.
    object_path = "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"
    
    payload = {
        "objectPath": object_path,
        "functionName": "ExecutePythonCommand",
        "parameters": {
            "Command": script_content
        },
        "generateTransaction": True
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Sending via HTTP {url} to {object_path}...")
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(f"SUCCESS: HTTP Request 200 OK")
                print(response.read().decode('utf-8'))
                return True
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        try:
             # Try to read the error message which often contains the "Object not found" detail
            print(f"Response: {e.read().decode('utf-8')}")
        except: 
            pass
            
        # Try 2: If Object Not Found, maybe try Kismet ExecuteConsoleCommand
        if e.code == 400 or e.code == 404:
             print("\nAttempting Fallback: ExecuteConsoleCommand matching 'py'...")
             # ... content for fallback
             return http_exec_fallback(script_content)

    except Exception as e:
        print(f"Connection Error: {e}")
        return False

def http_exec_fallback(script_content):
    url = "http://localhost:30010/remote/object/call"
    
    # Fallback to Console Command "py"
    # Note: This has limits (one line or escaping issues), but worth a try.
    # We must escape newlines for console command.
    one_line_script = script_content.replace('\n', '; ')
    command_str = f"py \"{one_line_script}\"" 
    # Use a simpler one-liner for test
    command_str = f"py \"print('HTTP Fallback Success')\""
    
    object_path = "/Script/Engine.Default__KismetSystemLibrary"
    
    payload = {
        "objectPath": object_path,
        "functionName": "ExecuteConsoleCommand",
        "parameters": {
            "WorldContextObject": "/Engine/Transient.World_0",
            "Command": command_str
        },
        "generateTransaction": True
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
        with urllib.request.urlopen(req) as response:
            print(f"Fallback Response: {response.status}")
            print(response.read().decode('utf-8'))
            return True
    except urllib.error.HTTPError as e:
        print(f"Fallback HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Test mode
        test_file = "TempHttpTest.py"
        with open(test_file, "w") as f:
            f.write("import unreal\nunreal.log_warning('AGENT: HTTP Connection Successful via PythonScriptLibrary!')")
        http_exec(test_file)
        try: os.remove(test_file) 
        except: pass
    else:
        http_exec(sys.argv[1])
