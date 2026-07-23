import unreal

def analyze_pawn():
    pawn_path = "/Game/XRFramework/Blueprints/BP_XRPawn"
    
    # Load Asset
    asset = unreal.EditorAssetLibrary.load_asset(pawn_path)
    if not asset:
        unreal.log_error(f"Could not load {pawn_path}")
        return

    # Helper to get formatted string
    report = []
    report.append(f"Analysis of {pawn_path}")
    report.append("=" * 30)
    
    # Get Generated Class to inspect properties/components
    # Blueprints have a 'GeneratedClass' which is the actual UClass
    bp_class = asset.generated_class
    
    # Safe Reflection for Components
    if not asset:
        report.append("  (Asset is None)")
    else:
        report.append(f"  Asset Type: {type(asset)}")
        gen_class = asset.get_editor_property("GeneratedClass") # Use property access
        
        if not gen_class:
            report.append("  (GeneratedClass is None)")
        else:
            report.append(f"  GeneratedClass: {gen_class}")
            cdo = unreal.get_default_object(gen_class)
        report.append(f"  CDO: {cdo}")
        
        # List properties from CDO
        report.append("\n[PROPERTIES (from CDO)]")
        for p in dir(cdo):
            if not p.startswith('_'): # and not callable(getattr(cdo, p)):
                try:
                    val = getattr(cdo, p)
                    report.append(f"  - {p} = {val}")
                except:
                    pass

    # Hardcoded Path
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/PawnAnalysis.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"Analysis saved to {report_path}")

if __name__ == "__main__":
    analyze_pawn()
