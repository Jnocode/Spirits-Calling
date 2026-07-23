import os
path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/TestWrite.txt"
try:
    with open(path, "w") as f:
        f.write("MCP Write Test Success")
    print(f"FILESYSTEM: Written to {path}")
except Exception as e:
    print(f"FILESYSTEM ERROR: {e}")
