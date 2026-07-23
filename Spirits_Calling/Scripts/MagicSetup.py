import unreal

def setup_magic():
    unreal.log_warning("=== MAGIC SETUP START ===")
    
    asset_name = "BP_MagicProjectile"
    package_path = "/Game/Blueprints/Abilities"
    
    # Check/Create Folder
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        unreal.EditorAssetLibrary.make_directory(package_path)
        
    full_path = f"{package_path}/{asset_name}"
    
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        unreal.log_warning(f"Projectile {full_path} already exists.")
        return

    # Create Blueprint
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Actor)
    
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    bp_asset = asset_tools.create_asset(asset_name, package_path, unreal.Blueprint, factory)
    
    # Add Components via Subobject Subsystem
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root_handle = subsystem.k2_gather_subobject_data_for_blueprint(bp_asset)[0]
    
    def add_comp(parent, comp_cls, name):
        params = unreal.AddNewSubobjectParams()
        params.parent_handle = parent
        params.new_class = comp_cls
        params.blueprint_context = bp_asset
        handle, _ = subsystem.add_new_subobject(params)
        if handle.is_valid():
             subsystem.rename_subobject(handle, unreal.Text(name))
        return handle

    # 1. Sphere Collision (Root)
    sphere = add_comp(root_handle, unreal.SphereComponent, "SphereCollision")
    
    # 2. Static Mesh (Visual)
    if sphere:
        mesh = add_comp(sphere, unreal.StaticMeshComponent, "ProjectileMesh")
        # Try to set a default mesh? We can't easily find one without a known path.
        # User can set it manually.

    # 3. Projectile Movement
    movement = add_comp(root_handle, unreal.ProjectileMovementComponent, "ProjectileMovement")
    
    # Compile
    unreal.BlueprintEditorLibrary.compile_blueprint(bp_asset)
    
    unreal.log_warning(f"Created {asset_name}. Please manually set the Static Mesh and Movement Speed.")
    unreal.log_warning("IMPORTANT: Open BP_SpiritPawn and add logic to SpawnActor(BP_MagicProjectile) on Trigger Press.")

if __name__ == "__main__":
    setup_magic()
