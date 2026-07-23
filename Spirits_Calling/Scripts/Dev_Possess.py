import unreal

def dev_possess():
    # 1. Get Player Controller
    # In Editor, we can access the world via EditorLevelLibrary or GameplayStatics? 
    # GameplayStatics might not work well in Editor context unless PIE is running.
    # But since we are running via MCP (Remote Execution), we *might* be able to affect PIE if it's running via "WorldContextObject".
    
    # However, Python usually runs in Editor World, not PIE World.
    # To affect PIE, we need to find the PIE World.
    
    worlds = unreal.SystemLibrary.get_all_worlds()
    pie_world = None
    for w in worlds:
        if w.get_world_type() == unreal.WorldType.PIE:
            pie_world = w
            break
            
    if not pie_world:
        unreal.log_error("NO PIE WORLD FOUND. Please press PLAY in Editor first.")
        return

    # 2. Get PC in PIE
    # We can assume Index 0
    # Note: KismetSystemLibrary functionality
    pc = unreal.GameplayStatics.get_player_controller(pie_world, 0)
    
    if not pc:
        unreal.log_error("Could not find Player Controller in PIE.")
        return
        
    # 3. Find Minion in PIE
    # We need to find the actor "MyMinion_01" BUT in the PIE world, it might be named differently (cloned).
    # Best to iterate actors in PIE world of class BP_UnitBase
    
    # Load class to filter
    unit_class = unreal.load_object(None, "/Game/Core/Characters/BP_UnitBase.BP_UnitBase_C")
    
    actors = unreal.GameplayStatics.get_all_actors_of_class(pie_world, unit_class)
    target_pawn = None
    if actors:
        target_pawn = actors[0] # Just grab the first one
        
    if target_pawn and pc:
        # 4. POSSESS!
        pc.possess(target_pawn)
        unreal.log_warning(f"Forced Possession of {target_pawn.get_name()} by {pc.get_name()}")
    else:
        unreal.log_error("Target Pawn not found in PIE.")

if __name__ == "__main__":
    dev_possess()
