# Spirits Calling — 編譯與遊玩指南

> 2026-07-04 全 C++ 完整可玩版(PC + VR)
> 2026-07-05 更新(S1):四文明差異化召喚 + 附身重攻擊
> 2026-07-05 更新(S2):第二張地圖(Void/Sands)+ 主選單難度/地圖/文明三顆循環鈕
> 2026-07-05 更新(S3/S4/S5):AI 改良(選目標/避障/分離)、Steam 成就骨架、VR 主選單 + 舒適暈影

## 這一版包含什麼

完整遊戲循環,零 Blueprint 接線需求(所有輸入、UI、單位視覺都在 C++ 執行期建立):

- **靈魂視角**:PC 是 RTS 俯視角;VR 是漂浮靈魂視角(HMD 自動偵測、自動切換 Pawn)
- **召喚**:每個文明 3 種原型單位,消耗靈魂資源,Server 驗證
- **四文明差異化(S1 新增)**:東方(高速脆皮)/ 北歐(高血重擊)/ 埃及(便宜壓制)/ 賽博(遠攻高傷),各隊套用自己文明的召喚表與色調;預設單機為東方(玩家)vs 北歐(AI)。文明選單於 S2 加入,目前用預設全域 `GSpiritsCivTeamA/B`
- **附身**:點選(PC)或射線指向+扳機(VR)附身我方單位,第一/三人稱操作攻擊,Q/B 鍵返回靈魂形態;單位死亡自動彈回
- **輕/重雙段攻擊(S1 新增)**:輕擊快、重擊有前搖與高回報(見下方操作表),AI 只用輕擊,重擊是附身玩家的英雄手段
- **戰鬥 AI**:未附身單位自動找最近敵人、追擊、攻擊(不依賴 NavMesh)
- **勝負**:摧毀敵方靈魂聖壇(Soul Shrine)獲勝;單人模式 15 秒後自動出現敵方 AI 兵潮
- **經濟**:每秒 +3 靈魂,擊殺全隊 +25
- **地圖(S2 新增)**:兩張程序化競技場 — Void(夜色黑曜、青光)與 Sands(黃沙日照、金光、更寬更多柱);主選單切換,經 GameState.MapIndex 複寫,全機一致
- **多人**:主選單 Host LAN / Join IP(UE 監聽伺服器);難度/地圖/文明於 Host 或新開局套用;Nakama 後端腳手架見 `Backend/Nakama/README.md`
- **HUD**:PC Canvas HUD(資源/召喚選單/血條/勝負畫面);VR 有頭顯內文字 HUD;所有單位有世界空間血條

## 編譯步驟

1. 需求:UE 5.8、Visual Studio 2022(含 C++ 遊戲開發工作負載)
2. 右鍵 `Spirits_Calling.uproject` → **Generate Visual Studio project files**
3. 開啟 `Spirits_Calling.sln` → 組態選 **Development Editor | Win64** → 建置
4. 開啟 uproject 進入編輯器;地圖已預設為 `Maps/DemoMap`
5. 直接 PIE(Play In Editor)即可玩;Shipping package 請使用版本化入口：`pwsh -File Scripts/build_shipping.ps1`。它固定 UE 5.8、project code build、Shipping、IoStore、DemoMap 與 `Builds/Windows/`；`-DryRun` 可只檢查參數與 toolchain，不會執行 build/cook。

> 若引擎版本差異導致 `XRBase` 模組找不到:確認 OpenXR 插件已啟用(本專案已啟用);
> `MotionControllerComponent.h` 與 `IXRTrackingSystem.h` 分屬 XRBase / HeadMountedDisplay 模組,兩者都已列在 Build.cs。

## PC 版操作

| 狀態 | 按鍵 | 功能 |
|---|---|---|
| 靈魂(RTS) | WASD / 方向鍵 | 平移鏡頭 |
| | Q / E | 旋轉 |
| | 滾輪 | 縮放 |
| | 1 / 2 / 3 | 選擇召喚單位 |
| | 右鍵 | 在游標處召喚 |
| | 左鍵 | 附身我方單位 |
| | M | 主選單(單機/開房/加入/離開) |
| 附身中 | WASD + 滑鼠 | 移動 / 視角 |
| | 左鍵 | 輕攻擊 |
| | 右鍵 | 重攻擊(前搖 0.4s、傷害 ×2.2、擊退 ×2、命中大 hit stop;蓄力時移動變慢、可被打斷) |
| | Space | 跳躍 |
| | Q | 返回靈魂形態 |

## VR 版操作(Quest / Index / WMR,經 OpenXR)

啟動時偵測到 HMD 即自動切換 VR Pawn(SteamVR / Quest Link 需先啟動)。

| 狀態 | 輸入 | 功能 |
|---|---|---|
| 靈魂(漂浮) | 左搖桿 | 水平移動(相對頭部朝向) |
| | 右搖桿 ↑↓ | 上升 / 下降 |
| | 右搖桿 ←→ | 45° 快速轉向 |
| | 右扳機 | 射線指向我方單位 → 附身 |
| | A | 在指向地面處召喚 |
| | X | 切換召喚單位類型 |
| | 左手 Y(Index 左 B) | 開/關 VR 主選單(S5;開啟時右扳機=射線點選,再按一次關閉) |
| 附身中 | 左搖桿 | 移動 |
| | 右搖桿 ←→ | 45° 快速轉向 |
| | 右扳機 | 輕攻擊 |
| | 左扳機 | 重攻擊 |
| | A / B | 跳躍 / 返回靈魂形態 |

## 多人對戰(區網)

1. 主機:M → **Host LAN Game**
2. 客機:M → IP 欄輸入主機 IP → **Join IP**(防火牆需放行 UDP 7777)
3. 先進的玩家是藍隊、後進是紅隊;各自摧毀對方聖壇獲勝
4. 命令列替代:主機 `SpiritsCalling.exe DemoMap?listen`,客機 `SpiritsCalling.exe 192.168.x.x`

## VR (Quest 原生 Android) 打包備註

- Config 已含 Meta Quest 設定(`bPackageForMetaQuest=True`)
- 需 Android SDK/NDK 環境;首次建議先用 PC VR(Quest Link)驗證玩法

## 已知限制(下一版方向)

- 單位是幾何體佔位模型(附身視角、隊伍顏色、血條齊全);可換成 XRMannequins 骨架網格 + 動畫
- 攻擊特效為除錯線條(Shipping 組態不顯示),需換 Niagara
- VR 主選單(S5 已加):世界空間面板 + 右手射線點選,重用 PC 版選單(難度/地圖/文明/Host/Quit);左手 Y 開關。上機時若射線點不到按鈕,調 `VRMenu` 元件的碰撞或 `WidgetInteraction` 的 TraceChannel。Join-by-IP 在 VR 需鍵盤,建議用 PC 主機開房。移動時有舒適暈影(隨速度收攏)。Nakama 配對需裝 nakama-unreal 插件
- AI(S3 已改良):加權選目標(補刀低血、無敵人時推進拆聖壇)+ 繞柱避障 + 同隊分離力,仍不依賴 NavMesh;超大障礙地形若要更精準可再加 NavMeshBoundsVolume 改用 MoveToActor
