import unreal
import os

def organize_assets():
    """
    Moves loose assets from the root /Game/ folder (Content) into typed subfolders.
    Example: /Game/MyTexture -> /Game/Textures/MyTexture
    """
    # 1. Setup Typed Paths
    # format: { unreal_class_name: destination_path }
    type_folders = {
        "Texture2D": "/Game/Textures",
        "Material": "/Game/Materials",
        "MaterialInstanceConstant": "/Game/Materials/Instances",
        "StaticMesh": "/Game/Meshes",
        "SkeletalMesh": "/Game/Characters/Meshes",
        "Blueprint": "/Game/Blueprints",
        "SoundWave": "/Game/Audio",
        "Level": "/Game/Maps",
        "WidgetBlueprint": "/Game/UI",
        "NiagaraSystem": "/Game/VFX",
    }

    # 2. Get all assets in the root Content folder (excluding existing subfolders if possible, but comprehensive search is safer)
    # We'll focus on the root path "/Game" to avoid messing up existing structures too much initially
    # Or strict cleanup: Check assets directly in /Game/
    
    root_path = "/Game"
    assets_in_root = unreal.EditorAssetLibrary.list_assets(root_path, recursive=False, include_folder=False)

    moved_count = 0
    
    with unreal.ScopedSlowTask(len(assets_in_root), "Organizing Root Assets...") as slow_task:
        slow_task.make_dialog(True)
        
        for asset_path in assets_in_root:
            if slow_task.should_cancel():
                break
                
            asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
            asset_class = asset_data.asset_class_path.asset_name # UE5.1+ uses asset_class_path.asset_name
            # For older UE5 versions, it might be asset_data.asset_class
            
            # Compatible class name retrieval
            class_name = str(asset_class)
            
            slow_task.enter_progress_frame(1, f"Processing {asset_path}")

            if class_name in type_folders:
                dest_folder = type_folders[class_name]
                asset_name = asset_data.asset_name
                dest_path = f"{dest_folder}/{asset_name}"
                
                # Don't move if already there (logic is implicitly handled by list_assets(root_path, recursive=False))
                
                # Check collision
                if unreal.EditorAssetLibrary.does_asset_exist(dest_path):
                    unreal.log_warning(f"Skipped {asset_path} -> {dest_path} (Collision)")
                    continue
                    
                # Create directory doesn't need explicit call, RenameAsset handles it? 
                # Better to be safe: EditorAssetLibrary doesn't have create_directory, but Rename creates path.
                
                result = unreal.EditorAssetLibrary.rename_asset(asset_path, dest_path)
                if result:
                    unreal.log(f"Moved {class_name}: {asset_path} -> {dest_path}")
                    moved_count += 1
                else:
                    unreal.log_error(f"Failed to move {asset_path}")

    unreal.log(f"Organization Complete. Moved {moved_count} assets.")

if __name__ == "__main__":
    organize_assets()
