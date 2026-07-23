import urllib.request
import json
import sys

def http_discovery():
    url = "http://localhost:30010/remote/search"
    
    # We want to find any object that looks like "PythonScriptLibrary"
    # or "KismetSystemLibrary"
    queries = ["PythonScriptLibrary", "KismetSystemLibrary"]
    
    found_paths = {}
    
    headers = {"Content-Type": "application/json"}
    
    for q in queries:
        print(f"Searching for '{q}'...")
        payload = {
            "query": q,
            "requestId": 1
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    data = json.load(response)
                    # Parse results
                    results = data.get('assets', [])
                    for res in results:
                        # We are looking for the Class Default Object (CDO) which usually has "Default__"
                        # Or just any valid instance.
                        name = res.get('name', '')
                        path = res.get('path', '')
                        if "Default__" in path or "Default__" in name:
                             print(f"  [FOUND] {name} -> {path}")
                             found_paths[q] = path
                             
        except Exception as e:
            print(f"  Error searching {q}: {e}")

    # If we found paths, let's try to execute a test command on them
    if not found_paths:
        print("No suitable libraries found via HTTP Search.")
        return

    print("-" * 30)
    print("Testing Execution...")
    
    # Test Payload
    test_script = "print('HTTP Discovery Success')"
    
    # Try Python Lib first
    if "PythonScriptLibrary" in found_paths:
        path = found_paths["PythonScriptLibrary"]
        exec_via_http(path, "ExecutePythonCommand", {"Command": test_script})
        
    # Try Kismet Lib as backup
    elif "KismetSystemLibrary" in found_paths:
        path = found_paths["KismetSystemLibrary"]
        exec_via_http(path, "ExecuteConsoleCommand", {"WorldContextObject": "/Engine/Transient.World_0", "Command": f"py \"{test_script}\""})

def exec_via_http(object_path, function_name, params):
    url = "http://localhost:30010/remote/object/call"
    payload = {
        "objectPath": object_path,
        "functionName": function_name,
        "parameters": params,
        "generateTransaction": True
    }
    headers = {"Content-Type": "application/json"}
    
    print(f"Calling {function_name} on {object_path}...")
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
        with urllib.request.urlopen(req) as response:
            print(f"Response {response.status}: {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    http_discovery()
