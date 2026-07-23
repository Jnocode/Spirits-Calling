import unreal

def configure_gamemode():
    gamemode_path = "/Game/Core/Framework/BP_SpiritsGameMode.BP_SpiritsGameMode_C"
    pawn_path = "/Game/Core/Characters/BP_SpiritPawn.BP_SpiritPawn_C"
    controller_path = "/Game/Core/Controllers/BP_SpiritController.BP_SpiritController_C"
    
    # Load the GameMode Class
    gm_class = unreal.load_object(None, gamemode_path)
    pawn_class = unreal.load_object(None, pawn_path)
    ctrl_class = unreal.load_object(None, controller_path)
    
    if not gm_class or not pawn_class or not ctrl_class:
        unreal.log_error("Could not load classes for GameMode configuration.")
        return
        
    # Get CDO to set defaults
    gm_cdo = unreal.get_default_object(gm_class)
    
    # Transaction
    unreal.SystemLibrary.begin_transaction("Agent Config GameMode", "Set Defaults", gm_cdo)
    
    try:
        # Set Default Pawn
        gm_cdo.set_editor_property("DefaultPawnClass", pawn_class)
        unreal.log_warning("Set DefaultPawnClass -> BP_SpiritPawn")
        
        # Set Player Controller
        gm_cdo.set_editor_property("PlayerControllerClass", ctrl_class)
        unreal.log_warning("Set PlayerControllerClass -> BP_SpiritController")
        
        # Compile/Save not strictly needed for CDO, but good practice to dirty it
        # unreal.EditorAssetLibrary.save_asset(gamemode_path.split('.')[0])
        
    except Exception as e:
        unreal.log_error(f"Failed to set properties: {e}")
        
    unreal.SystemLibrary.end_transaction()
    unreal.log_warning("GameMode Configuration Complete.")

if __name__ == "__main__":
    configure_gamemode()
