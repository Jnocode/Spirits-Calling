from mcp.server.fastmcp import FastMCP
import asyncio
import websockets
import json
import uuid

# Define the MCP Server
mcp = FastMCP("UnrealEngine")

# Configuration for Unreal Engine WebSocket
UE_WEBSOCKET_URI = "ws://127.0.0.1:30020"

import os

async def send_to_ue5(python_code: str):
    """
    Sends Python code to Unreal Engine 5 via Web Remote Control WebSocket.
    STRATEGY: Write code to a temp file, then ask UE5 to execute that file.
    This bypasses all quoting, escaping, and line-length issues.
    """
    try:
        # 1. Write the code to a temporary file in the Scripts folder (so UE can see it easily)
        # We use a fixed name to avoid polluting directory, but usually tempfile is better.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_file = os.path.join(script_dir, "_mcp_temp_exec.py")
        
        # Add boiler plate to ensure log visibility
        full_code = "import unreal\n" + python_code
        
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(full_code)
            
        # Normalize path for Unreal (forward slashes)
        ue_friendly_path = temp_file.replace("\\", "/")
        
        async with websockets.connect(UE_WEBSOCKET_URI) as websocket:
            # 2. Command UE to run this specific file
            # Syntax: py "C:/Path/To/File.py"
            command = f'py "{ue_friendly_path}"'
            
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
                             "Command": command
                        },
                        "generateTransaction": True
                    }
                },
                "Id": str(uuid.uuid4())
            }
            
            await websocket.send(json.dumps(payload))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            return response

    except Exception as e:
        return f"Error connecting to UE5: {str(e)}"

@mcp.tool()
async def list_assets(path: str = "/Game"):
    """
    Lists assets in a specific Unreal Engine folder path.
    Useful for finding the correct Blueprint path.
    """
    ue_code = f"""
import unreal

search_path = "{path}"
unreal.log_warning(f"MCP: Listing assets in {{search_path}}")
reg = unreal.AssetRegistryHelpers.get_asset_registry()
assets = reg.get_assets_by_path(search_path, recursive=True)

result = []
for asset in assets:
    # Format: AssetName (Class) -> Path
    result.append(f"{{asset.asset_name}} ({{asset.asset_class_path.asset_name}}) -> {{asset.object_path}}")

if not result:
    unreal.log_warning("MCP: No assets found in that path.")
else:
    for r in result[:20]: # Log first 20 to avoid spam
        unreal.log_warning(r)
    """
    response = await send_to_ue5(ue_code)
    # Since we can't easily get the return value back from the websocket exec without complex setup,
    # we ask the user to check the log, or we rely on the fact that send_to_ue5 returns the console response.
    return f"List command sent. Check Unreal Output Log (Yellow Text) for results. Response: {response}"

@mcp.tool()
async def spawn_enemy(blueprint_path: str = "/Game/Blueprints/Enemy/BP_Enemy", count: int = 1, x: float = 0.0, y: float = 0.0, z: float = 0.0):
    """
    Spawns enemies at the specified location.
    Args:
        blueprint_path: Path to the Blueprint asset (e.g. "/Game/Blueprints/Enemy/BP_Orc"). 
                        No need for "Blueprint''" wrapper or "_C" suffix.
        count: Number of enemies to spawn.
    """
    print(f"DEBUG: MCP passed spawn_enemy path='{blueprint_path}'")
    
    # Strip quotes and decorators just in case user provides them
    clean_path = blueprint_path.replace("Blueprint'", "").replace("'", "")
    if clean_path.endswith("_C"):
        clean_path = clean_path[:-2]
    # Remove Package.Asset duplication if present (e.g. Path/BP.BP -> Path/BP)
    # Actually EditorAssetLibrary.load_asset expects /Game/Path/BP_Name
    # But let's handle the case where user passed /Game/Path/BP.BP
    if "." in clean_path:
        clean_path = clean_path.split(".")[0]

    ue_code = f"""
import unreal

# Clean path passed from MCP
bp_path = "{clean_path}"
location = unreal.Vector({x}, {y}, {z})
count = {count}

unreal.log_warning(f"MCP: Attempting to spawn {{count}} actors from {{bp_path}}")

# 1. Load the Blueprint Asset
bp_asset = unreal.EditorAssetLibrary.load_asset(bp_path)

if not bp_asset:
    unreal.log_warning(f"MCP Error: Could not load asset at {{bp_path}}. Checking existence...")
    if not unreal.EditorAssetLibrary.does_asset_exist(bp_path):
         unreal.log_warning("MCP Error: Asset does not exist on disk/registry!")
    else:
         unreal.log_warning("MCP Error: Asset exists but failed to load.")
else:
    # 2. Get the Generated Class from the Blueprint
    # Note: For Blueprint assets, we need the GeneratedClass to spawn
    actor_class = None
    if isinstance(bp_asset, unreal.Blueprint):
        # Handle generated_class being a method or property depending on UE version
        raw_val = bp_asset.generated_class
        if callable(raw_val):
            actor_class = raw_val()
        else:
            actor_class = raw_val
    else:
        # Maybe it's a C++ class or something else?
        unreal.log_warning(f"MCP Warning: Asset is not a Blueprint (Type: {{type(bp_asset)}}), trying raw cast...")
        actor_class = bp_asset

    if not actor_class:
        unreal.log_warning("MCP Error: Could not resolve Actor Class from Blueprint asset.")
    else:
        # 3. Spawn
        unreal.log_warning(f"MCP: Resolved Class {{actor_class}}. Spawning...")
        editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor_subsystem.get_editor_world()
        
        for i in range(count):
            # Offset slightly to avoid stacking
            spawn_loc = unreal.Vector(location.x + i * 100, location.y, location.z)
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, spawn_loc)
            if actor:
                unreal.log_warning(f"MCP: Spawned {{actor.get_name()}}")
            else:
                unreal.log_warning("MCP Error: Spawn returned None")
    """
    response = await send_to_ue5(ue_code)
    return f"Sent spawn command to UE5. Engine Response: {response}"

@mcp.tool()
async def execute_python(code: str):
    """
    Executes raw Python code in Unreal Engine.
    Use this for custom logic not covered by other tools.
    """
    # Do NOT escape quotes. send_to_ue5 writes to a file, so raw code is fine.
    # Just ensure we import unreal and log execution.
    # We can rely on send_to_ue5 adding 'import unreal' at the very top.
    wrapped_code = f"unreal.log_warning('MCP Executing Custom Code')\n{code}"
    
    response = await send_to_ue5(wrapped_code)
    return f"Executed code. Engine Response: {response}"

@mcp.tool()
async def create_blueprint(name: str = "BP_Enemy", path: str = "/Game/Blueprints"):
    """
    Creates a new Actor Blueprint in the specified path.
    """
    print(f"DEBUG: MCP creating blueprint '{name}' in '{path}'")
    
    ue_code = f"""
import unreal

asset_name = "{name}"
package_path = "{path}"

unreal.log_warning(f"MCP: Creating new Blueprint {{asset_name}} in {{package_path}}...")

factory = unreal.BlueprintFactory()
factory.set_editor_property("parent_class", unreal.Actor)

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
new_asset = asset_tools.create_asset(asset_name, package_path, unreal.Blueprint, factory)

if new_asset:
    unreal.log_warning(f"MCP: SUCCESS created {{new_asset.get_path_name()}}")
    
    # Compile the blueprint to ensure the class (_C) is generated
    unreal.EditorAssetLibrary.save_loaded_asset(new_asset)
    unreal.EditorLevelLibrary.save_all_dirty_levels()
    
    # Try to compile it explicitly
    try:
        if isinstance(new_asset, unreal.Blueprint):
            unreal.BlueprintEditorLibrary.compile_blueprint(new_asset)
            unreal.log_warning("MCP: Blueprint compiled.")
    except:
        pass

    # Force Registry Update
    unreal.AssetRegistryHelpers.get_asset_registry().scan_modified_asset_files([new_asset.get_package().get_name()])
    
    unreal.log_warning(f"MCP: Asset ready. You can now spawn it using: Blueprint'{{new_asset.get_path_name()}}_C'")
else:
    unreal.log_warning("MCP Error: Failed to create asset (maybe it already exists?)")
    """
    response = await send_to_ue5(ue_code)
    return f"Create command sent. Check Unreal Output Log for 'SUCCESS'. Response: {response}"

@mcp.tool()
async def search_assets(query: str, root_path: str = "/Game"):
    """
    Searches for assets matching a name query within a root path.
    Case-insensitive.
    Example: search_assets("Enemy")
    """
    print(f"DEBUG: MCP received search_assets query='{query}', root_path='{root_path}'")
    
    ue_code = f"""
import unreal

search_query = "{query}".lower()
root = "{root_path}"
unreal.log_warning(f"MCP: Searching for assets containing '{{search_query}}' in {{root}}...")

reg = unreal.AssetRegistryHelpers.get_asset_registry()
# Get all assets in root (recursive)
assets = reg.get_assets_by_path(root, recursive=True)

found_count = 0
for asset in assets:
    asset_name = str(asset.asset_name).lower()
    if search_query in asset_name:
        # Log valid format for spawning: AssetClass -> PackagePath.AssetName
        
        full_path = str(asset.object_path)
        # Check if it's a Blueprint
        if asset.asset_class_path.asset_name == "Blueprint":
             # Append _C for class loading usually
             full_path += "_C"
        
        unreal.log_warning(f"FOUND: {{asset.asset_name}} ({{asset.asset_class_path.asset_name}}) -> {{full_path}}")
        found_count += 1
        if found_count >= 20:
            unreal.log_warning("MCP: Limit reached (20 items). Refine your search.")
            break

if found_count == 0:
    unreal.log_warning("MCP: No matching assets found.")
    """
    response = await send_to_ue5(ue_code)
    return f"Search command sent. Check Unreal Output Log (Yellow Text) for results. Response: {response}"

@mcp.tool()
async def read_recent_logs(lines: int = 50):
    """
    Reads the most recent log lines from the Unreal Engine saved log file.
    Use this to debug issues or verify if a command worked.
    """
    # Hardcoded path based on project structure. 
    # Ideally this would be dynamic or config-based.
    log_path = r"d:\Workspace\03_Dev_Projects\game\Spirits-Calling\Spirits_Calling\Saved\Logs\Spirits_Calling.log"
    
    if not os.path.exists(log_path):
        return f"Error: Log file not found at {log_path}"
        
    try:
        # Read file with shared access (sometimes tricky on windows if UE has it locked, but usually read-only works)
        # We read the last N lines efficiently
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Move to end
            f.seek(0, 2)
            file_size = f.tell()
            
            # Simple approach: Read last 10KB and look for lines
            read_size = min(20000, file_size)
            f.seek(file_size - read_size)
            content = f.read()
            
            all_lines = content.splitlines()
            return "\n".join(all_lines[-lines:])
            
    except Exception as e:
        return f"Error reading log file: {e}"

# Helper to read back data from logs
import time
import re

LOG_FILE_PATH = r"d:\Workspace\03_Dev_Projects\game\Spirits-Calling\Spirits_Calling\Saved\Logs\Spirits_Calling.log"

def fetch_mcp_response(req_id: str, max_retries=5):
    """
    Scrapes the log file for a specific request ID response.
    Format expected in log: MCP_RESPONSE_START:{req_id} ... content ... MCP_RESPONSE_END:{req_id}
    """
    for _ in range(max_retries):
        time.sleep(1.0) # Wait for UE to flush logs
        try:
            with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                # Read end of file usually
                # But for simplicity read whole file if not too huge, or last 100KB
                f.seek(0, 2)
                size = f.tell()
                start = max(0, size - 100000)
                f.seek(start)
                content = f.read()
                
                pattern = f"MCP_RESPONSE_START:{req_id}(.*?)MCP_RESPONSE_END:{req_id}"
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(1).strip()
        except Exception as e:
            print(f"Log read error: {e}")
    return "TIMEOUT: No response found in logs."

@mcp.tool()
async def list_actors(filter_class: str = "Actor"):
    """
    Lists all actors in the current level, optionally filtered by class name.
    Args:
        filter_class: The class name to filter by (e.g., 'StaticMeshActor', 'BP_Orc_C'). Default is 'Actor' (all).
    """
    req_id = str(uuid.uuid4())[:8]
    ue_code = f"""
import unreal

req_id = "{req_id}"
filter_cls = "{filter_class}"
# Get all actors
actors = unreal.EditorLevelLibrary.get_all_level_actors()
found = []

for actor in actors:
    # Check class name match
    cls_name = actor.get_class().get_name()
    if filter_cls.lower() == "actor" or filter_cls.lower() in cls_name.lower():
        pos = actor.get_actor_location()
        found.append(f"{{actor.get_actor_label()}} ({{cls_name}})")

max_print = 50
count = len(found)
output = "\\n".join(found[:max_print])
if count > max_print:
    output += f"\\n... and {{count - max_print}} more."

# Encapsulate output for scraper
final_msg = f"MCP_RESPONSE_START:{{req_id}}\\nFound {{count}} actors:\\n{{output}}\\nMCP_RESPONSE_END:{{req_id}}"
unreal.log_warning(final_msg)
"""
    await send_to_ue5(ue_code)
    return fetch_mcp_response(req_id)

@mcp.tool()
async def get_actor_property(actor_label: str, property_name: str):
    """
    Gets a property value from a specific actor by its Label.
    """
    req_id = str(uuid.uuid4())[:8]
    ue_code = f"""
import unreal

req_id = "{req_id}"
label = "{actor_label}"
prop = "{property_name}"
result = "Actor not found"

actors = unreal.EditorLevelLibrary.get_all_level_actors()
target_actor = None
for a in actors:
    if a.get_actor_label() == label:
        target_actor = a
        break

if target_actor:
    try:
        if prop.lower() in ["location", "actorlocation"]:
            val = target_actor.get_actor_location()
            result = f"{{val.x}},{{val.y}},{{val.z}}"
        elif prop.lower() in ["rotation", "actorrotation"]:
            val = target_actor.get_actor_rotation()
            result = f"{{val.roll}},{{val.pitch}},{{val.yaw}}"
        else:
            val = target_actor.get_editor_property(prop)
            result = str(val)
    except Exception as e:
        result = f"Error: {{e}}"
else:
    result = f"Actor '{{label}}' not found."

unreal.log_warning(f"MCP_RESPONSE_START:{{req_id}}\\n{{result}}\\nMCP_RESPONSE_END:{{req_id}}")
"""
    await send_to_ue5(ue_code)
    return fetch_mcp_response(req_id)

@mcp.tool()
async def set_actor_property(actor_label: str, property_name: str, value: str):
    """
    Sets a property value on a specific actor.
    """
    req_id = str(uuid.uuid4())[:8]
    ue_code = f"""
import unreal
import ast

req_id = "{req_id}"
label = "{actor_label}"
prop = "{property_name}"
val_str = "{value}"

result = "Init"
actors = unreal.EditorLevelLibrary.get_all_level_actors()
target_actor = None
for a in actors:
    if a.get_actor_label() == label:
        target_actor = a
        break

if target_actor:
    try:
        try:
            val = ast.literal_eval(val_str)
        except:
            val = val_str
            
        target_actor.set_editor_property(prop, val)
        result = f"Successfully set {{prop}} to {{val}}"
    except Exception as e:
        result = f"Failed to set {{prop}}: {{e}}"
else:
    result = f"Actor '{{label}}' not found."

unreal.log_warning(f"MCP_RESPONSE_START:{{req_id}}\\n{{result}}\\nMCP_RESPONSE_END:{{req_id}}")
"""
    await send_to_ue5(ue_code)
    return fetch_mcp_response(req_id)

@mcp.tool()
async def execute_console_command(command: str):
    """Executes a console command."""
    req_id = str(uuid.uuid4())[:8]
    ue_code = f"""
import unreal
req_id = "{req_id}"
unreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), "{command}")
unreal.log_warning(f"MCP_RESPONSE_START:{{req_id}}Command Executed\\nMCP_RESPONSE_END:{{req_id}}")
"""
    await send_to_ue5(ue_code)
    return fetch_mcp_response(req_id)

@mcp.tool()
async def setup_demo_level():
    """
    Initializes the demo level environment.
    Executes 'SetupDemoLevel.py' script on the UE5 side.
    """
    ue_code = """
import sys
import unreal
# Append Scripts path 
sys.path.append(r'd:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts')
import SetupDemoLevel
import importlib
try:
    importlib.reload(SetupDemoLevel)
    SetupDemoLevel.setup_demo_level()
    unreal.log_warning("MCP_RESP_SETUP_START: Success")
except Exception as e:
    unreal.log_warning(f"Setup Failed: {e}")
"""
    response = await send_to_ue5(ue_code)
    return f"Setup command sent. Check logs for 'MCP_RESP_SETUP_START'."

if __name__ == "__main__":
    mcp.run()
