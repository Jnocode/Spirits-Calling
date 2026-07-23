import unreal

def find_unused_assets():
    """
    Scans path (default /Game) for usage.
    Returns list of assets with 0 referencers (excluding Maps).
    """
    root_path = "/Game"
    recursive = True
    
    # Get all assets
    all_assets = unreal.EditorAssetLibrary.list_assets(root_path, recursive=recursive)
    
    unused_assets = []
    
    with unreal.ScopedSlowTask(len(all_assets), "Scanning for Unused Assets...") as slow_task:
        slow_task.make_dialog(True)
        
        for asset_path in all_assets:
            if slow_task.should_cancel():
                break
                
            slow_task.enter_progress_frame(1, f"Checking {asset_path}")
            
            # Find Referencers
            # AssetRegistryHelpers is faster than trying to load everything
            referencers = unreal.EditorAssetLibrary.find_package_referencers_for_asset(asset_path, load_assets_to_confirm=False)
            
            # If 0 referencers, it MIGHT be unused.
            # Exceptions:
            # 1. It's a Level (Map) - usually root
            # 2. It's in a specific "Developers" folder
            
            is_level = False
            asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
            if str(asset_data.asset_class_path.asset_name) == "World":
                is_level = True
                
            if len(referencers) == 0 and not is_level:
                unused_assets.append(asset_path)

    # Report
    unreal.log("--- Unused Assets Candidate List ---")
    for ua in unused_assets:
        unreal.log_warning(f"Unused? {ua}")
    
    unreal.log(f"Found {len(unused_assets)} potential unused assets.")
    
    # Optional: Write to file
    # project_dir = unreal.SystemLibrary.get_project_directory()
    # file_path = os.path.join(project_dir, "UnusedAssetsReport.txt")
    # ...

if __name__ == "__main__":
    find_unused_assets()
