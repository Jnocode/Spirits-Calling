import unreal

def demo_possess():
    unreal.log_warning("=== POSSESSION DEMO START ===")
    
    # We must be in PIE (Play In Editor) for possession to work correctly.
    # We will try to find a PIE world.
    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie_world = editor_subsystem.get_game_world()
            
    if not pie_world:
        unreal.log_error("[ERROR] You are not currently in Play mode (PIE). Please press 'Play' in the editor, wait 2 seconds, and run this script again.")
        return

    # 1. Get the local Player Controller
    pc = unreal.GameplayStatics.get_player_controller(pie_world, 0)
    if not pc:
        unreal.log_error("[ERROR] No Player Controller found in PIE.")
        return

    unreal.log_warning(f"Found PlayerController: {pc.get_name()}")

    # 2. Spawn a basic Pawn to act as our Minion
    # First, let's load a standard Pawn class or use a basic default class if custom is not compiled
    pawn_class = unreal.Pawn.static_class()
    
    # Try to load our BP_BaseMinion if it exists
    bp_minion_class = unreal.load_class(None, "/Game/SpiritsCalling/Core/Characters/BP_BaseMinion.BP_BaseMinion_C")
    if bp_minion_class:
        pawn_class = bp_minion_class
        unreal.log_warning("Found BP_BaseMinion architecture class. Spawning as Minion.")
    else:
        unreal.log_warning("BP_BaseMinion not compiled or found. Spawning default Pawn instead.")

    # Spawn Location: Just ahead of the current camera/pawn
    current_pawn = pc.get_pawn()
    spawn_loc = unreal.Vector(0, 0, 100) # Fallback
    spawn_rot = unreal.Rotator(0, 0, 0)
    
    if current_pawn:
        unreal.log_warning(f"Currently possessing: {current_pawn.get_name()}")
        spawn_loc = current_pawn.get_actor_location() + current_pawn.get_actor_forward_vector() * 200.0

    unreal.log_warning(f"Spawning Target Pawn at {spawn_loc}...")
    
    new_pawn = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(
        pie_world, 
        pawn_class, 
        unreal.Transform(location=spawn_loc, rotation=spawn_rot), 
        unreal.SpawnActorCollisionHandlingMethod.ADJUST_IF_POSSIBLE_BUT_ALWAYS_SPAWN
    )
    
    # Add a visual component if it's just a default pawn so we can verify possession easily
    if new_pawn and not bp_minion_class:
         # Hard to dynamically add components in pure Python after spawn, but we can 
         pass

    if new_pawn:
        unreal.GameplayStatics.finish_spawning_actor(new_pawn, unreal.Transform(location=spawn_loc, rotation=spawn_rot))
        unreal.log_warning(f"Successfully spawned {new_pawn.get_name()}.")
        
        # 3. POSSESS
        unreal.log_warning("Executing Possession...")
        pc.possess(new_pawn)
        
        # Verify
        check_pawn = pc.get_pawn()
        if check_pawn == new_pawn:
             unreal.log_warning(">>> SUCCESS! Control has been seamlessly transformed to the new Minion. <<<")
             unreal.log_warning("The VR Player has now taken first-person control of the unit.")
        else:
             unreal.log_error("Possession call failed. The engine rejected the switch.")
    else:
        unreal.log_error("Failed to spawn target Pawn.")

if __name__ == "__main__":
    demo_possess()
