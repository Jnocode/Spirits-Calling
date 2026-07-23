import unreal

def scaffold_refactor():
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    
    # Target Path
    base_path = "/Game/Core/Characters"
    
    # Ensure directories exist (simple dummy create/delete trick or just assume)
    # AssetTools creates folder if missing usually.
    
    created_assets = []
    
    # 1. BP_SpiritController
    # Parent: PlayerController
    name = "BP_SpiritController"
    path = "/Game/Core/Controllers"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{path}/{name}"):
        bp_factory = unreal.BlueprintFactory()
        bp_factory.set_editor_property("ParentClass", unreal.PlayerController)
        asset = asset_tools.create_asset(name, path, unreal.Blueprint, bp_factory)
        created_assets.append(name)
        unreal.log_warning(f"Created {name}")

    # 2. BP_UnitBase
    # Parent: Character
    name = "BP_UnitBase"
    path = "/Game/Core/Characters"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{path}/{name}"):
        bp_factory = unreal.BlueprintFactory()
        bp_factory.set_editor_property("ParentClass", unreal.Character)
        asset = asset_tools.create_asset(name, path, unreal.Blueprint, bp_factory)
        created_assets.append(name)
        unreal.log_warning(f"Created {name}")
        
    # 3. BPC_VRMovement
    # Parent: ActorComponent
    name = "BPC_VRMovement"
    path = "/Game/Core/Components"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{path}/{name}"):
        bp_factory = unreal.BlueprintFactory()
        bp_factory.set_editor_property("ParentClass", unreal.ActorComponent)
        asset = asset_tools.create_asset(name, path, unreal.Blueprint, bp_factory)
        created_assets.append(name)
        unreal.log_warning(f"Created {name}")

    # Report
    if created_assets:
        msg = f"Refactoring Scaffold Complete. Created: {', '.join(created_assets)}"
    else:
        msg = "Refactoring Scaffold skipped (Assets already exist)."
        
    print(msg)
    unreal.log_warning(msg)

if __name__ == "__main__":
    scaffold_refactor()
