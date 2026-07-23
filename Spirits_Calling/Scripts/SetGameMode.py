import unreal

def set_gamemode():
    # 1. Load the new GameMode
    gm_path = "/Game/Core/Framework/BP_SpiritsGameMode.BP_SpiritsGameMode_C"
    gm_class = unreal.load_object(None, gm_path)
    
    if not gm_class:
        unreal.log_error("Could not load BP_SpiritsGameMode!")
        return

    # 2. Update Project Settings (Global)
    # Get Maps & Modes Settings
    # Note: accessing ProjectSettings via Python is via config or specific ProjectSettings objects
    # easier way: Set it in the World Settings of the current level
    
    # 3. Update Current Level World Settings
    world = unreal.EditorLevelLibrary.get_editor_world()
    world_settings = world.get_world_settings()
    
    # 'DefaultGameMode' property on WorldSettings
    try:
        world_settings.set_editor_property("DefaultGameMode", gm_class)
        unreal.log_warning("Set DemoMap GameMode Override -> BP_SpiritsGameMode")
    except Exception as e:
        unreal.log_error(f"Failed to set World Settings: {e}")

    # 4. Also try to force the GameMode class in the Project Settings (Config)
    # This ensures Play In Editor uses it if no override
    # unreal.GeneralProjectSettings? No, MapsAndModesSettings
    # Configuring via set_engine_config specific keys might work
    # [/Script/EngineSettings.GameMapsSettings]
    # GlobalDefaultGameMode="/Game/Core/Framework/BP_SpiritsGameMode.BP_SpiritsGameMode_C"
    
    unreal.EditorLevelLibrary.save_current_level()

if __name__ == "__main__":
    set_gamemode()
