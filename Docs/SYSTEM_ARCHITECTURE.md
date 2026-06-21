# 亡者呼喚 Spirits Calling — 系統架構設計與類圖

## 1. 技術棧
- Unreal Engine 5
- C++/Blueprints
- Backend: Nakama (Docker/Go/Lua)
- Database: PostgreSQL

## 2. 架構圖
- 客戶端（PC/VR）→ Nakama Server (Game Backend) → PostgreSQL
- 健康 APP 整合（API）

## 3. 主要模組類圖
- 玩家管理、召喚體系、文明模組
- VR 互動模組、健康數據模組
- 多人連線與社群模組

## 4. 系統流程
- 用戶登入 → 選擇文明 → 召喚/附身/戰鬥 → 雲端同步

> 詳細 UML 請參考附件類圖與設計文檔