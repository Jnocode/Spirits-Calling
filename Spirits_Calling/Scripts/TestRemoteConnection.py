import urllib.request
import json
import sys

def test_connection():
    url = "http://localhost:30010/remote/info"
    print(f"Testing connection to {url}...")
    
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                print("SUCCESS: Connected to Unreal Engine!")
                data = json.load(response)
                print("Server Info:")
                print(json.dumps(data, indent=2))
                return True
            else:
                print(f"FAILED: Status Code {response.status}")
                return False
            
    except urllib.error.URLError as e:
        print(f"FAILED: Could not connect to localhost:30010.")
        print(f"Error: {e}")
        print("Make sure 'Web Remote Control' plugin is ENABLED in Unreal Editor.")
        print("And ensure the Editor is running.")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    if not success:
        sys.exit(1)
