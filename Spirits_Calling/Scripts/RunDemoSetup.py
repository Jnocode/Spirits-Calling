# Master Setup Script for Spirits Calling Demo
# Usage: Run this script in Unreal Engine Python Editor or Output Log (py "path/to/script.py")

import unreal
import sys
import os

# Helper to reload modules if editing
import importlib

# Add Scripts to path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

try:
    import SetupDemoLevel
    import WaveManager
    importlib.reload(SetupDemoLevel)
    importlib.reload(WaveManager)
except ImportError as e:
    unreal.log_error(f"Failed to import modules: {e}")
    # Fallback if running relative
    unreal.log_warning("Attempting relative import fallback...")

def run_demo():
    unreal.log_warning("=== SPIRITS CALLING DEMO SETUP START ===")
    
    # 1. Setup Environment
    try:
        SetupDemoLevel.setup_demo_level()
        unreal.log_warning("Environment Setup Complete.")
    except Exception as e:
        unreal.log_error(f"Environment Setup Failed: {e}")
        return

    # 2. Start Wave System
    try:
        # Reset wave manager
        WaveManager.wave_manager = WaveManager.WaveManager()
        # Start Wave 1
        WaveManager.wave_manager.start_wave(1)
        unreal.log_warning("Wave 1 Started.")
    except Exception as e:
        unreal.log_error(f"Wave System Failed: {e}")

    # 3. Setup Player/VR (Possess functionality usually runtime, but we can log checks)
    unreal.log_warning("=== DEMO READY. Press Play in VR! ===")

if __name__ == "__main__":
    run_demo()
