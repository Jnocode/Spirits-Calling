# Spirits Calling — v0.9 → v1.0 實作計畫

> 建立日期:2026-07-05
> 目標:把「可玩原型」推到「可上架(Early Access)」門檻
> 範圍:五條線 — 內容量 / 戰鬥深度 / 上架系統 / VR 收尾 / 生成式美術
> 原則:先出計畫再動手。本文件每一項都對到實際檔案與函式,C++ 為主、盡量不需開編輯器接線。

---

## 0. 現況基準(以實際原始碼為準)

已具備、可直接擴充的支點:

- `SpiritsTypes.h` — `FMinionArchetype`(DisplayName/HP/攻擊/範圍/間隔/移速/花費/Tint/MeshScale)、`GSpiritsDifficulty` 全域難度、`SpiritsTeams` 隊色。**四文明差異化可直接掛在這裡。**
- `ASpiritsGameMode` — `TArray<FMinionArchetype> SummonOptions`(目前 3 種原型)、AI 波次、經濟、聖壇生成、`SpawnUnitForPlayer/Team`。**文明配表與第二地圖切換的入口。**
- `AArenaBuilder` — 程序化建場,目前用 `static constexpr FloorHalfX/Y` 固定尺寸,含 `BuildGeometry / BuildLighting / UpdateMood`。**第二地圖參數化的入口(把 constexpr 改成 style 驅動的成員)。**
- `AUnitBase` — `TryAttack / PerformAttack_Server`(已含 hit stop、擊退、玩家附身 ×1.35),`Multicast_AttackFX / DamageFX`。**重攻擊直接在此加第二條攻擊路徑。**
- `AUnitAIController` — `AcquireTarget`(最近敵人)+ `Tick`(直線追擊)。**AI 改良就地擴充。**
- `ASpiritVRPawn` — VR 靈魂視角、射線附身、召喚;**目前無 VR 主選單。**
- `ASpiritsPlayerState` — `Souls`、`TeamId`;可加成就用統計欄位。
- `ASpiritsPlayerController` — 附身/召喚/選單 RPC、`SelectedArchetype`、`CycleSelectedArchetype`。

已知缺口(來自 BUILD_AND_PLAY「已知限制」與 SHIP_CHECKLIST):單位是幾何佔位、攻擊特效是除錯線、VR 無主選單、AI 直線追擊、只有一張地圖、四文明未差異化、無成就。

---

## 線 1:內容量 — 第二張地圖 + 四文明差異化

### 1A. 第二張地圖(ArenaBuilder 參數化)

**目標**:不新增系統,靠參數產出風格迥異的第二張競技場(尺寸 / 柱陣 / 色調 / 天空)。

**改動**:
1. `SpiritsTypes.h` 新增 `USTRUCT FArenaStyle`:`FloorHalfX/Y/TopZ`、`PillarCountPerSide`、`PillarSpacing`、`FloorTint`、`WallTint`、`GlowColor`、`SkyTint`、`FogColor`、`bRingsSpin`。
2. `ArenaBuilder.h` — 把三個 `static constexpr` 尺寸改為讀自 `FArenaStyle Style` 成員(保留同名 `inline` 取值器讓 GameMode 的 `FallbackBaseDistance` 對齊仍成立);新增 `void ApplyStyle(const FArenaStyle&)`。
3. `ArenaBuilder.cpp` — `BuildGeometry / BuildLighting / UpdateMood` 內所有寫死的顏色/座標/數量改讀 `Style`。
4. `SpiritsGameMode` 生成 ArenaBuilder 時,依 `GSpiritsMapIndex`(新增全域,類比 `GSpiritsDifficulty`)選 `FArenaStyle`。內建 2 組:`Arena_Void`(現況夜色)、`Arena_Sands`(埃及/黃沙、寬場、密柱)。
5. 主選單加「地圖」循環鈕(見線 3 版本收尾一併做 UI)。

**產出**:2 張可玩地圖,零新美術(靠色調+幾何差異)。之後每加一組 `FArenaStyle` = 一張新圖。
**風險**:`FallbackBaseDistance=3400` 與 `FloorHalfX=4500` 有隱含耦合(聖壇要落在地板內)。ApplyStyle 後需夾住基地距離 ≤ FloorHalf* 的 0.85。
**估時**:0.5–1 天。

### 1B. 四文明差異化

**目標**:東方仙俠 / 北歐戰士 / 埃及神祕 / 賽博科技,各有召喚組合、數值、色調 — 零新系統(換 `SummonOptions` + `Tint`)。

**改動**:
1. `SpiritsTypes.h` 新增 `UENUM ECivilization { East, Norse, Egypt, Cyber }` 與全域 `extern int32 GSpiritsCivTeamA/TeamB`。
2. `SpiritsGameMode` 把單一 `SummonOptions` 改為「每文明一組 3 原型」的表:`TMap<ECivilization, FCivilizationLoadout>`,`FCivilizationLoadout` 含 3× `FMinionArchetype` + 文明主色 + 名稱。在 C++ 建構式填預設值(維持免資產可玩)。
   - 東方:低 HP 高速高頻(靈巧);北歐:高 HP 近戰重擊;埃及:均衡+召喚較便宜;賽博:遠攻/高攻低 HP。差異全用既有欄位表達。
3. `SpawnUnitForPlayer` 依該玩家隊伍的文明取對應 loadout。
4. `PDA_MinionData` 已支援覆寫,保留給日後編輯器擴充文明外觀。
5. 主選單加「文明」選擇(Host 設 TeamA、單機時 AI = 另一文明)。

**產出**:4 文明 × 3 單位 = 12 種可召喚,配色與手感各異。
**風險**:平衡。先給合理起手值,靠線 3 的冒煙測試矩陣調。
**估時**:1–1.5 天。

---

## 線 2:戰鬥深度 — 重攻擊 + AI 改良

### 2A. 重攻擊(第二輸入)

**目標(櫻井配方)**:前搖 0.4s / hit stop 0.12s / 擊退 ×2 / 傷害 ×2.2 / 較長冷卻。給附身玩家一個「賭前搖換高回報」的決策。

**改動**(全在 `UnitBase`):
1. `UnitBase.h` 加狀態:`float HeavyWindupEndTime`、`bool bHeavyPending`、`float LastHeavyTime`;新增 `TryHeavyAttack()` / `Server_TryHeavyAttack()`(Server, Reliable)/ `PerformHeavy_Server()` / `Multicast_HeavyFX()`。
2. `UnitBase.cpp` — `PerformHeavy_Server`:進入前搖(鎖攻擊、播蓄力音效與微下蹲位移),0.4s 後掃更大球(半徑 90、範圍 ×1.3)、`ApplyDamage ×2.2`、擊退向量 ×2、hit stop 0.12s、受擊者較強閃白。冷卻 `AttackInterval × 2.2`。
3. `SetupPlayerInputComponent` — 新增 `IA_HeavyAttack`(PC:右鍵或 Shift+左鍵;綁定在此就地建 IA,沿用現有 runtime-input 模式)。
4. VR:`SpiritVRPawn` 附身路徑用左扳機/握把觸發重攻擊(附身時輸入轉送到單位)。
5. 音效:`SpiritsAudio` 加 `HeavyWindup` / `HeavyHit`(程序合成,沿用現有空值保護)。

**產出**:輕/重兩段攻擊,手感層次。
**風險**:前搖期間被打斷的規則要定義(建議可被硬直打斷 → 增加博弈)。多人下 hit stop 只做本地表現、傷害由 Server 結算(現有架構已這樣分)。
**估時**:1 天。

### 2B. AI 改良

**目標**:從「直線追最近敵人」升級為「會繞障礙、會選目標、不擠成一團」。

**改動**(全在 `UnitAIController`):
1. **目標選擇加權**:`AcquireTarget` 從「最近」改為評分 = 距離 + 血量(補刀傾向)+ 聖壇加權(接近敵方基地時優先拆聖壇,對應勝利條件)。
2. **避障**:`Tick` 移動前對前方做兩條側向球掃(左右 30°),被擋就轉向空側(轉向式 steering,不需 NavMesh,延續現有「不依賴 NavMesh」設計)。
3. **分離力**:對半徑內同隊單位加反向分離向量,避免疊人;讓兵潮散開推進更好看。
4. **停火帶**:進入 `EffectiveRange × 0.9` 後保持面向並攻擊(現況已有,保留),加入輕微環繞避免正面互頂。
5. 參數集中成 `UnitAIController` 的 `UPROPERTY` 可調(SightRadius/SeparationRadius/權重),方便後續平衡。

**產出**:兵潮推進自然、會拆聖壇、不卡牆。
**風險**:效能(每 unit 每 tick 掃描)。用現有 `GM->GetAllUnits()` + 0.5s 目標刷新節流;分離只掃半徑內、避障每 0.1s 掃一次即可。
**估時**:1–1.5 天。

---

## 線 3:上架系統 — Steam 成就 + 版本收尾

### 3A. Steam 成就骨架

**改動**:
1. `SpiritsCalling.Build.cs` 加 `OnlineSubsystem`、`OnlineSubsystemUtils` 依賴;啟用 `OnlineSubsystemSteam` 插件(`.uproject` + `DefaultEngine.ini` 的 `[OnlineSubsystemSteam]`、SteamDevAppId=480 佔位)。
2. 新增 `USpiritsAchievements`(UGameInstanceSubsystem):封裝 `WriteAchievementProgress(FName Id, float Pct)`,對 Steam 不可用時退化為本地 log(維持免 Steam 可跑)。
3. 統計來源:`ASpiritsPlayerState` 加 `PossessedKills`、`GamesWon`、`DifficultiesBeaten(bitmask)` 等 replicated 欄位;在 `SpiritsGameMode::NotifyUnitDied` / `EndMatch` 記帳並呼叫成就子系統。
4. 首批 8–10 個成就定義(對應 SHIP_CHECKLIST):首勝、三難度各勝、附身擊殺 50、單場召喚 20、拆聖壇不失聖壇、四文明各贏一場、重攻擊擊殺 10、LAN 首勝。做成 `DataTable` 或 C++ 常數表。

**產出**:成就在 Steam 開啟時上報、關閉時安全退化。
**風險**:真正驗證需 Steamworks App 與實機;此線先把「觸發點 + 上報介面」做完,商店側門檻列在 SHIP_CHECKLIST。
**估時**:1–1.5 天(不含 Steamworks 帳號流程)。

### 3B. 版本收尾與選單擴充

**改動**:
1. `MainMenuWidget` 擴充:在既有 Difficulty 循環鈕旁加「地圖」「文明」兩個循環鈕(重用 `MakeButton` + `RefreshXxxLabel` 模式),寫入線 1 的全域變數。
2. 版本號 v0.9.0 → v0.9.5(整合本輪),集中到一個 `SpiritsVersion.h` 常數,HUD/選單/結算共用。
3. `DefaultGame.ini` 專案顯示名、公司名、商店描述句校對(SHIP_CHECKLIST 已列)。
4. 打包組態複驗:Shipping、只烹飪 DemoMap + 第二地圖、IoStore、圖示。

**估時**:0.5 天。

---

## 線 4:VR 收尾 — VR 主選單 + 手感優化

### 4A. VR 世界空間主選單

**目標**:VR 玩家不再只能被動進單機/被開房,能在頭顯前開一個可用射線點選的面板(單機/難度/文明/地圖/Host/離開)。

**改動**:
1. `SpiritVRPawn.h/.cpp` 加 `UWidgetComponent VRMenuComp`(World/Screen space,置於相機前 ~120cm),內容重用 `UMainMenuWidget`(它已是純 C++ 建構,可共用)。
2. 新增 `IA_Menu`(右手 Menu/B 鍵)切換面板顯示;顯示時鎖移動輸入。
3. 射線選取:沿用 `TraceFromRightController` + `AimBeam`,加一個 `UWidgetInteractionComponent` 做 hover/click,扳機 = 點擊。
4. 面板出現時給一次輕觸覺回饋。

**產出**:VR 端獨立可操作的主選單,和 PC 選單同源。
**風險**:`UMainMenuWidget::RebuildWidget` 目前針對螢幕布局,VR 需確認字級/按鈕命中盒夠大;必要時加 `bVRLayout` 分支放大。
**估時**:1–1.5 天。

### 4B. 手感/舒適度優化(VR_Optimization_Guide 對齊)

**改動**:
1. 移動時舒適暈影(vignette):`SpiritVRPawn` 在 `OnMoveInput` 速度>閾值時,透過後處理材質參數收暈影,停下淡出。
2. Snap turn 已有(45°);加可選 comfort 冷卻與轉向瞬黑淡入(減暈)。
3. 附身/受擊/召喚的控制器觸覺(`PlayHapticEffect`)。
4. 90fps 檢查點:確認 ArenaBuilder 動態光/霧在 VR 下的成本;必要時 VR 走精簡 mood。加 `stat fps` 冒煙步驟到 checklist。

**估時**:1 天。

---

## 線 5:美術進化 — ComfyUI 生成式素材

> 說明:此線是資產產線,無法在本機開 UE 編輯器完成匯入,但可先把**工作流、規格與掛點**全部定好,產出即可直接套進現有的 MID(動態材質)管線。

### 5A. 能立即吃到生成素材的掛點(已存在)

- `AUnitBase` 的 `BodyMID` 等動態材質:可把生成的 **emissive/noise/文明紋樣貼圖**餵進去,不改幾何就讓四文明外觀分明(對接線 1B)。
- `AArenaBuilder` 的地板/牆/天空材質:吃生成的 **地面紋理 / 天空球 HDRI 風格圖**(對接線 1A 的兩張地圖)。

### 5B. ComfyUI 工作流(規劃)

1. **文明紋樣貼圖包**(4 套,tileable,512/1024):東方雲雷紋、北歐盧恩、埃及象形、賽博電路。輸出 base color + emissive mask,套到單位 `BodyMID` 與聖壇。
2. **地面/牆面材質**(2 地圖 × 3 貼圖):void 黑曜石、黃沙岩。
3. **天空球**:每張地圖一張 panoramic(equirectangular)當 sky material。
4. **Steam 商店素材**(SHIP_CHECKLIST 明列最值得投資):膠囊主圖概念稿、6–10 張截圖後製底、trailer 分鏡關鍵視覺(hit stop / 聖壇光柱)。
5. 工作流檔(`.json`)+ 提示詞 + 尺寸/命名規範,存到 `RawAssets/AI/`,並寫一份 `Docs/ComfyUI_Asset_Pipeline.md`(生成 → PNG → Content/Textures/<Civ> → 指到 MID 的參數名)。

### 5C. 待你確認的前置

- 你的 ComfyUI 是本機服務嗎?若可用 API(預設 `127.0.0.1:8188`),我可以直接寫**批次生成腳本**(讀提示詞表 → 打 ComfyUI API → 落檔到 `RawAssets/AI/`),你只要在編輯器把 PNG 拖進 Content。
- 是否已有偏好的 checkpoint/風格,或要我先出四文明的提示詞與參考風格板(mood board 描述)。

**估時**:管線與提示詞 0.5 天;實際生成視 ComfyUI 可用性與張數而定。

---

## 建議執行順序(梅爾:先核心後廣度)

| 階段 | 內容 | 為何先做 |
|---|---|---|
| **S1** | 線 1B 四文明配表 + 線 2A 重攻擊 | 純數據/單檔,立刻讓「每局」變豐富,風險最低 |
| **S2** | 線 1A 第二地圖 + 線 3B 選單三鈕(難度/地圖/文明) | 地圖與文明都要靠選單串起來,一起做 |
| **S3** | 線 2B AI 改良 | 有了多文明多單位再調 AI,平衡一次到位 |
| **S4** | 線 3A Steam 成就骨架 | 統計欄位依賴前面玩法定型 |
| **S5** | 線 4 VR 主選單 + 手感 | 選單同源(等 PC 選單三鈕定案) |
| **S6** | 線 5 ComfyUI 產線 | 需你確認 ComfyUI 環境;可與 S1–S5 並行起草 |

粗估純程式線(1–4)約 7–10 個工作日;線 5 視素材量另計。

---

## 我需要你拍板的三件事

1. **要不要照上面的 S1 開始**,還是你想先跳到某一條(例如先做重攻擊手感)?
2. **ComfyUI 環境**:本機 API 可用嗎?要我先寫批次生成腳本 + 四文明提示詞嗎?
3. **平衡取向**:四文明你要「明顯不對稱、各有玩法」還是「輕度差異、好平衡」?(影響 1B 起手值)

> 確認後我就從 S1 開始實際改 `Source/` 的 .cpp/.h。
