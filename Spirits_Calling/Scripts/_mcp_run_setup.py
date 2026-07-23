import sys
sys.path.append(r'd:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts')
import SetupDemoLevel
import importlib
try:
    importlib.reload(SetupDemoLevel)
    SetupDemoLevel.setup_demo_level()
    print("MCP_RESP_SETUP_START: Success")
except Exception as e:
    import unreal
    unreal.log_error(f"Setup Failed: {e}")
