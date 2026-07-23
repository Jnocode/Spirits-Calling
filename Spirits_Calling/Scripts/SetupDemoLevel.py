import unreal

def setup_demo_level():
    # 1. Load or Create Level
    unreal.log_warning("MCP_RESP_SETUP_START")
    level_path = "/Game/Maps/DemoMap"
    if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
        world = unreal.EditorLevelLibrary.new_level(level_path)
    else:
        unreal.EditorLevelLibrary.load_level(level_path)
    
    # 2. Add Floor (Static Mesh)
    # Using specific cube from the project or generic?
    # Found "/Game/LevelPrototyping/Interactable/Door/Meshes/SM_DoorFrame_Edge" in previous scan?
    # Let's try to find a basic cube.
    cube_path = "/Engine/BasicShapes/Cube" # Standard
    
    # Create Floor
    floor_actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
        unreal.load_asset(cube_path), 
        unreal.Vector(0, 0, -50), 
        unreal.Rotator(0, 0, 0)
    )
    if floor_actor:
        floor_actor.set_actor_label("Ground")
        floor_actor.set_actor_scale3d(unreal.Vector(20, 20, 1)) # 20m x 20m floor
        
    # 3. Add Dummy Unit (BP_UnitBase)
    unit_bp = unreal.load_asset("/Game/Core/Characters/BP_UnitBase")
    if unit_bp:
        unit = unreal.EditorLevelLibrary.spawn_actor_from_object(
            unit_bp, 
            unreal.Vector(200, 200, 50), 
            unreal.Rotator(0, 0, 0)
        )
        if unit:
            unit.set_actor_label("MyMinion_01")
    
    # 4. Add Player Start
    # unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PlayerStart, ...)
    # Note: spawn_actor_from_class might be restricted in some implementations or named differently
    # spawn_actor_from_object works if we have the class asset.
    # Simpler: Spawn BP_SpiritPawn directly to ensure possesion? 
    # No, PlayerStart is better for GameMode handling.
    ps_class = unreal.PlayerStart
    # Need to find how to spawn by class in Python API if 'spawn_actor_from_class' is missing
    # unreal.EditorLevelLibrary.spawn_actor_from_class(ps_class, location, rotation)
    
    try:
        ps = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.PlayerStart, 
            unreal.Vector(0, 0, 500), 
            unreal.Rotator(0, 0, 0)
        )
    except:
        unreal.log_warning("Could not spawn PlayerStart via class. Skipping.")

    # Save
    unreal.EditorLevelLibrary.save_current_level()
    unreal.log_warning("Demo Level Setup Complete.")

if __name__ == "__main__":
    setup_demo_level()
