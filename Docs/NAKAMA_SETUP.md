# Nakama 伺服器設置指南

本專案使用 [Heroic Labs Nakama](https://heroiclabs.com/nakama) 作為多人連線、社交與後端服務的解決方案。

## 1. 環境需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (Windows/Mac) 或 Docker Engine (Linux)
- Docker Compose

## 2. 啟動伺服器

我們使用 Docker Compose 來快速部署 Nakama 與 PostgreSQL 資料庫。

1. 開啟終端機 (Terminal/PowerShell)。
2. 進入 `Backend/Nakama` 目錄：
   ```bash
   cd Backend/Nakama
   ```
3. 啟動服務：
   ```bash
   docker-compose up -d
   ```

## 3. 驗證安裝

啟動後，您可以透過瀏覽器訪問 Nakama Console (管理後台)：

- **URL**: `http://localhost:7351`
- **預設帳號**: `admin`
- **預設密碼**: `password`

如果能成功登入，代表伺服器已正常運作。

## 4. Unreal Engine 整合

要在 Spirits Calling 中使用 Nakama，我們需要安裝 Nakama Unreal SDK。

### 安裝步驟

1. 下載 [Nakama Unreal SDK](https://github.com/heroiclabs/nakama-unreal)。
2. 將 SDK 解壓縮至專案的 `Plugins` 資料夾中 (如果沒有請自行建立)。
3. 在 Unreal Editor 中啟用 Plugin。
4. 在 `Build.cs` 中加入模組依賴：
   ```csharp
   PublicDependencyModuleNames.AddRange(new string[] { "Nakama" });
   ```

### 連線設定 (C++ 範例)

```cpp
#include "NakamaClient.h"

// 建立 Client
auto Client = Nakama::createNakamaClient(
    Nakama::ClientParameters({
        "defaultkey",   // Server Key (預設為 defaultkey)
        "127.0.0.1",    // Host
        7350,           // Port
        false           // SSL (本地開發設為 false)
    })
);

// 使用 Device ID 登入
string deviceId = "my-device-id";
auto successCallback = [](Nakama::NSessionPtr session) {
    UE_LOG(LogTemp, Log, TEXT("Login successful! Session token: %s"), *FString(session->getAuthToken().c_str()));
};

auto errorCallback = [](const Nakama::NError& error) {
    UE_LOG(LogTemp, Error, TEXT("Login failed: %s"), *FString(error.message.c_str()));
};

Client->authenticateDevice(deviceId, "", true, {}, successCallback, errorCallback);
```

## 5. 常用功能對應

| 遊戲功能 | Nakama 功能模組 | 說明 |
| :--- | :--- | :--- |
| 帳號登入 | Authentication | 支援 Device ID, Email, Steam, Facebook 等 |
| 隊伍/大廳 | Groups / Matchmaker | 建立隊伍或自動配對 |
| 即時對戰 | Realtime Multiplayer | 狀態同步、RPC 呼叫 |
| 排行榜 | Leaderboards | 賽季排名、積分榜 |
| 玩家資料 | Storage Engine | 儲存玩家設定、背包資料 |
| 聊天 | Chat | 全頻、隊伍、私訊 |

## 6. 伺服器端邏輯 (Server-Authoritative)

若需撰寫伺服器端邏輯 (如驗證作弊、複雜配對規則)，請參考 `Backend/Nakama/data` 目錄 (對應 Docker 的 `/nakama/data`)。
您可以放入 `.lua` 腳本或編譯好的 Go plugin 來擴充功能。

---
更多詳細資訊請參考 [Nakama 官方文件](https://heroiclabs.com/docs/)。
