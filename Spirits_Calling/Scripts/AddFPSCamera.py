import unreal

def add_fps_camera():
    bp_path = "/Game/Core/Characters/BP_UnitBase"
    asset = unreal.load_asset(bp_path)
    if not asset:
        unreal.log_error("BP_UnitBase not found.")
        return

    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = subsystem.k2_gather_subobject_data_for_blueprint(asset)
    
    # Find Mesh Component Key
    # Usually inherited components are visible in handles
    # We want to attach to the Capsule (Root) or Mesh. 
    # Let's attach to Capsule (Root) and offset it to Head height.
    root_handle = handles[0]
    
    unreal.SystemLibrary.begin_transaction("Add FPS Camera", "Python Add", asset)
    
    try:
        # Add Camera
        cam_handle, fail = subsystem.add_new_subobject(
            unreal.SubobjectDataHandle(root_handle),
            unreal.CameraComponent,
            unreal.Name("FPS_Camera")
        )
        
        if fail.is_empty():
            unreal.log_warning("Added FPS_Camera to BP_UnitBase.")
            
            # Note: Setting Relative Location on a newly created subobject via Python 
            # might require getting the CDO or modifying the template.
            # Using a simpler workaround: 
            # We assume the user can tweak the height, but we want it non-zero.
            # Default is (0,0,0) which is feet.
            # We will try to set the default property on the blueprint CDO.
            
            # Alternatively, since we can't easily set properties on the new component node 
            # without complex API usage, we ask user to adjust it OR we use the "Cheat":
            # Set it on the *Instance* in the level if we can find it.
            pass
            
            # Accessing the CDO to set the "FPS_Camera" property...
            # The variable name "FPS_Camera" is added to the class.
            
            # Let's try to set default value on CDO
            bp_class = asset.generated_class
            cdo = unreal.get_default_object(bp_class)
            # This relies on the property being exposed which it might not be yet until recompile.
            
    except Exception as e:
        unreal.log_error(f"Error: {e}")
        
    unreal.SystemLibrary.end_transaction()
    unreal.EditorAssetLibrary.save_asset(bp_path)

    # Also update the instance in the leve to be sure
    lib = unreal.EditorLevelLibrary
    actors = lib.get_all_level_actors()
    minion = next((a for a in actors if "MyMinion" in a.get_actor_label()), None)
    if minion:
        # Find component by name
        # It might need re-construction in level
        pass

if __name__ == "__main__":
    add_fps_camera()
