import unreal
import os

def inspect_bp():
    # Pick a known blueprint (e.g. from the template)
    # The default VR template usually has /Game/VRTemplate/Blueprints/VRPawn
    test_path = "/Game/VRTemplate/Blueprints/VRPawn"
    
    asset = unreal.EditorAssetLibrary.load_asset(test_path)
    if not asset:
        # Fallback to any blueprint
        assets = unreal.EditorAssetLibrary.list_assets("/Game", recursive=True)
        for a in assets:
             d = unreal.EditorAssetLibrary.find_asset_data(a)
             if d.asset_class_path.asset_name == "Blueprint":
                 asset = unreal.EditorAssetLibrary.load_asset(a)
                 test_path = a
                 break
    
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/InspectReport.txt"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Inspecting: {test_path}\n")
        f.write(f"Type: {type(asset)}\n")
        f.write("-" * 20 + "\n")
        
        # Check properties
        # Try get_editor_property
        try:
            f_graphs = asset.get_editor_property("FunctionGraphs")
            f.write(f"Property 'FunctionGraphs': Found {len(f_graphs)}\n")
        except Exception as e:
             f.write(f"Property 'FunctionGraphs': Error {e}\n")
             
        try:
            u_graphs = asset.get_editor_property("UbergraphPages")
            f.write(f"Property 'UbergraphPages': Found {len(u_graphs)}\n")
        except Exception as e:
             f.write(f"Property 'UbergraphPages': Error {e}\n")
             
        try:
            m_graphs = asset.get_editor_property("MacroGraphs")
            f.write(f"Property 'MacroGraphs': Found {len(m_graphs)}\n")
        except Exception as e:
             f.write(f"Property 'MacroGraphs': Error {e}\n")
            
        # Dump dir()
        f.write("-" * 20 + "\nPROPERTIES:\n")
        for p in dir(asset):
            if not p.startswith('__'):
                f.write(f"{p}\n")

if __name__ == "__main__":
    inspect_bp()
