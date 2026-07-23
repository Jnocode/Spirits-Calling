import unreal
import sys

def create_core_architecture():
    unreal.log_warning("=== SPIRITS CALLING CORE ARCHITECTURE SETUP START ===")
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    
    # 1. Base Folders
    folders = [
        "/Game/SpiritsCalling/Core/Controllers",
        "/Game/SpiritsCalling/Core/Characters",
        "/Game/SpiritsCalling/Core/Data",
        "/Game/SpiritsCalling/Core/Components"
    ]
    
    for folder in folders:
        if not unreal.EditorAssetLibrary.does_directory_exist(folder):
            unreal.EditorAssetLibrary.make_directory(folder)
            unreal.log_warning(f"Created directory: {folder}")

    created_assets = []

    def create_blueprint(name, path, parent_class):
        full_path = f"{path}/{name}"
        if not unreal.EditorAssetLibrary.does_asset_exist(full_path):
            factory = unreal.BlueprintFactory()
            factory.set_editor_property("parent_class", parent_class)
            asset = asset_tools.create_asset(name, path, unreal.Blueprint, factory)
            if asset:
                unreal.BlueprintEditorLibrary.compile_blueprint(asset)
                created_assets.append(name)
                unreal.log_warning(f"Created Blueprint: {full_path}")
            return asset
        else:
            unreal.log_warning(f"Blueprint {full_path} already exists. Skipping.")
            return None

    def create_data_asset(name, path, data_class):
        full_path = f"{path}/{name}"
        if not unreal.EditorAssetLibrary.does_asset_exist(full_path):
            factory = unreal.DataAssetFactory()
            # In Python, creating specific PrimaryDataAsset classes can be tricky if they aren't instantiated in C++ first.
            # For this MVP script, we'll create a basic PrimaryDataAsset to serve as a placeholder for PDA_MinionData.
            # If a base C++ class exists, it should be used instead of PrimaryDataAsset.
            asset = asset_tools.create_asset(name, path, data_class, factory)
            if asset:
                created_assets.append(name)
                unreal.log_warning(f"Created Data Asset: {full_path}")
            return asset
        else:
            unreal.log_warning(f"Data Asset {full_path} already exists. Skipping.")
            return None

    # Step 1: Controllers
    create_blueprint("BP_SpiritsPlayerController", folders[0], unreal.PlayerController)

    # Step 2: Pawns
    # BP_CommanderPawn (VR)
    create_blueprint("BP_CommanderPawn", folders[1], unreal.Pawn)
    
    # BP_BaseMinion (RTS)
    create_blueprint("BP_BaseMinion", folders[1], unreal.Character)

    # Step 3: Data Assets Setup (Placeholder for PDA_MinionData)
    # Ideally,PDA_MinionData should be a C++ class inheriting from UPrimaryDataAsset.
    # Here we create a Blueprint based on PrimaryDataAsset so designers can add variables.
    pda_bp = create_blueprint("BP_PDA_MinionData_Base", folders[2], unreal.PrimaryDataAsset)
    
    # Step 4: Create some default instances for the 4 civilizations (assuming they will inherit from the base PDA)
    # Note: Cannot directly create DataAssets from a Blueprint class via script easily without C++ base, 
    # so we log instruction.
    unreal.log_warning("IMPORTANT: Please add variables (Health, Mesh, CivType) to BP_PDA_MinionData_Base in the editor.")
    unreal.log_warning("Then create Data Asset instances for Oriental, Norse, Egyptian, Cyberpunk manually or via C++.")

    
    if created_assets:
        unreal.log_warning(f"=== SETUP COMPLETE. Created {len(created_assets)} core assets. ===")
    else:
        unreal.log_warning("=== SETUP COMPLETE. No new assets were created. ===")

if __name__ == "__main__":
    create_core_architecture()
