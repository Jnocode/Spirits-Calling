import unreal

def move_test():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = subsystem.get_all_level_actors()
    
    pistol = None
    cube = None
    
    # Specific Targets from Level Scan
    # Pistol: BP_Pistol_00 [BP_Pistol_C]
    # Cube: GrabActor_StaticMesh_Physics10 [BP_Grabbable_SmallCube_C]
    
    print(f"Scanning {len(all_actors)} actors...")
    
    for actor in all_actors:
        label = actor.get_actor_label()
        
        if label == "BP_Pistol_00" and not pistol:
            pistol = actor
        
        # Use substring for cube since the number might vary, but "GrabActor" seems to be the prefix
        if "GrabActor" in label and not cube:
            cube = actor
            
        if pistol and cube:
            break
            
    if pistol and cube:
        start_loc = pistol.get_actor_location()
        target_loc = cube.get_actor_location()
        
        # Stack on top (+20 Z)
        # Note: Cube Z is ~96, Pistol Z is ~76. 
        # Target Z should be ~116 to sit on top.
        new_loc = unreal.Vector(target_loc.x, target_loc.y, target_loc.z + 20.0)
        
        unreal.SystemLibrary.begin_transaction("Agent Move Test", "Move Pistol", pistol)
        pistol.set_actor_location(new_loc, False, True)
        unreal.SystemLibrary.end_transaction()
        
        msg = f"✨ SUCCESS: Teleported {pistol.get_actor_label()} to {cube.get_actor_label()}"
        print(msg)
        unreal.log_warning(msg)
    else:
        print("Still missing actors?")
        if not pistol: print("  - Missing BP_Pistol_00")
        if not cube: print("  - Missing GrabActor...")

if __name__ == "__main__":
    move_test()
