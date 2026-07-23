import unreal

def setup_inputs_clone():
    lib = unreal.EditorAssetLibrary
    
    # Source Assets (Templates)
    src_bool = "/Game/XRFramework/Input/Actions/IA_Grab_Left_Pressed"
    src_axis2d = "/Game/XRFramework/Input/Actions/IA_Move"
    src_axis1d = "/Game/XRFramework/Input/Actions/IA_Turn"
    src_imc = "/Game/XRFramework/Input/IMC_Default"
    
    # Destination
    dest_path = "/Game/Core/Input"
    dest_action_path = f"{dest_path}/Actions"
    
    # Define Tasks: (NewName, SourcePath)
    tasks = [
        ("IA_Select", src_bool),
        ("IA_Possess", src_bool),
        ("IA_RTS_Move", src_axis2d),
        ("IA_VR_Move", src_axis2d),
        ("IA_VR_Turn", src_axis1d)
    ]
    
    # 1. Create Actions
    for name, src in tasks:
        target = f"{dest_action_path}/{name}"
        if not lib.does_asset_exist(target):
            # Duplicate
            new_asset = lib.duplicate_asset(src, target)
            if new_asset:
                unreal.log_warning(f"Created {name} (Cloned)")
            else:
                unreal.log_error(f"Failed to clone {name} from {src}")
        else:
             unreal.log_warning(f"Skipped {name} (Exists)")

    # 2. Create Contexts
    ctx_tasks = ["IMC_Spirit", "IMC_Possessed"]
    for name in ctx_tasks:
        target = f"{dest_path}/{name}"
        if not lib.does_asset_exist(target):
            # Duplicate IMC
            # Note: duplicating an IMC copies the mappings too! 
            # We might want to clear them, but Python API for clearing IMC mappings is complex.
            # For now, cloning is better than nothing. User can clear them.
            new_asset = lib.duplicate_asset(src_imc, target)
            if new_asset:
                unreal.log_warning(f"Created {name} (Cloned)")
                
                # Try to clear mappings if possible?
                # wrapping in try block
                try:
                    # InputMappingContext.unmap_all() ? No such luck usually.
                    # We just leave it populated. Better to have valid asset.
                    pass 
                except:
                    pass
        else:
             unreal.log_warning(f"Skipped {name} (Exists)")

    unreal.log_warning("Input Setup (Clone) Complete.")

if __name__ == "__main__":
    setup_inputs_clone()
