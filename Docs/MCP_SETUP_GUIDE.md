# Unreal MCP 設定指南

這份指南將協助您在 Spirits-Calling 專案中設定 `unreal-mcp`，讓 AI 能夠直接控制 Unreal Editor。

## 1. 什麼是 Unreal MCP？

[unreal-mcp](https://github.com/chongdashu/unreal-mcp) 是一個開源工具，透過 MCP (Model Context Protocol) 讓 AI 助手可以：
- 創建與操作 Actor (方塊、燈光、相機等)
- 編輯 Blueprint (添加節點、連接引腳)
- 控制編輯器視角
- 查詢場景中的物件

這解決了 AI 無法直接編輯 `.uasset` (二進位檔案) 的問題。

## 2. 安裝步驟

### 步驟一：準備 Unreal 專案
由於目前 `Spirits-Calling` 資料夾是空的，您需要先建立一個基礎的 C++ 專案。
1. 打開 Unreal Engine 5.5+
2. 建立新專案 (Blank C++ Project)
3. 將專案路徑設為 `d:\Workspace\dev_projects\game\Spirits-Calling`
4. 專案名稱設為 `SpiritsCalling`

### 步驟二：安裝插件 (Plugin)
1. 下載 [unreal-mcp](https://github.com/chongdashu/unreal-mcp) 儲存庫。
2. 將 `MCPGameProject/Plugins/UnrealMCP` 資料夾複製到您的專案中：
   `d:\Workspace\dev_projects\game\Spirits-Calling\Plugins\UnrealMCP`
3. 重新生成 Visual Studio 專案檔 (Right-click .uproject -> Generate Visual Studio project files)。
4. 打開 `.sln` 並編譯專案。
5. 開啟 Unreal Editor，確認插件已啟用 (Edit > Plugins > UnrealMCP)。

### 步驟三：設定 Python MCP Server
1. 確保已安裝 Python 3.12+。
2. 進入 `unreal-mcp/Python` 目錄。
3. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```
4. 啟動伺服器 (測試用)：
   ```bash
   python unreal_mcp_server.py
   ```

### 步驟四：設定 VS Code / Copilot
在您的 MCP 設定檔 (通常位於 `%USERPROFILE%\.config\claude-desktop\mcp.json` 或 VS Code 擴充設定) 中加入：

```json
{
  "mcpServers": {
    "unrealMCP": {
      "command": "python",
      "args": [
        "D:/path/to/unreal-mcp/Python/unreal_mcp_server.py"
      ]
    }
  }
}
```

## 3. 如何使用？

完成設定後，當您在 VS Code 中與 Copilot 對話時，我將能夠使用如 `create_actor`, `compile_blueprint` 等新工具。

例如，您可以對我說：
> "在場景中建立一個 10x10 的方塊陣列"
> "幫我建立一個新的 Character Blueprint，並加入 Nakama 連線功能"

## 4. 注意事項
- 這是實驗性專案，請務必備份您的專案。
- 必須保持 Unreal Editor 開啟，MCP Server 才能與其溝通。
