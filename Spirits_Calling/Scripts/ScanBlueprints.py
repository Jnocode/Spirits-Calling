import unreal
import os

def scan_blueprints():
    root_path = "/Game"
    all_assets = unreal.EditorAssetLibrary.list_assets(root_path, recursive=True)
    
    blueprint_stats = []
    
    with unreal.ScopedSlowTask(len(all_assets), "Analyzing Blueprints...") as slow_task:
        slow_task.make_dialog(True)
        
        for asset_path in all_assets:
            if slow_task.should_cancel():
                break
            slow_task.enter_progress_frame(1)
            
            asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
            
            if asset_data.asset_class_path.asset_name == "Blueprint":
                registry = unreal.AssetRegistryHelpers.get_asset_registry()
                deps = registry.get_dependencies(asset_data.package_name, unreal.AssetRegistryDependencyOptions())
                dep_count = len(deps) if deps else 0
                
                try:
                    pkg_filename = unreal.EditorAssetLibrary.get_package_filename(asset_data.package_name)
                    if pkg_filename and os.path.exists(pkg_filename):
                        size_kb = os.path.getsize(pkg_filename) / 1024.0
                    else:
                        size_kb = 0
                except:
                    size_kb = 0
                
                # Include ALL blueprints
                if size_kb >= 0:
                    blueprint_stats.append((asset_path, size_kb, dep_count))

    blueprint_stats.sort(key=lambda x: x[1], reverse=True)
    
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/BlueprintReport.txt"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("--- Blueprint Complexity Report (Size & Dependencies) ---\n")
        f.write(f"Total Blueprints: {len(blueprint_stats)}\n")
        f.write("Format: [Size KB | Dependencies] Path\n\n")
        
        if len(blueprint_stats) == 0:
             f.write("No Blueprints found.\n")
        else:
            for path, size, deps in blueprint_stats:
                line = f"[{size:6.1f} KB | {deps:3} Refs] {path}"
                # Log only top ones to console to avoid spam
                if size > 10:
                    unreal.log_warning(line)
                f.write(line + "\n")
                
    unreal.log(f"Report saved to: {report_path}")

if __name__ == "__main__":
    scan_blueprints()
