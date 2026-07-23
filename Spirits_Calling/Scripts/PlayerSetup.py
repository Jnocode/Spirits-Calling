import unreal

def setup_player():
    unreal.log_warning("=== PLAYER SETUP START ===")
    
    asset_path = "/Game/Blueprints/Character/BP_SpiritPawn"
    # Check if asset exists, if not create it (or assume checking logic from previous steps)
    # For this phase, let's assume we are modifying the existing one or finding it.
    
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.log_warning(f"Player Pawn not found at {asset_path}. Please run SetupDemoLevel first or check path.")
        return

    # Load the Blueprint
    bp_asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    
    # We need to modify the SimpleConstructionScript (SCS) or add components to the CDO if it's a C++ parent.
    # For Blueprints, editing SCS is the way to add components purely via Python in Editor.
    
    # 1. Get the Subsystem
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    
    # 2. Gather Data Handles
    root_data_handle = subsystem.k2_gather_subobject_data_for_blueprint(bp_asset)[0]
    
    # Helper to add component
    def add_component(parent_handle, comp_class, name):
        # Check if already exists? (Hard with Subobject API, usually we just add and it auto-renames if duplicate)
        # But let's try to be clean.
        
        params = unreal.AddNewSubobjectParams()
        params.parent_handle = parent_handle
        params.new_class = comp_class
        params.blueprint_context = bp_asset
        
        new_handle, fail_reason = subsystem.add_new_subobject(params)
        if not fail_reason.is_empty():
            unreal.log_error(f"Failed to add {name}: {fail_reason}")
            return None
            
        subsystem.rename_subobject(new_handle, unreal.Text(name))
        unreal.log_warning(f"Added Component: {name}")
        return new_handle

    # Add Left Hand
    left_hand = add_component(root_data_handle, unreal.MotionControllerComponent, "MotionController_L")
    
    # Add Right Hand
    right_hand = add_component(root_data_handle, unreal.MotionControllerComponent, "MotionController_R")
    
    # Add Widget Interaction (attached to Right Hand usually)
    if right_hand:
         add_component(right_hand, unreal.WidgetInteractionComponent, "WidgetInteraction_R")

    # Add Camera (if not present? usually DefaultPawn has one, but let's ensure)
    # add_component(root_data_handle, unreal.CameraComponent, "VRCamera")

    # Compile
    unreal.BlueprintEditorLibrary.compile_blueprint(bp_asset)
    unreal.log_warning("Player Pawn Setup Complete.")

if __name__ == "__main__":
    setup_player()
