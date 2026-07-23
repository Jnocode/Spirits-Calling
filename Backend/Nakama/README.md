# Spirits Calling — Nakama 後端

## 現況

第一版多人對戰使用 **UE 內建 Replication(監聽伺服器)**,已完整可玩:

- 主選單 → `Host LAN Game` 開房(listen server)
- 另一台機器 → `Join IP` 輸入主機 IP 即可加入,自動分到另一隊

Nakama 在此階段作為**配對/帳號/資料腳手架**,已備妥:

- `docker-compose.yml` — Nakama 3.x + PostgreSQL 15
- `modules/spirits_match.lua` — 1v1 配對 RPC(`spirits_find_match`)+ 權威 match handler 骨架(隊伍分配、訊息轉發)

## 啟動後端

```bash
cd Backend/Nakama
docker compose up -d
```

- 遊戲 API:`localhost:7350`(預設 server key:`defaultkey`)
- 管理後台:`http://localhost:7351`(帳密 `admin` / `password`)
- Lua 模組會自動從 `modules/` 載入,啟動 log 應出現 `spirits_find_match` 註冊成功

## UE 整合(下一步)

1. 下載 [nakama-unreal](https://github.com/heroiclabs/nakama-unreal/releases) 插件,解壓到 `Spirits_Calling/Plugins/Nakama/`
2. `.uproject` 的 Plugins 加入 `{ "Name": "Nakama", "Enabled": true }`
3. `SpiritsCalling.Build.cs` 加入 `"NakamaUnreal"`、`"NakamaCore"`
4. 流程:Device 認證 → RPC `spirits_find_match` 取得 match_id → 加入 match → 以 match 資料交換主機 IP,再走現有 `ClientTravel` 加入 UE 對戰

詳見 `Docs/NAKAMA_SETUP.md`。
