import unreal

def setup_gamemode_assets():
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    
    # 1. BP_SpiritPawn (DefaultPawn parent provides simple movement)
    name = "BP_SpiritPawn"
    path = "/Game/Core/Characters"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{path}/{name}"):
        bp_factory = unreal.BlueprintFactory()
        bp_factory.set_editor_property("ParentClass", unreal.DefaultPawn)
        asset_tools.create_asset(name, path, unreal.Blueprint, bp_factory)
        unreal.log_warning(f"Created {name}")

    # 2. BP_SpiritsGameMode
    name = "BP_SpiritsGameMode"
    path = "/Game/Core/Framework"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{path}/{name}"):
        bp_factory = unreal.BlueprintFactory()
        bp_factory.set_editor_property("ParentClass", unreal.GameModeBase)
        asset_tools.create_asset(name, path, unreal.Blueprint, bp_factory)
        unreal.log_warning(f"Created {name}")

    unreal.log_warning("GameMode Assets Created.")

if __name__ == "__main__":
    setup_gamemode_assets()
