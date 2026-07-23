import unreal
import sys
import os

def scaffold_asset_folders():
    unreal.log_warning("=== SPIRITS CALLING ASSET COLLECTION SETUP ===")
    
    # 建立四大文明與核心共用的素材目錄結構
    base_asset_path = "/Game/SpiritsCalling/Assets"
    
    civs = ["Oriental", "Norse", "Egyptian", "Cyberpunk", "Common"]
    categories = ["Meshes", "Materials", "Audio", "Effects", "Textures"]
    
    created_count = 0
    
    for civ in civs:
        civ_path = f"{base_asset_path}/{civ}"
        if not unreal.EditorAssetLibrary.does_directory_exist(civ_path):
            unreal.EditorAssetLibrary.make_directory(civ_path)
            
        for cat in categories:
            cat_path = f"{civ_path}/{cat}"
            if not unreal.EditorAssetLibrary.does_directory_exist(cat_path):
                unreal.EditorAssetLibrary.make_directory(cat_path)
                created_count += 1
                unreal.log_warning(f"Created Folder: {cat_path}")
                
    unreal.log_warning(f"=== SETUP COMPLETE. Created {created_count} asset folders. ===")
    unreal.log_warning("Please import downloded assets (.wav, .fbx, .png) into the corresponding folders.")
    
if __name__ == "__main__":
    scaffold_asset_folders()
