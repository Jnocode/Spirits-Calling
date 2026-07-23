try:
    import mcp
    import websockets
    print("Imports OK")
except ImportError as e:
    print(f"Import Failed: {e}")
