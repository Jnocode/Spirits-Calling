# Spirits Calling (亡者呼喚)

> 呼喚先祖智慧，征戰文明戰場  
> Call Upon Ancient Wisdom, Command Civilizations

## 專案簡介
「亡者呼喚 Spirits Calling」是一款以 UE5 製作、結合靈魂附身機制與四大文明召喚玩法的跨平台策略遊戲，支援 PC 與 VR 沉浸式體驗。

## 專案資訊
- **專案名稱**：Spirits Calling（亡者呼喚）
- **遊戲引擎**：Unreal Engine 5
- **平台**：PC (Windows/Mac)、VR（Oculus/Steam VR/PICO）
- **開發語言**：C++、藍圖（Blueprints）
- **開發狀態**：概念設計完成，進入原型開發
- **專案負責人**：[@xiujiang1987](https://github.com/xiujiang1987)
- **啟動日期**：2025-06-16

## 🚀 快速開始(完整可玩版)

目前版本為**全 C++ 完整可玩**:PC(RTS 俯視 + 附身第三人稱)與 VR(OpenXR,自動偵測 HMD)共用同一套遊戲循環——召喚、附身、戰鬥 AI、摧毀敵方聖壇獲勝、單人 AI 兵潮、LAN 多人對戰。

編譯與操作說明:[`Spirits_Calling/Docs/BUILD_AND_PLAY.md`](Spirits_Calling/Docs/BUILD_AND_PLAY.md)
Nakama 後端:[`Backend/Nakama/README.md`](Backend/Nakama/README.md)

> **引擎版本**：本專案已對齊 **Unreal Engine 5.8**（`.uproject` `EngineAssociation=5.8`）。以其他版本開啟需自行 retarget。

### Note on VR / Third-Party Assets

To keep the repository lightweight and focused on the custom IP code, standard UE VR
template content (`VRTemplate`, `XRMannequins`, `XRFramework`, `VRSpectator`,
`LevelPrototyping`, `Weapons`) and large Fab marketplace packs (Big Niagara Bundle,
Basic Pickups VFX) are excluded via `.gitignore`.

When opening in Unreal Editor, please ensure your UE 5 project is created with or
references the standard **Unreal Engine 5 VR Template**. Fab packs can be re-added from
your Epic account — see [`Spirits_Calling/Docs/FAB_ASSETS.md`](Spirits_Calling/Docs/FAB_ASSETS.md).
Missing-asset warnings on a fresh clone are expected for these excluded, non-IP assets.

## 核心特色
- **創新靈魂附身RTS機制**：玩家可附身至召喚物，實現第一人稱戰術博弈
- **四大文明召喚體系**：東方仙俠、北歐戰士、埃及神祕、賽博科技
- **VR原生體驗**：支援空間動作、冥想與文化互動
- **健康整合**：可與 Apple Health/Google Fit 整合遊戲獎勵

## 技術棧
- **引擎**：Unreal Engine 5.8
- **語言**：C++ / Blueprints
- **VR支援**：OpenXR、SteamVR、Oculus SDK
- **網路/多人**：Nakama (開源遊戲後端) / Unreal Multiplayer Framework
- **資料庫/雲端**：PostgreSQL (via Nakama) / AWS / Azure

## 建議資料夾結構
```
/Config
/Content
  /Blueprints
  /Characters
  /UI
  /Audio
  /VR
  /Levels
/Docs
  README.md
  DESIGN.md
  ROADMAP.md
/Plugins
/Scripts
```

## 開發規範
- 使用 Git 進行版本管理，建議主分支保留穩定版本，開新功能請開 feature branch
- 原型階段以 C++ 為主，快速開發可用 Blueprints
- 美術、音效資源統一放於 Content 目錄下並明確分類

## 參考資源
- [Unreal Engine 官方文件](https://docs.unrealengine.com/5.0/zh-TW/)
- [Unreal Multiplayer 網路教學](https://docs.unrealengine.com/5.0/zh-TW/InteractiveExperiences/Networking/index.html)
- [OpenXR VR 開發指南](https://docs.unrealengine.com/5.0/zh-TW/SharingAndReleasing/XRDevelopment/index.html)

---

*歡迎貢獻者、合作夥伴與投資人一同參與 Spirits Calling 的開發旅程！*
