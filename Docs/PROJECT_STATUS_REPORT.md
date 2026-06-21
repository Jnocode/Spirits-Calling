# Spirits Calling（亡者呼喚）— 專案現況勘查報告

> 📅 報告日期：2026-03-04
> 📝 用途：接手開發前的全面現況盤點，供後續追蹤進度使用

## 📋 專案概覽

| 項目 | 內容 |
|------|------|
| **引擎** | Unreal Engine 5.7 |
| **語言** | C++ + Blueprints |
| **平台** | Windows/Mac/Linux/Android/iOS/PS4/PS5/Xbox/Switch/VisionOS |
| **VR** | OpenXR + EyeTracker + HandTracking |
| **後端** | Nakama (Go/Lua) + PostgreSQL |
| **開發狀態** | 概念設計完成，原型開發初期 |
| **Git** | 僅 3 次提交 (Initial → README → Upload) |

## 🏗 專案結構

```
Spirits-Calling/
├── Backend/Nakama/             # Nakama 後端（尚空）
├── Docs/                       # 高階設計文件 (PRD, Architecture, Design)
├── Spirits_Calling/            # UE5 專案根目錄
│   ├── Source/SpiritsCalling/  # C++ 模組
│   │   ├── SpiritsPlayerController.h/.cpp  ← Server RPC Possession
│   │   ├── PDA_MinionData.h/.cpp           ← Minion 數據資產
│   │   └── SpiritsCalling.Build.cs
│   ├── Content/
│   │   ├── Core/               # 核心遊戲資產
│   │   │   ├── Characters/     # BP_SpiritPawn, BP_UnitBase
│   │   │   ├── Controllers/    # BP_SpiritController
│   │   │   ├── Components/     # BPC_VRMovement
│   │   │   ├── Framework/      # GameMode 等
│   │   │   └── Input/          # IMC_Spirit, IMC_Possessed + 5 Input Actions
│   │   ├── Maps/DemoMap.umap   # 唯一地圖
│   │   ├── Weapons/            # 武器資產 (27 項)
│   │   ├── XRFramework/        # VR 框架模板 (65 項)
│   │   ├── VRTemplate/         # VR 模板
│   │   └── ...
│   ├── Scripts/                # 54 個 Python 輔助腳本
│   ├── Docs/                   # 實作指南文件
│   └── Config/                 # 引擎設定
└── .github/                    # GitHub 設定
```

## 🔧 已完成的工作

### C++ 層

- **`ASpiritsPlayerController`**: 繼承 `APlayerController`，實作了 Server RPC (`Server_PossessMinion`) 用於多人遊戲中的附身驗證和執行
- **`UPDA_MinionData`**: `UPrimaryDataAsset` 子類，定義 Minion 基本屬性（MaxHP=100, BaseAttack=10, CivilizationName）

### Blueprint 層

- **`BP_SpiritPawn`**: 玩家的 RTS 視角 Pawn
- **`BP_UnitBase`**: 可被附身的單位基類
- **Input Mapping Contexts**: `IMC_Spirit`（RTS 模式）、`IMC_Possessed`（附身模式）
- **Input Actions**: `IA_RTS_Move`、`IA_Select`、`IA_Possess`、`IA_VR_Move`、`IA_VR_Turn`

### 啟用的插件

- OpenXR、OpenXREyeTracker、OpenXRHandTracking
- RemoteControl、RemoteControlWebInterface（用於 Python 腳本遠端操控）

## ⚠️ 當前痛點診斷

### 🏛 架構 (Architecture)

- **SRP 違反風險**：`BP_XRPawn` 可能仍承擔過多職責（已有重構計畫但尚未完成）
- **MVC 未落實**：Blueprint 常混合 data/logic/UI
- **Nakama 後端為空**：Backend/Nakama 目錄僅有空結構

### 🔨 實作 (Implementation)

- **Blueprint 連線未完成**：RTS Camera 移動和點擊附身的 Blueprint 邏輯尚需手動連線
- **VR 模板資產大量引入**：XRFramework (65 項) + VRTemplate 直接從模板匯入，未經整理
- **Python 腳本爆量**：54 個腳本散落，功能重疊且缺乏統一入口

### 📦 流程 (Process)

- **Git 歷史極少**：僅 3 次 commit，無分支策略
- **無測試覆蓋**：未發現任何自動化測試
- **文件未同步**：部分文件內容為簡易大綱級別

## 🎯 MVP 待完成項目

- [ ] **RTS Camera 移動** — `BP_SpiritPawn` EventGraph 連線（WASD 移動）
- [ ] **點擊附身** — `BP_SpiritController` EventGraph 連線（滑鼠點擊 → Cast → Possess）
- [ ] **重構 BP_XRPawn** → `BP_SpiritController` + `BP_UnitBase` + `BPC_VRMovement`
- [ ] **VR 移動組件** — `BPC_VRMovement` 實作（Snap Turn / Teleport / Smooth Locomotion）
- [ ] **DemoMap 整合測試** — 在 DemoMap 中驗證完整遊戲流程

## 📁 關鍵檔案索引

| 檔案 | 說明 |
|------|------|
| `Source/SpiritsCalling/SpiritsPlayerController.cpp` | C++ Possession RPC 邏輯 |
| `Source/SpiritsCalling/PDA_MinionData.h` | Minion 數據資產定義 |
| `Spirits_Calling/Docs/MVP_Logic_Guide.md` | MVP 實作步驟 |
| `Spirits_Calling/Docs/Refactoring_Plan.md` | 架構重構計畫 |
| `Spirits_Calling/Docs/Wiring_Tutorial.md` | Blueprint 連線教學（中文版） |
| `Spirits_Calling/Docs/VR_Optimization_Guide.md` | VR 效能優化指南 |
| `Docs/PROJECT_PRD.md` | 專案需求規格書 |
| `Docs/SYSTEM_ARCHITECTURE.md` | 系統架構設計 |
| `Docs/DESIGN_SUMMARY.md` | 遊戲設計總結 |
