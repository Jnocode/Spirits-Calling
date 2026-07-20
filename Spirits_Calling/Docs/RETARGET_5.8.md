# Spirits Calling — UE 5.7 → 5.8 Retarget 記錄

> 日期：2026-07-20 ｜ 觸發：冒煙測試 harness `--build` 挖出專案編不動

## 根因（root blocker）

- 舊綁定引擎 **UE 5.7 已被使用者移除**；`E:/UE_5.7/Engine/Binaries/Win64/` 為空、無 `Build/BatchFiles`。
- 機器上唯一完整引擎 = **`D:\Epic Games\UE_5.8`**（Launcher promoted build，`++UE5+Release-5.8`）。
- 2026-07-06 的綠燈是在當時還在的 5.7 上跑的；5.7 被砍後專案成孤兒 → 編不動 → 無法打包 → 無法上架。

## 修改項（commit：retarget UE 5.7 -> 5.8）

| 檔案 | 改動 |
|------|------|
| `Spirits_Calling.uproject` | `EngineAssociation` `5.7` → `5.8` |
| `_build_s2s3.bat` | `call` 引擎路徑 `E:\UE_5.7\...` → `D:\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat` |
| `Source/Spirits_Calling.Target.cs` | `DefaultBuildSettings` `V6` → `V7` |
| `Source/Spirits_CallingEditor.Target.cs` | `DefaultBuildSettings` `V6` → `V7` |

## 關鍵 pitfall：BuildSettingsVersion V6→V7

第一次重編爆 `OtherCompilationError`，**不是 C++ source API 破壞**，而是 UBT 設定衝突：

```
Spirits_CallingEditor modifies the values of properties:
[ UnreachableCodeWarningLevel: Off != Error, ReturnTypeWarningLevel: Off != Error,
  DanglingWarningLevel: Off != Error ]. This is not allowed, as Spirits_CallingEditor
has build products in common with UnrealEditor.
```

- UE 5.8 在 `BuildSettingsVersion.V7` 把這三個 warning level 預設為 `Error`
  （證據：`UnrealBuildTool/Configuration/Rules/CppCompileWarnings.cs` 的 `VersionWarningLevelDefault(WarningLevel.Error, V7, Latest, ...)`）。
- 專案停在 V6 → 這三個維持 `Off` → 與 installed engine（共用 build products）的 Error 衝突 → UBT 直接擋。
- 修法：兩個 Target.cs `DefaultBuildSettings` 升 V7，讓預設對齊 Error。升 V7 後全量重編 **Result: Succeeded / EXITCODE=0，零 source 修改**。

## 流程備忘（乾淨 retarget）

1. 備份 uproject + build bat（`D:/Workspace/artifacts/spirits-retarget-5.8/backups/`）。
2. 改 uproject `EngineAssociation` 與 build bat 引擎路徑。
3. 清 `Intermediate/Build`、`Binaries/Win64`（強制乾淨、避免舊版本 artifact 撞車）。
4. UBT `-projectfiles` 重新產生 sln（against 5.8）。
5. 全量重編；讀 `_build_log.txt` 的 `EXITCODE=` 判定（**別信 bat wrapper 的 exit code**，最後一行 echo 會蓋掉真值）。
6. harness `smoke_preflight.py` 獨立回讀驗證。

## 驗證

- `_build_log.txt`：`Result: Succeeded`、`EXITCODE=0`（2026-07-20 14:06）。
- 產物：`Binaries/Win64/UnrealEditor-SpiritsCalling.dll`（747KB，14:06）。
- harness A 段：5 PASS / 2 WARN（A5 Steam、A6 打包，皆已知待辦）/ 0 FAIL。
