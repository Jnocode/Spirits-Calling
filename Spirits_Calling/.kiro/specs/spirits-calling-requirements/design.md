# Spirits Calling 技術設計文件

## 1. 文件目的與設計基線

本文件將 `spirits-calling-requirements/requirements.md` 的 Requirement 1–6 與 P1–P9 轉換為可實作、可驗證、可打包的 Unreal Engine 技術設計。設計只描述 runtime、Editor/asset pipeline、packaging、release validation 與測試 seam；本階段不修改產品程式碼，也不建立 `tasks.md`。

現況基線以實際專案檔案為準：

- Unreal C++ runtime 位於 `Source/SpiritsCalling`，核心類別為 `ASpiritsGameMode`、`ASpiritsGameState`、`ASpiritsPlayerState`、`ASpiritsPlayerController`、`AUnitBase`、`AUnitAIController`、`ASoulShrine`、`AArenaBuilder`、`ASpiritPawn`、`ASpiritVRPawn`。
- `DemoMap.umap` 是目前唯一 `.umap`；Void/Sands 是同一張地圖內由 `AArenaBuilder::FArenaStyle` 與 replicated `ASpiritsGameState::MapIndex` 選擇的 runtime variant，不應在設計中假設存在第二個 `.umap`。
- PC 與 PCVR 輸入主要在 C++ runtime 建立，PCVR 已使用 OpenXR、`UMotionControllerComponent`、`UWidgetInteractionComponent` 與世界空間 `UWidgetComponent`。
- `Config/DefaultGame.ini` 已設定 Shipping、IoStore、`/Game/Maps/DemoMap`；`Config/DefaultEngine.ini` 已啟用 Forward Shading、Instanced Stereo、OpenXR 相關設定與 `3DWidget` collision channel。
- `RawAssets/AI` 目前包含四文明 pattern、Void/Sands ground/sky 與 store capsule concept；`RawAssets/Audio` 與 `Content/Audio` 各有 9 個音訊檔案/資產。
- `Scripts/smoke_preflight.py` 是既有的自動 pre-flight 與手動 Smoke Matrix 結果產生器，應擴充為 Release_Readiness_Record 的 evidence source，而不是另起一套無法對齊的結果格式。
- 專案 `.uproject` 現在使用 UE `5.8`；既有文件部分仍寫 UE `5.7`。最終 package 前必須鎖定實際使用的 5.8 toolchain，並以同一 toolchain 產生 source revision、cook 與 package evidence。

### 1.1 非目標

本設計不包含 public matchmaking、dedicated server、Nakama authentication、anti-cheat、公網配對、Quest 原生 Android 出貨保證或 Steam lobby。出貨 multiplayer scope 僅為 Windows PC/PCVR 的 listen server LAN 與朋友直接連線；任何 UI、商店文字或 release material 都不得把非目標能力呈現為已出貨功能。

## 2. 架構總覽

### 2.1 分層與責任邊界

| 層 | Unreal 類別/資產 | 責任 | 禁止事項 |
|---|---|---|---|
| Match authority | `ASpiritsGameMode` | server-only match FSM、隊伍、difficulty、civilization loadout、AI wave、Soul economy、summon transaction、win/end/restart | client 不直接改 phase、winner、Soul 或 spawn |
| Replicated match state | `ASpiritsGameState` | `Phase`、`WinningTeam`、`MapIndex`、difficulty/civilization snapshot、summon options、wave timing 與 presentation events | 不在 client 以本地 global 覆蓋 server snapshot |
| Player authority/state | `ASpiritsPlayerController`、`ASpiritsPlayerState` | owner RPC、possess/summon request、mode detection、team/Souls、owner achievement event routing | Server 不使用任意 server player identity 代替 LAN event owner |
| Combat actor | `AUnitBase`、`ASoulShrine` | replicated stats/health/team、server hit/damage/death、possessable unit、light/heavy attack、BodyMID/shrine visuals | client 只請求，不在 client 結算傷害、擊退或死亡 |
| AI | `AUnitAIController` | server-side target scoring、避障、separation、AI attack/wave behavior | 不依賴 client NavMesh 或 client-only state |
| Platform pawn | `ASpiritPawn`、`ASpiritVRPawn` | PC/PCVR input projection、camera/movement、ray selection、VR menu、comfort feedback | 平台輸入不得繞過 `ASpiritsPlayerController` authority boundary |
| Presentation | `ASpiritsHUD`、`UMainMenuWidget`、HUD widgets、multicast FX/audio | HUD、kill feed、warning、menu、world-space widget、局部 FX | Presentation failure 不得更改 match outcome |
| Backend adapter | `USpiritsAchievements` (`UGameInstanceSubsystem`) | Steam readiness gate、identity、definition query、achievement writes、fallback log、session dedup | 沒有正式 identity/definition 時不得發 Steam write |
| Editor/release | manifest validator、Editor Python、`smoke_preflight.py`、BuildCookRun、Release record | import、hook、cook closure、launch、Smoke Matrix、P0 gates | store-only asset 不得因 editor reference 被 cook |

### 2.2 Match 狀態機

`ASpiritsGameState::Phase` 是唯一對外 match phase：

```text
WaitingToStart
  └─ StartBattle (server, map/loadout/difficulty snapshot ready)
       ↓
InProgress
  ├─ summon / possess / combat / economy / AI wave
  └─ enemy Soul Shrine destroyed → Ended
Ended
  └─ RequestRestartMatch → cleanup + new level/match initialization → WaitingToStart
```

- `StartBattle` 必須在 `DemoMap` 的程序化 arena collision 已建立後執行，並在 phase 變成 `InProgress` 前完成 difficulty、map、civilization loadout、Shrine 與 timers 的 server 初始化。
- `EndMatch` 必須具備 exactly-once guard；清除 Soul income、AI wave start/loop 與 pending heavy/temporary match timers，設定 `WinningTeam`，通知所有 participants，並保存一筆 end-of-match event。
- `ASpiritsGameState::Phase`、`WinningTeam`、`MapIndex`、difficulty/civilization snapshot 與 loadout 必須 replicated；client 使用 `OnRep` 或 equivalent callback 更新 HUD、arena style 與選單，不需 restart/reconnect。
- Restart 走同一個可測試的 `ResetMatchState()`/level-travel seam：清理舊 units、shrines、timers、AI state、winner 與 replicated presentation event，避免第二局沿用第一局的 Soul、wave number 或 achievement event。

### 2.3 資料模型與純邏輯介面

現有 `FMinionArchetype` 保留既有欄位：`DisplayName`、`MaxHP`、`AttackDamage`、`AttackRange`、`AttackInterval`、`MoveSpeed`、`SummonCost`、`Tint`、`MeshScale`。設計上增加或以平行 snapshot 保留 `ECivilization`/`CivilizationId`，讓 unit/shrine 的 material hook 可以選擇 pattern，而不依賴目前的 host global。

建議將以下資料抽成可在 Unreal automation 與外部 harness 呼叫的純函式/immutable model；實作可留在現有類別或新增 `SpiritsRules`/`SpiritsValidation` helper，不要求本階段決定檔名：

```cpp
struct FMatchSettings
{
    ESpiritsMatchPhase Phase;
    int32 Difficulty;             // normalized 0..2
    int32 MapIndex;               // normalized 0..1
    ECivilization TeamACiv;
    ECivilization TeamBCiv;
    bool bLan;
};

struct FSummonValidation
{
    bool bAccepted;
    int32 Cost;
    FString FailureCode;          // non-empty on rejection
};

struct FSummonTransactionResult
{
    bool bSpawned;
    int32 SoulsBefore;
    int32 SoulsAfter;
    bool bRefundApplied;
    FString FailureCode;
};

struct FHeavyAttackResult
{
    bool bAccepted;
    bool bHit;
    float ResolveTime;
    float Damage;
    float KnockbackMagnitude;
    float HitStopSeconds;
};
```

純 helper 的輸入不得讀取 global world 或 Steam SDK；world、actor spawn、network、Steam callback 只在 adapter 層。這使 P1–P9 可以用 generated inputs 測試，而端到端仍由 Unreal automation/packaged smoke 補足。

## 3. 核心玩法設計（Requirement 1）

### 3.1 Civilization loadout

`ASpiritsGameMode::BuildCivLoadout(Civilization)` 保持四個文明各三筆配置，輸出固定長度 3。每筆必須對 `MaxHP`、`AttackDamage`、`AttackRange`、`AttackInterval`、`MoveSpeed`、`SummonCost`、`Tint`、`MeshScale` 做有效性驗證；同一文明內任兩筆的 stat vector 不得完全相同。`RebuildLoadouts()` 在 `InitGameState`/新 Match 建立時產生 Team A/B snapshot，再複製到 `ASpiritsGameState`。

- Team A/B 的 civilization 與 loadout 必須是 match snapshot；Match 開始後 UI 的循環選擇不得偷偷改變已在場 units 的 Stats。
- 每個 spawned `AUnitBase` 保存其文明 ID 與 `FMinionArchetype` snapshot，讓 client `OnRep_Visuals` 可選 BodyMID pattern；Team color 永遠由 `SpiritsTeams::GetTeamColor` 提供，文明 tint/pattern 只能乘在隊色上，保證藍/紅同時可辨識。
- `FArenaStyle` 仍以 `GSpiritsMapIndex`/`GameState::MapIndex` 選 Void/Sands；map index 必須 clamp 到 `[0,1]`，不得讓 client 以任意整數建立不同 arena。

### 3.2 Server-authoritative summon transaction

所有 PC/VR summon input 最終進入 `ASpiritsPlayerController::Server_SummonUnit`，再由 `ASpiritsGameMode::SpawnUnitForPlayer` 執行以下順序：

```text
request received
  → identify requesting PlayerState and TeamId
  → require GameState.Phase == InProgress
  → resolve team loadout snapshot
  → validate archetype index against that loadout
  → validate non-negative cost and Soul balance
  → validate location/ground projection and spawn policy
  → atomically deduct exact cost
  → SpawnUnitForTeam / FinishSpawning
       success → commit, replicate unit, report summon event to owning client
       failure → exactly-once refund exact deducted cost, report failure reason
```

- Invalid phase、team/loadout mismatch、index、Soul、location 或 spawn policy 任一失敗，都不得 spawn、不得扣 Soul，並以 owner-only `Client_SummonFailed(FailureCode)` 或等效 presentation 回報。
- 扣款與 spawn 必須以 transaction token/guard 防止 deferred spawn callback、死亡 cleanup 或 exception-like failure 重複 refund。`bRefundApplied` 只允許由該 transaction 寫入一次。
- AI wave 使用 `SpawnUnitForTeam`，不走 human achievement report；AI 不可消耗人類 PlayerState Soul。
- 維持現有 economy：每秒 `SoulsPerSecond`，Normal 為 3；Easy/Hard 只按已定義 difficulty tuning 改變收入/pressure，kill team reward 為 25，possessing player 的 personal bonus 與既有行為保持一致，Shrine below 50% 的 comeback bonus 也必須明確記入 rules snapshot。

### 3.3 Possession、combat 與 Soul Shrine

`ASpiritsPlayerController` 是 possession authority boundary：server 驗證目標是存活、非 structure、同隊、`InProgress` 且尚未被其他 player 控制；成功後保存 spirit pawn、移除 AI controller、`Possess(Unit)`。死亡或 unpossess 由 server 將 unit 還給 AI 或重建 spirit pawn。`AUnitBase::HandleDeath` 只允許一次，通知 `GameMode::NotifyUnitDied`，再處理 controller、collision、lifespan。

`AUnitBase` 的 light attack 保留現有 interruption/cooldown/possession modifier。heavy attack 使用明確狀態：

```text
Idle → HeavyWindup (0.40 s, movement 0.35x)
  ├─ death/hard interruption → Cancelled, no hit, restore movement
  └─ resolve → HeavyHit (damage ×2.2, knockback ×2.0, hit-stop 0.12 s)
       → Cooldown (AttackInterval ×2.2) → Idle
```

- Server 只在 resolve 時做 sweep、enemy-team filter、damage、knockback；Multicast 只做 windup/hit FX/audio/local hit stop。
- 若目前沒有獨立 hard-stun 系統，死亡是最低限度 interruption；設計保留 `CancelHeavy_Server(reason)` seam，避免日後加入硬直時破壞 0.4 秒未命中規則。
- P4 的 oracle 使用 damage `base × 2.2`、knockback magnitude `base × 2.0`、取消時間 `<0.4s` 不產生 heavy hit、hit-stop `0.12s`（以 engine timer tolerance 比對）。
- `ASoulShrine` 繼承 `AUnitBase`，`bIsStructure=true`、不能被 possess/AI 控制；其死亡是唯一 Match victory trigger。`GameMode::EndMatch` 以被摧毀 Shrine 的 opposite team 設為 winner，並複製 result。

### 3.4 Difficulty 與 AI wave

Difficulty 在 Match 開始前由 Host/menu snapshot：Easy、Normal、Hard 每一對至少有一個不同的 `AIWaveInterval`、`MaxWaveSize`、`SoulsPerSecond` 或其他明確 pressure/economy parameter。`StartBattle` 完成 snapshot 後才設 `Phase=InProgress`。

單機規則：`InProgress` 後最多 15 秒呼叫 `MaybeStartAIWaves`；只有 Team B 沒有人類 `PlayerState` 時啟動。`PostLogin` 發現人類 Team B 後立即清除 wave timer、標記不再排後續 AI wave。AI controller 每 0.5 秒重新選 target、每約 0.12 秒更新 obstacle probe，保留 weighted low-HP target、Shrine fallback、避障與 separation，不增加 client-side AI。

## 4. PC、PCVR、LAN 與 replicated state（Requirement 2）

### 4.1 啟動與模式選擇

- Windows 無 HMD：`ASpiritsPlayerController::BeginPlay` 偵測 `GEngine->XRSystem`，保留 `ASpiritPawn`，載入 `DemoMap`，顯示 PC menu/PC match flow。
- OpenXR HMD：透過 OpenXR tracking state（Quest Link 或 SteamVR）向 server `Server_ReportVRMode(true)`；server 只在未 possession 時切換 `ASpiritVRPawn`。啟動前必須完成 mode selection，不能讓玩家先進入錯誤 flat pawn 再切換。
- OpenXR plugin、XRBase、HeadMountedDisplay 與既有 input mappings 保留。PCVR hardware 判定屬 packaged integration gate，不用 fake HMD 宣稱通過實機支援。

### 4.2 PC 與 VR input contract

`ASpiritPawn` 提供 WASD/方向鍵 RTS movement、Q/E rotation、wheel zoom、1/2/3 selection、LMB possession、RMB ground summon、M/Esc menu；`AUnitBase` possession mode 提供 movement、light、heavy、jump、unpossess。所有 action 只產生 controller request，不直接改 authoritative state。

`ASpiritVRPawn` 保留：左 stick spirit movement、右 stick vertical/snap turn、right trigger pointed possession、A pointed summon、X summon cycle、menu button、possessed unit 的 heavy input forwarding。輸入測試使用 action adapter，而非把每個 hardware key 當作獨立 gameplay implementation。

### 4.3 世界空間 VR menu

`VRMenuComp` 重用 `UMainMenuWidget`，內容必須包含 Play、difficulty、map、civilization、Host LAN、Join IP、Resume、Quit。`WidgetInteractionComponent` 使用既有 `ECC_Visibility` trace/collision；menu 開啟時：

1. 啟用 right-controller widget interaction，hover 只更新被指向的 widget item。
2. trigger press/release 對應 pointer press/release；不可將同一輸入同時送到 possession。
3. `bMenuOpen` 使 movement/vertical/summon gameplay handlers return，玩家 transform 不應因 menu input 改變。
4. menu 關閉後恢復 game-only input；join failure 顯示 owner/local error，不把 travel failure 當作 connected state。

Comfort layer 位於 VR pawn：移動速度驅動 camera vignette，停止時平滑恢復；`LastSnapTurnTime` 以 server-independent local monotonic world time gate，距離前一個 accepted snap turn `<0.35s` 直接拒絕，45 度 snap turn 僅在 accepted 時執行。

### 4.4 Listen server 與 LAN state

- Host 以 `OpenLevel(/Game/Maps/DemoMap?listen)` 建立 listen server；Join 使用輸入 IP 的 `ClientTravel`。不引入 public matchmaking 或 dedicated server。
- Host/server 分配 Team A/B，server snapshot difficulty/map/civ；client 僅透過 RPC request。`ASpiritsGameState` 需複製：team assignment、phase、winner、MapIndex、difficulty/civ snapshot、loadout、accepted summon/possession/combat outcome 的可觀測狀態。
- Actor replication：`AUnitBase` replicated movement、Stats、Health、TeamId、structure flag；controller possession state 以 replicated pawn/controller relation 或明確 owner state mirror 供 HUD 顯示。
- Disconnect：server 清除該 player 的 connection/possession bookkeeping、寫入 `Disconnect` record；其餘 instance 不停止 movement/menu input，也不虛構其為仍 connected。Join failure 由 local travel failure callback/timeout 轉成明確錯誤 event，Host 保持可操作，`bMatchConnected=false`。
- event convergence 測試採 host snapshot 為 oracle，對每個指定事件等待 replicated state stable，再比對 client snapshot；不要用畫面文字作為唯一 LAN oracle。

## 5. Steamworks achievement subsystem（Requirement 3）

### 5.1 Readiness gate 與 backend adapter

`USpiritsAchievements` 維持 `UGameInstanceSubsystem`，跨 level travel 保存本 session counters。新增 backend readiness state：

```text
Disabled/Fallback
  → ConfigValid (non-zero, non-placeholder approved App ID)
  → OSSReady (OnlineSubsystemSteam loaded)
  → IdentityReady (current Steam UniqueNetId valid)
  → DefinitionsReady (QueryAchievements completed successfully)
  → WriteEligible
```

只有正式或核准測試 App ID（非 0、非 placeholder `480`，除非明確標為 development-only path）且 Steam client/identity/achievement interfaces ready，才可將 release path 標為 Steam write eligible。沒有 Steam client 時保留本機 log、screen debug、counter/achievement intent，不阻擋 PC/LAN gameplay；fallback-compatible development verification 可以 pass，但 `SteamReleaseAcceptance` 必須保持未通過。

需要加入 `OnlineSubsystem`、`OnlineSubsystemUtils` 以及在選定 integration 可用時的 Steam achievement interface dependency；plugin/ini/`steam_appid.txt` 與正式 App ID 由 release gate 控制，不在沒有核准 ID 時把 `480` 當成上架條件。

### 5.2 Query-before-write、ID 與 ownership

唯一允許的 ID 集合如下，大小寫完全固定：

```text
ACH_FIRST_WIN
ACH_WIN_EASY
ACH_WIN_NORMAL
ACH_WIN_HARD
ACH_POSSESS_KILL_50
ACH_SUMMON_100
ACH_WIN_ALL_CIVS
ACH_LAN_WIN
```

`USpiritsAchievements` 內部流程：

1. `RegisterDefinitionSet()` 建立 exact set；任何事件 ID 不在 set 直接拒絕並寫 local error。
2. `EnsureDefinitionsQueried(UserId)` 先呼叫 `QueryAchievements`，成功 callback 建立 definition cache；query fail 不能發 write。
3. `UnlockAchievement(Id, EventOwner)` 檢查 exact definition、identity、session dedup set，再建立 `FOnlineAchievementsWrite`。同一 user/session/ID 最多產生一次 write request。
4. write callback success/failure 都寫入 local debug/release evidence；local progress/counters 不因 backend failure 消失。若採 retry，必須用 request token 防止相同 event 重複產生 write。
5. client-generated LAN event 的 `EventOwner` 由 server 在收到事件時綁定來源 `PlayerController/PlayerState`；owner-only Client RPC 只通知該 player 的 subsystem，該 subsystem 取自己的 Steam identity，不使用 server player index 或任意 Team B identity。

Win semantics：每場 qualifying win 產生 `ACH_FIRST_WIN` 與恰好一個 normalized difficulty ID；只有 `bLan=true` 產生 `ACH_LAN_WIN`；possess kill 累計達 50、summon 累計達 100、四文明 win bitmask 達 `0x0F` 時各產生一次 milestone。progress scope 先明確固定為 GameInstance session；若未來接 Steam Stats 跨啟動，必須另行版本化並保持 achievement ID/threshold semantics 不變。

## 6. Generated asset import、manifest、material hooks 與 cook 分類（Requirement 4）

### 6.1 Canonical manifest

以一份可被 Editor Python 與外部 validator 共同讀取的 manifest 為 canonical source（格式可為 JSON；放在 `RawAssets/AI` 或 `Docs/Release`，實作時固定一個版本化路徑）。每一筆至少包含：

```json
{
  "source": "RawAssets/AI/Civilizations/East/East_pattern.png",
  "category": "civilization_pattern",
  "runtimePath": "/Game/Textures/Civilizations/East_pattern",
  "hook": "BodyMID.PatternTex|SoulShrine.PatternTex",
  "cookClass": "runtime",
  "validation": { "powerOfTwo": true, "maxDimension": 2048 }
}
```

canonical entries 必須保留下列 exact source path/category：

- `RawAssets/AI/Civilizations/East/East_pattern.png` → East pattern
- `RawAssets/AI/Civilizations/Norse/Norse_pattern.png` → Norse pattern
- `RawAssets/AI/Civilizations/Egypt/Egypt_pattern.png` → Egypt pattern
- `RawAssets/AI/Civilizations/Cyber/Cyber_pattern.png` → Cyber pattern
- `RawAssets/AI/Arenas/Void/Arena_Void_ground.png`、`Arena_Void_sky.png` → Void ground/sky
- `RawAssets/AI/Arenas/Sands/Arena_Sands_ground.png`、`Arena_Sands_sky.png` → Sands ground/sky
- `RawAssets/AI/Store/Store_capsule_concept.png` → store draft, `cookClass=store_only`

Import destination固定為 `/Game/Textures/Civilizations` 或 `/Game/Textures/Arenas` 的文明/arena 子資料夾。import operation 必須由 source path 決定 destination/name，`replace_existing` 可重跑但不得因重跑產生第二個 runtime asset；manifest 保留 exact source path 與 import result/hash/timestamp。

### 6.2 Validation 與 material hooks

- Gameplay texture 只有在寬、高皆為 power of two 且每一維 `<=2048` 才算 import-valid。現有 `CheckTextureSettings.py` 的 4096 audit limit 必須在正式驗證 profile 中分成 `GameplayTextureProfile=2048` 與 `DocumentedSkyboxExceptionProfile`；未有 exception record 的 sky texture 仍受 2048 限制。
- 失敗 asset 必須 `runtimeReady=false`，record exact source path、non-empty failure reason、affected hook；沒有 hook 時明確寫 `no-hook-assigned`，不能留空。
- `wire_civ_materials.py` 的 idempotent import 與 `M_UnitBody` `PatternTex`/`Color`/`EmissiveStrength` 概念保留；正式 hook 再由 `AUnitBase::ApplyVisuals` 依 civilization 設定 BodyMID 的 `PatternTex`，`ASoulShrine::ApplyVisuals` 使用相同 civilization pattern。四文明必須是 one-to-one mapping，不得兩文明 resolve 同一 pattern。
- `AArenaBuilder::FArenaStyle` 為 Void/Sands 各保存 ground/sky soft reference 或 canonical runtime path；`BuildGeometry/BuildLighting`/arena material hook 依 MapIndex 選 pair。MapIndex replicated 後 client 重新 resolve 同一 pair。
- Team A/B visual color 仍由 blue/red team color 乘 pattern/tint；scene validator 必須以同一 scene 同時放置兩隊，確認兩色都可見，不以文明色覆蓋隊色。
- Required imported references 不得在 PC/PCVR runtime 變成 missing reference、black/default material 或未進 cook。若 required hook load 失敗，runtime 產生明確 asset error 並讓 package acceptance blocked；不得用 silent default material 讓 smoke 假通過。Prototype engine shapes 可作非-required cosmetic fallback，但不可冒充 generated hook 已通過。
- Store capsule concept 永遠在 store-only manifest，不能被 DemoMap/BodyMID/ArenaBuilder 引用；直到 final capsule、6–10 screenshots、30–60 秒 trailer 全部 gate approved 前，只能標示 draft，不進 runtime cook。

## 7. Shipping/IoStore packaging 與 launch validation（Requirement 5）

### 7.1 可重現 package pipeline

正式 pipeline 以 UE 5.8 固定 toolchain 執行 `BuildCookRun` 或等效 UAT command：

```text
-project=Spirits_Calling.uproject
-targetplatform=Win64
-serverconfig=Shipping
-build -cook -stage -pak -iostore -archive
-archivedirectory=Builds/Windows
-map=/Game/Maps/DemoMap
```

實際參數須由版本化 build script 統一，不以 Editor UI 的暫存選項為唯一來源。pipeline 必須：

1. 使用 project code build 與 Shipping configuration。
2. 啟用 IoStore，檢查 staged container/manifest，而非只檢查 ini。
3. Cook `/Game/Maps/DemoMap`，closure 包含 Void/Sands runtime style dependencies、四文明 pattern hooks、PC/PCVR menu、achievement fallback/local log path、9 audio assets 與 `S_Ambient` looping/fallback path。
4. 產出固定於 `Builds/Windows/`，package manifest 記錄 source revision、engine/toolchain、configuration、map、IoStore、path。
5. Store-only capsule 與未被 runtime reachable 的 draft material 不得進 cook set。

### 7.2 Closure、launch 與 metadata validation

Package acceptance 分三層：

- **Static closure**：從 DemoMap、GameMode/GameState、PC/VR pawns、menu、material hooks、achievement fallback、audio fallback 遍歷 soft/hard references；每一個 required runtime object 必須有 cooked object，沒有 editor-only、missing map/class/asset 或 store-only reference。
- **Launch gate**：在未安裝 Unreal Editor 的 clean Windows machine 啟動，120 秒內到 title/menu；從 menu 開 PC Match，120 秒內到 `InProgress`；log 與畫面不得含 `missing-map`、`missing-class`、`missing-asset`。兩個 packaged LAN instance 連線 deadline 為 60 秒。
- **Platform gate**：Quest Link/SteamVR package 在可操作流程前選 `PCVR_Mode`；PCVR menu、possession、summon、heavy attack、return-to-spirit 五項各自寫入 Smoke_Matrix `Pass`/`Fail`。

`DefaultGame.ini` 的 `ProjectID`、`ProjectDisplayedTitle=Spirits Calling`、`CompanyName=XiuJiang Studio` 保持不變。版本值由單一 `SpiritsVersion` source-of-truth 投影到 project metadata、menu、HUD、end-match presentation；package record 另記實際 resolved version。

## 8. Release_Readiness_Record、Smoke_Matrix 與 release scope（Requirement 6）

### 8.1 Record schema

`Release_Readiness_Record` 可輸出 JSON 加 Markdown 人讀版本；JSON 是 validator source。至少包含：

```json
{
  "packageAcceptance": "blocked|not_ready|ready",
  "packageVersion": "0.9.x",
  "sourceRevision": "git-short-sha",
  "engineVersion": "5.8",
  "cookMaps": ["/Game/Maps/DemoMap"],
  "platform": "Win64",
  "configuration": "Shipping",
  "ioStore": true,
  "packagePath": "Builds/Windows/...",
  "launchLog": "evidence/launch.log",
  "smokeMatrix": {},
  "gates": [],
  "unresolvedIssues": [],
  "earliestFailure": null,
  "machine": { "os": "", "cpu": "", "gpu": "", "ram": "" }
}
```

每個 gate 必須有 stable `id`、owner、status、evidencePath、timestamp 與 optional failure reason。P0 failure 必須將 package 設為 `not_ready`/`blocked`，保留 unresolved issue，並指向 gate、原因、evidence 與 resolution status。缺少 earliest step、reason、log path 的失敗 record 永遠 blocked；`ready` 只有在所有 gates pass、無 unresolved issue、每一筆 evidence 可定位時才可產生。

### 8.2 Smoke Matrix

固定矩陣至少包含：

- Easy、Normal、Hard：每種 difficulty 一筆，打至 Victory/Defeat end state 後 `Pass`/`Fail`。
- LAN：Host、Join IP、summon、possession、combat、victory、disconnect 分列結果；兩 instance 的 replicated match result 與 evidence path 一致。
- Quest Link PCVR：一筆 pass/fail 與可定位 screenshot/log/video；若有 SteamVR 相容硬體，另列一筆 SteamVR PCVR。
- PCVR 五案例：menu、possession、summon、heavy attack、return to spirit form，各自完成且無 missing errors。
- 5 分鐘 arena movement + active combat wave：保存完整 frame log，平均至少 90 FPS，路徑寫入 record。
- 30 分鐘 stability：每次 input/state query <=5 秒、無 crash、無連續 >10 秒 hang；第 5 分鐘與結束 private working set 增幅 <=20%，記錄兩次讀值/時間、OS、CPU/GPU/RAM。

既有 `Scripts/smoke_preflight.py` 的 A 段檢查 raw assets、DemoMap、build log、version 與 package；B 段結果 JSON 改以同一 record schema 匯入，避免「A 段 pass 但 B 段未測」被誤判為 ready。

### 8.3 非程式 release gates

Record 將下列各列為獨立 gate，且各自有 owner、evidence path、Pass/Fail：Steamworks account/App ID approval、capsule art、6–10 screenshots、30–60 秒 trailer、content-rating questionnaire、EULA/privacy、Early Access scope、9 audio imports 與 `S_Ambient` loop 或 documented runtime fallback。商店 scope 必須寫明 PC single-player、LAN/friend connection、PCVR，並明確排除 public matchmaking。

## 9. 錯誤處理、向後相容與可觀測性

### 9.1 Error taxonomy

所有可拒絕流程使用穩定 machine-readable code，並同時寫 server/local log 與適當 owner presentation：

- `Summon.InvalidPhase`、`Summon.InvalidLoadout`、`Summon.InvalidIndex`、`Summon.InsufficientSouls`、`Summon.SpawnFailedRefunded`。
- `Possess.InvalidTarget`、`Possess.WrongTeam`、`Possess.AlreadyControlled`。
- `Match.JoinFailed`、`Match.Disconnected`、`Match.RestartRejected`。
- `Steam.AppIdInvalid`、`Steam.SubsystemUnavailable`、`Steam.IdentityUnavailable`、`Steam.DefinitionQueryFailed`、`Steam.UnknownAchievementId`、`Steam.OwnerMismatch`。
- `Asset.SourceMissing`、`Asset.DuplicateMapping`、`Asset.InvalidDimensions`、`Asset.MissingHook`、`Asset.MissingCookReference`、`Asset.StoreAssetInRuntime`。
- `Package.MissingMap`、`Package.MissingClass`、`Package.MissingAsset`、`Package.IncompleteRecord`。

Error log 至少帶 timestamp、package/source revision、match/player context（不寫入不必要的 PII）、stable code、human reason、evidence path。Gameplay soft-fail 不應 kick client；安全/authority violation 只拒絕 request。

### 9.2 向後相容

- 保留 `FMinionArchetype` 現有欄位與 `SummonOptions`/`SummonOptionsB` 對 HUD 的既有讀取介面；文明 ID/asset hook 以新增欄位或 parallel snapshot 向後相容，舊 replicated client 缺欄位時使用明確的 `Unknown`/未通過 asset state，而非錯配文明。
- 保留 `DemoMap` 與 runtime Void/Sands model，不要求把 Sands 強制拆成新 `.umap`。
- 保留 `SpiritsAchievements` fallback API；OnlineSubsystemSteam 未啟用時仍可遊玩，但 release gate 不能把 fallback 當正式 Steam 成就通過。
- 保留既有 engine primitive/VFX/audio null-safe behavior 作為開發 fallback；required generated asset 的 release validator 仍必須拒絕 missing/default hook。
- UE 5.7 文件與 UE 5.8 實際 target 的差異需在 record 固定；不得混用 5.7 build log 與 5.8 package 證據。

### 9.3 已知不確定性

1. 正式 Steamworks App ID、後台八個 achievement definitions、測試帳號與法律/store materials 尚未提供；正式 Steam acceptance 目前不能視為通過。
2. `OnlineSubsystemSteam` API callback/Build.cs 相容性要以選定 UE 5.8 integration 實編驗證；設計要求 query-before-write，但不假設未驗證的 callback signature。
3. Generated PNG 的實際尺寸、skybox 是否超過 2048 與材質參數命名需由 manifest/import validation 最終確認；文件中的例外不是自動豁免。
4. VR `ECC_Visibility`/`3DWidget` 在 Quest Link 與 SteamVR 的 widget hit-test 仍需實機確認。
5. 30 分鐘 memory growth 的 private working set measurement tool 與最終測試機規格尚未固定；record schema 已固定欄位，實測時補齊。
6. 若未來要把 session progress 改為 Steam Stats 跨啟動，必須另定 migration 與 ownership policy，不可在本設計的 session dedup 上偷偷混用。

## 10. 測試策略與自動化 seams

### 10.1 測試分工

- **Property tests**：純規則/validator/adapter model，使用 generated inputs，每個 property 至少 100 iterations；測試名稱 tag 為 `Feature: spirits-calling-requirements, Property N: <property text>`。
- **Unreal automation tests**：spawn/replication、timer、OnRep、HUD routing、world widget、material hook 與 fake GameWorld；避免將所有 property 綁到昂貴真機。
- **Integration tests**：Steam client/OSS、Quest Link、SteamVR、兩個 packaged LAN instance、clean Windows launch、Cook/IoStore closure。
- **Smoke/performance tests**：固定 3 difficulty、LAN、PCVR、5 分鐘 90 FPS、30 分鐘 stability；結果只能寫入 record，不以未測項推導 pass。
- **Static/config tests**：exact IDs、App ID gate、project identity/version、scope text、manifest paths、store-only classification、package flags。

### 10.2 建議 test seams

| Seam | 可驗證內容 |
|---|---|
| `BuildCivLoadout` / `NormalizeMapIndex` | P1、P2 的純資料與 clamp |
| `ValidateSummon` + `Commit/RefundSummon` | P3 transaction、invalid request、exactly-once refund |
| `EvaluateHeavyAttack` | P4 timing、倍率、取消、cooldown |
| `AchievementEventRouter` + fake backend | P5 exact IDs、query order、threshold、owner、dedup/fallback |
| `AssetManifestValidator` / `HookResolver` | P6 exact path、bijection、dimension、exception、cook class |
| `ReplicatedMatchModel` + fake transport | P2/P7 event convergence、failed join、disconnect liveness |
| `PlatformActionRouter` / `ComfortTurnGate` | P8 action coverage、menu lock、snap interval、scope declaration |
| `PackageClosureValidator` / `ReadinessRecordValidator` | P9 cooked closure、required fields、blocked/ready invariant |
| Unreal functional automation | actors、timers、OnRep、HUD/menu、material/asset load、restart |
| `smoke_preflight.py` + BuildCookRun | P0 package/build/assets/launch evidence aggregation |

## 11. Correctness Properties

*A property 是應在所有有效 execution 上成立的行為特徵。每個 property 都是可被 automated test 實作的規格橋接；真機、Steam、Cook 與長時間穩定性仍需由本文件的 integration/smoke gates 補足。*

### Property 1: Civilization loadout shape and distinct entries

**For every** generated civilization in `{East, Norse, Egypt, Cyber}`, `BuildCivLoadout(civilization)` SHALL return exactly three summonable entries; every entry SHALL have valid configured health, attack, range, interval, movement speed, cost, tint, and mesh scale, and every pair within that civilization SHALL differ in at least one required stat value.

**Validates: Requirements 1.2**

### Property 2: Map selection and replication consistency

**For every** generated integer map selection, the host SHALL normalize it into `[0, 1]`, publish that value as `ASpiritsGameState::MapIndex`, and every simulated connected client SHALL resolve the same Map_Style and ground/sky hook pair as the host; **for any** failed Join IP attempt, the host SHALL remain operable and neither host nor joiner SHALL expose a connected Match state.

**Validates: Requirements 2.10, 4.4, 4.10**

### Property 3: Server summon validation and economy invariant

**For every** generated Soul balance, team loadout, archetype index, Match phase, location, validation outcome, and spawn outcome, a summon SHALL spawn and deduct exactly the archetype cost only when team loadout, index, phase, balance, and spawn validation all succeed; a validated spawn failure SHALL restore the original balance exactly once; any invalid request SHALL spawn no unit, deduct no Soul, and emit a non-empty failure indication.

**Validates: Requirements 1.3, 1.4, 1.5**

### Property 4: Heavy attack timing and multiplier invariant

**For every** generated positive base damage, knockback magnitude, target context, cooldown state, and cancellation time, an accepted heavy attack that reaches its hit time SHALL apply `base damage × 2.2` and knockback magnitude `base magnitude × 2.0` with `0.12` seconds of hit-stop within engine timer tolerance, while a heavy attack cancelled before `0.4` seconds SHALL apply no heavy hit.

**Validates: Requirements 1.6**

### Property 5: Achievement definition, event semantics, ownership, and deduplication

**For every** generated bounded event sequence containing wins, normalized difficulty values, civilization values, LAN flags, summon events, possession-kill events, repeats, Steam identity availability, definition-query results, ownership mappings, and fallback availability, every emitted achievement ID SHALL belong to the exact eight-ID set; a qualifying win SHALL emit `ACH_FIRST_WIN` and exactly one matching difficulty ID; `ACH_LAN_WIN` SHALL be emitted if and only if the win is LAN; threshold achievements SHALL appear exactly when their configured thresholds/bitmask are crossed; each user/session/ID SHALL produce at most one Steam unlock write request; a client LAN event SHALL target only its owning Steam identity; query failure or unknown ID SHALL produce zero Steam writes while retaining local progress/fallback records.

**Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.16**

### Property 6: Generated-asset manifest, hook, validation, and cook classification

**For every** generated canonical or mutated asset manifest, each valid required Generated_Asset SHALL have exactly one deterministic Imported_Asset runtime path, exact source path/category, required hook, and runtime cook classification; civilization patterns SHALL form a one-to-one mapping to their BodyMID/shrine hooks; Void and Sands SHALL resolve their exact ground/sky pairs; gameplay textures SHALL be power-of-two and no dimension greater than 2048 unless a documented skybox exception exists in the record; every invalid entry SHALL be non-runtime-ready with a non-empty reason and affected hook or explicit no-hook value; and the store-only capsule SHALL be absent from the runtime cook set.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8, 4.11**

### Property 7: LAN replicated match and remaining-client liveness

**For every** generated valid host/client sequence of menu selections and gameplay commands, all connected clients SHALL converge on the host's team assignment, difficulty, Map_Style, civilization loadout, Match phase, winner, accepted summon, possession, and combat outcomes after each authoritative event; **for any** optional disconnect point, the remaining client SHALL continue accepting movement/menu input and may reach `Ended`; a failed Join IP SHALL leave the host operable and SHALL not claim a connected Match.

**Validates: Requirements 1.10, 2.8, 2.9, 2.10, 4.10**

### Property 8: Platform interaction and release-scope invariant

**For every** generated PC and PCVR action sequence, PC_Mode SHALL expose the documented movement, summon selection/placement, possession, light/heavy attack, menu, and restart commands; PCVR_Mode SHALL expose spirit movement/turn, pointed possession/summoning, summon cycling, return from possession, and heavy attack; while the PCVR menu is open, right-controller hover/click SHALL route to the targeted item and movement input SHALL not change player transform; snap turns less than `0.35` seconds after the previous accepted turn SHALL be rejected; and the published multiplayer scope SHALL include LAN/friend connection while excluding public matchmaking, dedicated servers, Nakama authentication, and anti-cheat.

**Validates: Requirements 2.2, 2.5, 2.6, 2.11**

### Property 9: Packaging manifest closure and acceptance-record invariant

**For every** generated Windows package manifest and Release_Readiness_Record, an accepted package SHALL use project code build, Shipping configuration, IoStore, output path `Builds/Windows/`, and cook `/Game/Maps/DemoMap` with both Map_Style variants and all reachable Imported_Asset references; every required runtime reference from DemoMap, PCVR menu, achievement fallback, and audio fallback SHALL resolve to a cooked non-editor-only object, while store-only assets SHALL be absent; a valid record SHALL contain package version, source revision, cook maps, platform, configuration, IoStore status, package path, launch log, and Smoke_Matrix results; any packaging/launch failure or incomplete failure fields SHALL keep acceptance blocked and record the earliest reproducible step, reason, and log path; `ready` SHALL be possible only when every gate passes, every evidence path is locatable, and no unresolved issue exists.

**Validates: Requirements 5.1, 5.2, 5.3, 5.9, 5.10, 5.11, 5.12, 6.6, 6.8, 6.9**

## 12. Requirement traceability summary

| Requirement | Design coverage |
|---|---|
| R1.1–R1.2 | Match FSM、Shrine win condition、civilization loadout shape、P1 |
| R1.3–R1.5 | Server summon validation/transaction、failure indication、exactly-once refund、P3 |
| R1.6 | `AUnitBase` heavy state machine、0.4/0.12/2.2/2.0 constants、P4 |
| R1.7–R1.9 | difficulty snapshot、AI wave deadline/stop、income/kill reward invariants |
| R1.10–R1.12 | replicated GameState、kill/warning presentation、restart cleanup |
| R2.1–R2.3 | DemoMap PC boot、OpenXR HMD mode selection、PC/VR input contract、platform integration |
| R2.4–R2.7 | world-space menu、WidgetInteraction、menu input lock、comfort turn、90 FPS record |
| R2.8–R2.11 | listen server/LAN replication、disconnect/join failure、honest scope、P2/P7/P8 |
| R3.1–R3.5 | App ID/OSS/identity readiness、query-before-write、exact eight IDs |
| R3.6–R3.13 | win/difficulty/LAN/threshold/civ/dedup event router、P5 |
| R3.14–R3.16 | fallback non-blocking path、development-vs-release status、event-owner identity |
| R4.1–R4.4 | canonical manifest、deterministic import、BodyMID/shrine/Arena hooks、P6 |
| R4.5–R4.8 | runtime/cook closure、dimension validation、store-only classification、error records |
| R4.9–R4.11 | blue/red visual example、MapIndex client convergence、skybox exception gate |
| R5.1–R5.3 | UE 5.8 BuildCookRun、Shipping、IoStore、DemoMap/style dependency closure |
| R5.4–R5.8 | clean launch, PC/PCVR/LAN deadlines、Smoke Matrix integration gates |
| R5.9–R5.12 | readiness schema、metadata consistency、earliest-failure/block invariant、P9 |
| R6.1–R6.5 | fixed Smoke Matrix、Quest/SteamVR、LAN、30-minute stability evidence |
| R6.6–R6.7 | independent release gates、owner/evidence/status、honest Release_Materials scope |
| R6.8–R6.10 | P0 unresolved issue/readiness rules、audio one-time import and ambient fallback evidence |

本設計的主要尚待決策事項為：正式 Steamworks App ID 與八個後台 definition、Steam identity/query callback 的 UE 5.8 API 版本、生成素材實際尺寸與 skybox exception、Quest Link/SteamVR 測試硬體、最終 Windows 測試機與 memory telemetry 工具，以及是否將目前 session-only progress 在日後升級為 Steam Stats 跨啟動持久化。