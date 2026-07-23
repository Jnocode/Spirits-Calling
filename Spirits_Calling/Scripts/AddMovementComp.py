
import unreal

def add_movement_component():
    pawn_path = "/Game/Core/Characters/BP_SpiritPawn"
    
    # Load the Blueprint
    bp_asset = unreal.EditorAssetLibrary.load_asset(pawn_path)
    if not bp_asset:
        print(f"Error: Could not load {pawn_path}")
        return

    # Get the SubobjectDataSubsystem (standard way to edit components in UE5 Python)
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    
    # Grab the data handle for the Blueprint
    bp_handle = subsystem.k2_gather_subobject_data_for_blueprint(bp_asset)
    
    # Check if Movement Component already exists
    # (Simplified check: just look at names in the handle list)
    # We will just try to add it.
    
    # Class to add: FloatingPawnMovement
    component_class = unreal.FloatingPawnMovement
    
    # Add the component to the Root Actor (first handle usually)
    root_handle = bp_handle[0]
    
    params = unreal.AddNewSubobjectParams()
    params.parent_handle = root_handle
    params.new_class = component_class
    params.blueprint_context = bp_asset
    
    try:
        fail_reason = unreal.Text()
        new_handle, fail_reason = subsystem.add_new_subobject(params, fail_reason)
        if not new_handle.is_valid():
            print(f"Failed to add component: {fail_reason}")
        else:
            print("Successfully added FloatingPawnMovement component!")
            
            # Use a slightly different method to rename if needed, 
            # but default name is fine.
            
    except Exception as e:
        print(f"Exception during component add: {e}")

    # Compile the Blueprint
    unreal.EditorAssetLibrary.save_loaded_asset(bp_asset)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp_asset)

add_movement_component()
