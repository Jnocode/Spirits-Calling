import unreal
import os

def debug_scan():
    root_path = "/Game"
    all_assets = unreal.EditorAssetLibrary.list_assets(root_path, recursive=True)
    
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/DebugReport.txt"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Total Assets found in {root_path}: {len(all_assets)}\n")
        f.write("-" * 20 + "\n")
        
        for i, path in enumerate(all_assets[:20]):
            data = unreal.EditorAssetLibrary.find_asset_data(path)
            # Safe access to class name
            cls_name = "Unknown"
            try:
                cls_name = data.asset_class_path.asset_name
            except:
                try:
                    cls_name = data.asset_class
                except:
                    pass
                    
            f.write(f"{i}: {path} [Class: {cls_name}]\n")

if __name__ == "__main__":
    debug_scan()
