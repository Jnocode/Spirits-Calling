import urllib.request
import json

def find_python_object():
    url = "http://localhost:30010/remote/search"
    
    # Search for the class
    payload = {
        "query": "PythonScriptLibrary",
        "requestId": 1
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Searching for PythonScriptLibrary via {url}...")
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.load(response)
                print("Search Results:")
                print(json.dumps(data, indent=2))
                return True
            else:
                print(f"Failed with status: {response.status}")
                return False
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        try:
            print(e.read().decode('utf-8'))
        except:
            pass
        return False
    except Exception as e:
        print(f"Connection Error: {e}")
        return False

if __name__ == "__main__":
    find_python_object()
