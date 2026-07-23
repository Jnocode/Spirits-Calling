import unreal

def add_components_to_pawn():
    pawn_path = "/Game/Core/Characters/BP_SpiritPawn"
    asset = unreal.load_asset(pawn_path)
    
    if not asset:
        unreal.log_error("Pawn not found.")
        return

    # Use Subobject Data Subsystem (modern way)
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    
    # 1. Gather Data Handle
    handles = subsystem.k2_gather_subobject_data_for_blueprint(asset)
    root_handle = handles[0] # Usually the root (SCS Node or Inherited)
    
    # We need to find the specific handle for the "RootComponent" or "Capsule" to attach to
    # DefaultPawn has a CollisionComponent as Root.
    
    # 2. Add SpringArm
    # params: Handle to attach to, Class to add, Name, ...
    # create_new_subobject(handle, new_class, new_name)
    
    # Transaction
    unreal.SystemLibrary.begin_transaction("Add Camera", "Python Add Components", asset)
    
    try:
        # Create SpringArm
        spring_arm_handle, fail_reason = subsystem.add_new_subobject(
            unreal.SubobjectDataHandle(root_handle), 
            unreal.SpringArmComponent, 
            unreal.Name("RTS_SpringArm")
        )
        
        if not fail_reason.is_empty():
            unreal.log_error(f"Failed to add SpringArm: {fail_reason}")
        else:
            unreal.log_warning("Added SpringArm")
            
            # Configure SpringArm (defaults: -60 deg pitch, 1000 length)
            # Accessing the template object?
            # data = subsystem.k2_find_subobject_data_from_handle(spring_arm_handle)
            # obj = data.get_object() (?)
            # Setting properties on the template is hard via this API directly in one go.
            
            # Create Camera attached to SpringArm
            cam_handle, fail_reason_2 = subsystem.add_new_subobject(
                spring_arm_handle, 
                unreal.CameraComponent, 
                unreal.Name("RTS_Camera")
            )
            
            if not fail_reason_2.is_empty():
                 unreal.log_error(f"Failed to add Camera: {fail_reason_2}")
            else:
                 unreal.log_warning("Added Camera")
                 
    except Exception as e:
        unreal.log_error(f"Error adding components: {e}")
        
    unreal.SystemLibrary.end_transaction()
    
    # Compile
    unreal.EditorAssetLibrary.save_asset(pawn_path)
    unreal.AssetEditorSubsystem().open_editor_for_asset(asset) # Open it for user to check

if __name__ == "__main__":
    add_components_to_pawn()
