import unreal

def improve_scene():
    # 1. Load Level
    level_path = "/Game/Maps/DemoMap"
    unreal.EditorLevelLibrary.load_level(level_path)
    
    lib = unreal.EditorLevelLibrary
    
    # 2. Add Lighting (Sun, Sky, Fog)
    # Check if they exist to avoid duplicates
    existing_actors = lib.get_all_level_actors()
    has_light = any(a.get_class().get_name() == "DirectionalLight" for a in existing_actors)
    
    if not has_light:
        # Sun
        sun = lib.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0,0,1000), unreal.Rotator(-50, -30, 0))
        sun.set_actor_label("Sun")
        # Make it bright
        # (Properties might need specific component access)
        
        # Sky Atmosphere
        lib.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
        
        # Sky Light
        lib.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
        
        # Exponential Height Fog
        lib.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
        
        unreal.log_warning("Added Lighting & Sky.")

    # 3. Enhance BP_UnitBase Visuals
    # Find a mesh to use. 
    # VR Template usually has: /Game/XRMannequins/Mesh/SKM_Manny_Simple.SKM_Manny_Simple
    # Or /Game/Mannequin/Character/Mesh/SK_Mannequin
    
    mesh_path = "/Game/XRMannequins/Mesh/SKM_Manny_Simple"
    mesh_asset = unreal.load_asset(mesh_path)
    if not mesh_asset:
        # Fallback
        mesh_path = "/Game/Mannequin/Character/Mesh/SK_Mannequin" 
        mesh_asset = unreal.load_asset(mesh_path)
        
    if mesh_asset:
        # We need to set this mesh on the BP_UnitBase CDO
        bp_path = "/Game/Core/Characters/BP_UnitBase.BP_UnitBase_C"
        bp_class = unreal.load_object(None, bp_path)
        if bp_class:
            cdo = unreal.get_default_object(bp_class)
            # Character has a 'Mesh' component (SkeletalMeshComponent)
            # In Python, accessing inherited component properties on CDO is tricky.
            # But we can try to set it on the *Instance* in the level first for immediate gratification.
            
            # Find the unit in level
            actors = lib.get_all_level_actors()
            minion = next((a for a in actors if "MyMinion" in a.get_actor_label()), None)
            
            if minion:
                # Get the Mesh Component
                # Character -> Mesh
                mesh_comp = minion.get_editor_property("Mesh")
                if mesh_comp:
                    mesh_comp.set_editor_property("SkeletalMeshAsset", mesh_asset)
                    # Shift it down to align with capsule (usually -90 Z)
                    mesh_comp.set_relative_location(unreal.Vector(0, 0, -90))
                    mesh_comp.set_relative_rotation(unreal.Rotator(0, -90, 0))
                    unreal.log_warning(f"Updated Minion Mesh to {mesh_asset.get_name()}")
    
    lib.save_current_level()

if __name__ == "__main__":
    improve_scene()
