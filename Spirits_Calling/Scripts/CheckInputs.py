import unreal

def check_inputs():
    path = "/Game/Core/Input"
    assets = unreal.EditorAssetLibrary.list_assets(path, recursive=True)
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/InputCheck.txt"
    with open(report_path, "w") as f:
        f.write(f"Found {len(assets)} assets in {path}:\n")
        for a in assets:
            f.write(f" - {a}\n")
    print(f"Check saved to {report_path}")

if __name__ == "__main__":
    check_inputs()
