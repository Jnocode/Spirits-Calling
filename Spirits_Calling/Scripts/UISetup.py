import unreal

def setup_ui():
    unreal.log_warning("=== UI SETUP START ===")
    
    asset_name = "WBP_HUD"
    package_path = "/Game/UI"
    
    # Check/Create Folder
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        unreal.EditorAssetLibrary.make_directory(package_path)
    
    # Create Widget Blueprint
    factory = unreal.WidgetBlueprintFactory()
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    
    # Check existence
    full_path = f"{package_path}/{asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        unreal.log_warning(f"UI {full_path} already exists. Loading...")
        bp_asset = unreal.EditorAssetLibrary.load_asset(full_path)
    else:
        bp_asset = asset_tools.create_asset(asset_name, package_path, unreal.WidgetBlueprint, factory)
        unreal.log_warning(f"Created UI: {full_path}")

    # Note: Manipulating UMG Widget Hierarchy via Python is extremely limited/experimental in UE5.
    # The standard Python API does NOT expose UWidgetTree easily for editing.
    # Strategy: We will rely on the user to manually add the text blocks or use a pre-made asset if possible.
    # OR: We can use `unreal.SubobjectDataSubsystem` if the widget tree is exposed as subobjects (rarely works well).
    
    # ALTERNATIVE: We just create the asset and log instructions.
    # BUT, let's try to see if we can at least open it for them.
    unreal.AssetEditorSubsystem().open_editor_for_assets([bp_asset])
    
    unreal.log_warning("""
    IMPORTANT: Python cannot fully construct UMG Widget Trees (Canvas, Text, etc.) reliably.
    Please manually:
    1. Open WBP_HUD.
    2. Add a 'Canvas Panel'.
    3. Add a Text Block named 'HealthText' (top left).
    4. Add a Text Block named 'WaveText' (top right).
    5. Compile & Save.
    """)

if __name__ == "__main__":
    setup_ui()
