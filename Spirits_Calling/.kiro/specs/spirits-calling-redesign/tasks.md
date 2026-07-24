# Implementation Plan: Spirits Calling Redesign (v2)

## Overview

本計畫把 `requirements.md` 的 Requirement 1–8 與 `design.md` 的五根設計柱轉成增量、可驗證的實作任務。順序鐵律：**核心循環先好玩 → 社交/內容/美術才有價值**。每過一 phase 送審計團（Feynman/Karpathy/Musk）維持方向不歪。

> **給 Kiro / 實作者**：這是 game-design pivot。P0（設計鎖定）**必須先完成**——它把 `requirements.md` 的 8 個 [TBD] / Open Design Decisions 補成可測數值，之後 P1+ 才動工。P0 未完成前不得大規模寫玩法程式碼。既有基礎設施（魂體 pawn、義體戰鬥、Match FSM、AArenaBuilder、Nakama scaffold、打包鏈）重用不重寫。

## Tasks

- [ ] 0. **設計鎖定（P0，Jun 拍板）** — 把 Open Design Decisions 補成可測準則
  - **目標：** 由專案負責人拍板 `requirements.md` §Open Design Decisions 的 8 項，將 Req 1.5/2.5/3.5/5.5 的 [TBD] 補成具體、可測的數值與機制。
  - **涉及：** `requirements.md`（補 [TBD]→[DECIDED]）、`design.md` §7。
  - **完成條件：** 8 項全部有明確決定；心靈門檻/階級數、義體耗損、run 時序、技能數、天賦形式、RTS 程度、終局護欄、四文明靈視內容皆可寫成驗收準則。
  - **不動工鐵律：** 本 phase 是純設計決策，不寫玩法程式碼。
  - _Requirements: 1.5, 2.5, 3.5, 5.5; Open Design Decisions 1–8_

- [ ] 1. **重用審計 + 魂體探索原型（P1）** — 先證明「弱靈魂探索」不無聊
  - [ ] 1.1 重用審計：盤點既有 `ASpiritPawn/ASpiritVRPawn`、`AUnitBase`、Match FSM、`AArenaBuilder`、四文明系統、Nakama scaffold 的可重用面與需改造面，產出 reuse map。
  - [ ] 1.2 魂體探索移動：以 `ASpiritPawn` 為基底做「無形穿越 + 靈界視覺」的魂體探索狀態。
  - [ ] 1.3 靈界迷霧 + 視野：Spirit_Fog 遮蔽 + 附身取得視野的資訊機制骨架。
  - [ ] 1.4 心靈吸收：探索行為（靈脈/秘密/淨化/擊散）累積 Psyche 的資源系統。
  - [ ] 1.5 安全地帶悠閒探索原型：無威脅、可自由摸索學操作（環境式教學）。
  - **審計 gate：** 這個「弱靈魂探索」逐秒好玩嗎？（潛行+發現的張力）不好玩就先修 P1，別往下。
  - _Requirements: 1.2, 2.3, 5.1, 5.3, 8.1_

- [ ] 2. **附身門檻 + 義體階級（P2）** — 附身即變身、掙來的力量
  - [ ] 2.1 Possession_Threshold：Psyche gate 附身；未達門檻拒絕並指示原因。
  - [ ] 2.2 義體階級：至少兩階（低階脆弱→高階英雄），高階戰鬥力明顯更強。
  - [ ] 2.3 附身即變身：以 `AUnitBase` 為基底，附身後實體化為對應階級義體（含輕/重擊既有基底）。
  - [ ] 2.4 附身萬物骨架：一般義體 + 至少一種特殊附身目標（中立守衛/地形物件）。
  - _Requirements: 1.1, 1.3, 1.4, 5.1, 5.2, 8.1_

- [ ] 3. **危險地帶擴張（P3）** — 反向縮圈節奏脊椎
  - [ ] 3.1 Danger_Zone 系統：以 `AArenaBuilder` 為承載面，做「無→出現→擴張→吞全圖」四階段。
  - [ ] 3.2 魂體消滅機制：Soul_Form 在 Danger_Zone 內被威脅（損 Psyche / 結束 Run）。
  - [ ] 3.3 終局窒息：全圖 Danger_Zone 下裸奔魂體無法久存，附身成剛需。
  - [ ] 3.4 反挫折護欄：消滅前明確警訊 + 逃生窗口 + 心靈淨化小塊危險區（死亡=玩家賭輸，非地圖宣判）。
  - **審計 gate：** 終局是「緊張」還是「焦慮」？玩家能不能說「是我剛太貪」而非「遊戲亂弄死我」。
  - _Requirements: 2.1, 2.2, 2.4, Open Design Decision 7_

- [ ] 4. **魂體 ⇄ 義體 推幣循環（P4）** — 核心動詞閉環
  - [ ] 4.1 義體庫存：召喚重定義為準備 Vessel_Inventory（待命義體），Psyche 解鎖、非開場即用。
  - [ ] 4.2 保命/成長互斥：Vessel 中不長 Psyche，逼出「出魂 vs 苟命」抉擇。
  - [ ] 4.3 義體耗損 + 死亡轉場：Vessel 消耗性；被摧毀→回 Soul_Form 續 Run，直到魂體亦滅才結束。
  - **審計 gate：** 「還敢不敢再出去撈一波」這個賭命抉擇，逐秒成立嗎？
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3_

- [ ] 5. **roguelite 天賦層（P5）** — 探索者/成就者延壽
  - [ ] 5.1 天賦系統：依 P0 決定的形式（附身三選一/場中升級/開局配裝）做 build 選擇。
  - [ ] 5.2 難度階：一場學到的帶進下一場，危險更快/更兇。
  - _Requirements: 6.2, 6.3, Open Design Decisions 4, 5_

- [ ] 6. **四文明靈視（P6）** — replay ×4
  - [ ] 6.1 四種 Spirit_Vision：同圖四層隱藏內容覆蓋層（東方靈脈/北歐盧恩/埃及墓室/賽博快取）。
  - [ ] 6.2 四義體風格：四文明各自的義體手感/技能差異（重用既有四文明系統）。
  - [ ] 6.3 心靈越高靈視越深：探索深度隨 Psyche 成長揭開。
  - _Requirements: 5.4, 5.5, 6.3, 8.1_

- [ ] 7. **Nakama 社交地基（P7）** — 基礎要有，day-1 骨架先行
  - [ ] 7.1 nakama-unreal 接線：帳號（Device/social 認證）+ 既有 `Backend/Nakama` scaffold 啟用。
  - [ ] 7.2 排行榜 + build 分享碼：day-1 骨架（成就者 + 探索者/社交者傳播）。
  - [ ] 7.3 每局可炫耀內容：結算戰報圖 / build 碼 / 破紀錄 run（餵內容裂變機器）。
  - [ ] 7.4 EA 逐步長：好友/群組/聊天/錦標賽/線上 PvP（Nakama 現成，接 UI 即可）。
  - **誠實 gate：** scope 文字不得把未完成的線上 PvP/public matchmaking 呈現為已出貨。
  - _Requirements: 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 8.1_

- [ ] 8. **內容 / 美術 / 打磨 / 上架（P8）** — 循環爽了才值得做
  - [ ] 8.1 美術升級：單位/義體換骨架網格+動畫、Niagara 特效接上身（Big Niagara/Basic Pickups 已在 Content）。
  - [ ] 8.2 內容量：足夠天賦/義體階級/四英雄差異，防「三局玩膩」（roguelite 最大死法）。
  - [ ] 8.3 上架硬門檻：Steamworks App ID、膠囊圖/截圖/trailer、內容分級（沿用既有 SHIP_CHECKLIST / release gate）。
  - [ ] 8.4 沿用打包/驗證鏈：`build_shipping.ps1` + closure/audio/version validators（前一輪已全綠，直接重用）。
  - _Requirements: 6.5, 7.4, 8.2_

## Notes

- **重用不重寫**：`design.md` §5 的既有資產全部重用；pivot 的是玩法層，不是引擎/打包/後端。
- **審計 gate**：P1/P3/P4 的「好不好玩」審計是硬 gate——不好玩就地修，別往下堆功能。這正是本次 pivot 的教訓（前一輪把工程做到全綠卻從沒驗證好不好玩）。
- **舊 spec 保留**：`spirits-calling-requirements` 是基礎設施歷史紀錄，不刪不覆寫。
- **P0 先行**：8 個 Open Design Decisions 未鎖定前，P1+ 不動工。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["0"] },
    { "id": 1, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["3.1", "3.2", "3.3", "3.4"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 5, "tasks": ["5.1", "5.2", "6.1", "6.2", "6.3"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3"] },
    { "id": 7, "tasks": ["7.4", "8.1", "8.2", "8.3", "8.4"] }
  ]
}
```
