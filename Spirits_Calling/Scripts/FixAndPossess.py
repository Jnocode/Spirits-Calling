import unreal

def fix_and_possess():
    # 1. Force Fix GameMode Defaults (Again)
    gm_path = "/Game/Core/Framework/BP_SpiritsGameMode.BP_SpiritsGameMode_C"
    pawn_path = "/Game/Core/Characters/BP_SpiritPawn.BP_SpiritPawn_C"
    
    gm_class = unreal.load_object(None, gm_path)
    pawn_class = unreal.load_object(None, pawn_path)
    
    if gm_class and pawn_class:
        cdo = unreal.get_default_object(gm_class)
        # Using string names for properties if set_editor_property is flaky?
        # But set_editor_property is the standard.
        try:
            cdo.set_editor_property("DefaultPawnClass", pawn_class)
            unreal.log_warning("Forced DefaultPawnClass -> BP_SpiritPawn")
        except Exception as e:
            unreal.log_error(f"Failed to config GameMode: {e}")
            
    # 2. Possess Logic (Fixed for PIE visibility)
    # Get the Game World (PIE)
    editor_sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie_world = editor_sub.get_game_world()
    
    if not pie_world:
        unreal.log_error("NO PIE WORLD DETECTED. Game is not running?")
        return
        
    # Get PC
    pc = unreal.GameplayStatics.get_player_controller(pie_world, 0)
    if not pc:
        # Sometimes Index 0 is not ready
        unreal.log_warning("PC 0 not found. Listing all controllers...")
        # Fallback?
        return

    # Find Minion
    unit_class = unreal.load_object(None, "/Game/Core/Characters/BP_UnitBase.BP_UnitBase_C")
    actors = unreal.GameplayStatics.get_all_actors_of_class(pie_world, unit_class)
    
    if actors:
        target = actors[0]
        pc.possess(target)
        unreal.log_warning(f"POSSESSED: {target.get_name()}")
    else:
        unreal.log_error("No Minion found in PIE to possess.")

if __name__ == "__main__":
    fix_and_possess()
