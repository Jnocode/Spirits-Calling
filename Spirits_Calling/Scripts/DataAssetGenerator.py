import unreal

def generate_civilization_data_assets():
    unreal.log_warning("=== STARTING CIVILIZATION DATA ASSET GENERATOR (FORCE OVERRIDE) ===")

    base_path = "/Game/SpiritsCalling/Core/CivilizationData"    
    unreal.EditorAssetLibrary.make_directory(base_path)
    
    pda_class = unreal.PDA_MinionData
    
    civilizations = [
        {"name": "Oriental"},
        {"name": "Norse"},
        {"name": "Egyptian"},
        {"name": "Cyberpunk"},
    ]

    factory = unreal.DataAssetFactory()
    created_assets = []
    
    for civ in civilizations:
        asset_name = f"PDA_Minion_{civ['name']}Basic"
        asset_path = f"{base_path}/{asset_name}"
        
        # Aggressive delete if a ghost still remains
        if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
             unreal.EditorAssetLibrary.delete_asset(asset_path)
             
        new_asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name, 
            base_path, 
            pda_class, 
            factory
        )
        
        if new_asset:
            created_assets.append(new_asset)
            unreal.log_warning(f"   [SUCCESS] Created {asset_path}")

    # DO NOT use Python API to save. Let user click 'Save All' manually.

    unreal.log_warning(f"=== COMPLETE. Generated {len(created_assets)} new Data Assets. ===")

if __name__ == "__main__":
    generate_civilization_data_assets()
