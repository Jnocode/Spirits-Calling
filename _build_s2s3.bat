@echo off
del "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt" 2>nul
echo BUILD START %DATE% %TIME% > "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt"
call "D:\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" Spirits_CallingEditor Win64 Development -project="D:\Workspace\03_Dev_Projects\Spirits-Calling\Spirits_Calling\Spirits_Calling.uproject" -waitmutex >> "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt" 2>&1
echo. >> "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt"
echo EXITCODE=%ERRORLEVEL% >> "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt"
echo BUILD END %DATE% %TIME% >> "D:\Workspace\03_Dev_Projects\Spirits-Calling\_build_log.txt"
