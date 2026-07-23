# Implementation Plan: Spirits Calling Release Baseline

## Overview

本計畫把 `requirements.md` 的 Requirement 1–6 與設計文件的 Property P1–P9 轉成可直接交給 code-generation LLM 執行的增量任務。任務分成純規則/PBT、Unreal C++ runtime、PC/PCVR/LAN、Steamworks、Editor asset pipeline、Shipping/IoStore packaging，以及硬體整合與 release gate evidence；每一步都要在前一步的可測試 seam 上接續，最後由 package、Smoke_Matrix 與 `Release_Readiness_Record` 收斂成可追蹤的提交判定。

## Execution Checkpoint — 2026-07-23

- 為避免干擾目前執行中的 Development Editor，改以 DebugGame Editor target 建置；最新建置 `Result: Succeeded`、exit 0，未終止使用者的 Unreal Editor。
- 最新完整 Unreal automation 記錄為 `Saved/Logs/SpiritsCalling-Full-DebugGame-4.log`：discover `10` 項 `SpiritsCalling` tests，SteamReadiness、CoreRuntime authority/world、P1、P2、P3、P4、P5、P7、P8 全部 `Success`；P4/P8 各執行 `256 iterations`，queue empty、process status 0、wrapper exit 0。
- 新增 `CoreRuntimeWorldAutomationTests.cpp` transient-world regression，實際 spawn GameMode/GameState/PlayerState/Unit actor，覆蓋 `EndMatch → RequestRestartMatch → ResetMatchState`、OnRep/HUD route、kill feed、Ended/WaitingToStart presentation、Souls/loadout/wave/generation cleanup，以及 `AUnitBase::EndPlay()` local combat cleanup不送 multicast。targeted 證據為 `Saved/Logs/SpiritsCalling-CoreRuntimeWorld-DebugGame-9.log`：1/1 `Success`、queue empty、process/status 0。
- `AUnitBase::CancelPendingCombat()` 現在不依賴 net driver loopback，會先完成 local state/timer cleanup，再由 authority dispatch cosmetic cancellation；dev-only counter計算 dispatch 而非 implementation delivery。
- Python 完整 suite 最新實跑 `95 tests ... OK`；canonical asset manifest `9 entries` 通過；Shipping dry-run exit 0；Development Game target `Result: Succeeded`，輸出 `Binaries/Win64/Spirits_Calling.exe`。
- live reports：`version_consistency.json` 為 `pass/readinessEligible=true`；`audio_validation.json` 為 `blocked/readinessEligible=false`（無 cooked manifest/runtime ambient evidence）；`package_launch.json` 為 `not_run/readinessEligible=false`（dry-run 未啟動 process）。
- 已產生 `Docs/Release/Release_Readiness_Record_20260723_1526.json/.md`；`packageAcceptance=blocked`。validator CLI 已修正為由 `.uproject` 推斷 project-relative evidence base，仍正確回傳 `valid=false/ready=false`，只保留真實缺少的 stability、package/Smoke 與外部 release evidence。
- accepted Shipping/IoStore staged package 尚不存在，因此未建立 `package_closure.json`；clean Windows、三難度完整對局、雙機 LAN、Quest Link/SteamVR、5 分鐘平均 90 FPS、30 分鐘 stability、正式 Steam App ID、store/legal/audio runtime approval 均維持 `not_run/open`，不得標記 ready。

### 2026-07-23 追加 — PC/PCVR/LAN 可自動化部分（tasks #7）

- 新增可測試的純連線模型 `Source/SpiritsCalling/MatchConnection.h`（`SpiritsNet::FMatchConnectionModel`），並在 `ASpiritsPlayerController` 綁定/解除 `OnNetworkFailure`/`OnTravelFailure`：failed Join IP → `Match.JoinFailed` 且 `bMatchConnected=false`、host 保持可操作；已連線後斷線 → `Match.Disconnected` 且回到 operable idle。`MainMenuWidget` 新增 owner-facing `ShowConnectionError`，Join 前先 `BeginJoinAttempt`；`PresentConnectionError` 在無 LocalPlayer（headless）時只記 stable code 不建立 UI。這補上先前缺席的 R2.10/2.11 production wiring。
- 新增真 actor/world regression `Source/SpiritsCalling/Tests/PlatformActionWorldAutomationTests.cpp`：spawn 真 controller + `ASpiritPawn` + `ASpiritVRPawn`，驗證 menu 開啟時 PC/VR movement handler 不改變 `GetPendingMovementInputVector`、PC summon selection 不變、VR snap-turn 被 menu 擋；menu 關閉後 first snap turn 旋轉 actor、0.35s 內第二次被 comfort gate 拒絕、低於門檻軸不轉；並逐步驗證連線 lifecycle 的 phase/code/connected 旗標。pawn 以 `WITH_DEV_AUTOMATION_TESTS` 窄 seam 呼叫 production protected handlers，不污染 Shipping。
- 這讓 P8（純 router/gate，256 iterations）之外，首次有 actor-level transform-stability 與 menu-lock 證據；`1.9`/parent `1` 依此實跑證據勾選。
- packaged launch runner `Scripts/package_launch_smoke.py` 擴為 stage machine：新增 `title_menu`、`pc_in_progress` marker（production 端於 menu 開啟、match 進 InProgress 時輸出 `[SpiritsSmoke] Stage=...` Display log），`--require-stage` 缺 marker 即 fail、dry-run/fixture 維持 `not_run`；既有 DemoMap-ready 行為與測試相容不變。
- 新增 fail-closed evaluator：`Scripts/fps_smoke_runner.py`（5 分鐘 active-wave 平均 ≥90 FPS，需完整 machine/build metadata，fixture→`not_run`）與 `Scripts/lan_smoke_runner.py`（雙 instance host/client 收斂，`Match.JoinFailed`/`Match.Disconnected`/crash/hang 皆 fail-closed，fixture 或單一 log→`not_run`）。新增 `Scripts/test_platform_live_smoke.py` 17 tests 全過。
- 實跑證據：DebugGame Editor build `Result: Succeeded`/exit 0；targeted `Saved/Logs/SpiritsCalling-PlatformWorld-DebugGame-1.log` 1/1 `Success`；full suite `Saved/Logs/SpiritsCalling-Full-DebugGame-5.log` discover `11` tests 全 `Success`、queue empty 11、status 0；Development Game build `Result: Succeeded`；Python 完整 suite `Ran 112 tests ... OK`（TestWrite.txt 為既知無害噪音）。未中止使用者 Editor。
- 仍 blocked/未勾（外部/硬體 gate）：`4.1`（缺 accepted no-HMD packaged PC smoke）、`4.2`（Quest Link/SteamVR 實機）、`4.3`（真 WidgetInteraction hit-test）、`4.4`（雙機/雙 instance 60 秒收斂）、`4.5`/`7.3`（accepted package、clean Windows、5 分鐘 90 FPS）、parent `4`/parent `7`。新增 runner/evaluator 皆 fail-closed，未產生任何 live evidence，`Release_Readiness_Record_20260723_1526.json` 維持 `valid=false`/`ready=false`/`packageAcceptance=blocked` 不變。

### 2026-07-23 追加 — Steam/fallback 整合 regression（tasks #8 / 5.3）

- 先前 P5（`AchievementPropertyAutomationTests.cpp`）只測 `SpiritsRules` 純 router + fake `IAchievementBackend`；production 的 `USpiritsAchievements` GameInstance subsystem（controller Client RPC 實際呼叫的膠合層）沒有 automation。這是 reviewer 指出的 5.3 缺口。
- 新增 `Source/SpiritsCalling/Tests/AchievementSubsystemIntegrationAutomationTests.cpp`：以真 `UGameInstance` 為 outer 建立 `USpiritsAchievements`（`InitializeForAutomation()`→`RefreshBackendReadiness()`），在無 Steam approved App ID 的環境驗證：canonical 八 ID exact set；未知 ID 不記錄；`ReportWin` 依難度/LAN/civ 精確解鎖；重複 win 不重複解鎖（dedup）；49→50 possession kills 與 99→100 summons threshold；四文明 bitmask 完成才解 `ACH_WIN_ALL_CIVS`；且 subsystem 保持 `!IsSteamWriteEligible()`、`!IsSteamReleaseAcceptance()`、`IsDevelopmentFallbackPass()` — 沒有 Steam credentials 時明確未通過、只保留 local fallback 進度而非假 Pass。新增 dev-only seams（`InitializeForAutomation`/`HasUnlockedForAutomation`/`GetUnlockedCountForAutomation`/`GetPossessKills/Summons`）僅在 `WITH_DEV_AUTOMATION_TESTS`。
- 實跑證據：DebugGame Editor build `Result: Succeeded`/exit 0；targeted `Saved/Logs/SpiritsCalling-Achievements-DebugGame-2.log` = SteamReadiness + SubsystemIntegration 2/2 `Success`；full suite `Saved/Logs/SpiritsCalling-Full-DebugGame-6.log` discover `12` tests、無 Fail、queue empty 12、status 0。未中止使用者 Editor。`5.3`/parent `5` 依此實跑證據勾選。
- 仍 blocked：正式 Steam App ID/測試帳號/八個外部 definitions/live write callback 的 packaged Steam integration 屬 release owner/credentials gate，未取得前不得標記 Steam release acceptance；`Release_Readiness_Record` 相關 Steam gate 維持 `not_run/open`。

### 2026-07-23 追加 — Asset pipeline 契約 drift guard（tasks #9 / 6.4·6.5·7.5 可自動化部分）

- 盤點確認 6.4/6.5/7.5 的多數面向已由既有 validator/PBT 覆蓋：canonical manifest bijection/hook/dimension/store-exclusion/cook-classification（`PropertyP6AssetManifestTests.py`、`test_asset_validation.py`）、package closure incl. missing/editor-only/store-only/IoStore/map-object/audio-object（`test_package_closure.py`、`test_p9_package_record.py`）、九音效 import + S_Ambient loop/fallback + version/title/company + readiness ingestion fail-closed（`test_release_validation.py`）。這些不重複實作。
- 真正缺口只有兩處，且可在無 imported assets/無 cooked package 下自動化：
  - `wire_civ_materials.py`（Editor-only，硬 import `unreal`，無法 headless 執行）先前零測試覆蓋。
  - 無 drift guard 確保 package closure 的 runtime reference set 與 canonical manifest runtime paths 一致。
- 新增 `Scripts/test_asset_pipeline.py`（6 tests）：`MaterialHookContract` 綁定 canonical manifest 的四文明 pattern→`BodyMID.PatternTex|SoulShrine.PatternTex`、四 arena texture→`ArenaMaterialHook.{Void,Sands}.{Ground,Sky}` bijection、store capsule 無 hook/無 runtimePath，並以 source-scan 確保 Editor 腳本仍引用 `"Color"/"PatternTex"/"EmissiveStrength"/M_UnitBody` 且由 manifest `cookClass=="runtime"` 的 `runtimePath`/`hook` 驅動匯入（防 manifest↔Editor 腳本 desync）；`RuntimeReferenceContract` 確保 closure `_required_references` 涵蓋每個 manifest runtime path、store-only asset 永不進入 runtime reference set。
- 實跑證據：`python -m unittest Scripts.test_asset_pipeline -v` = 6/6 OK；完整 Python suite `Ran 118 tests ... OK`（TestWrite.txt 既知噪音）。live 佐證 blocked 仍成立：canonical manifest `VALID (9 entries)`；`audio_validation --execution-mode fixture` = `blocked`；`readiness_record_validator` 對 `Release_Readiness_Record_20260723_1526.json` 仍 `valid=false`/`ready=false`。
- 仍 blocked、未勾（缺 imported assets / cooked package / live ambient / Editor 執行）：`6.4`（R4.5 imported PC/PCVR runtime refs 需 cooked package 才能證明解析）、`6.5`（Editor Python 實際 import + M_UnitBody 建置 + team color 可視性需 Editor 與 imported assets）、`7.5`（R6.10 audio cook + S_Ambient live loop 需 cooked manifest/live evidence）、parent `6`/parent `7`。source existence 不得升級為 runtime-ready，`packageAcceptance` 維持 blocked。

**Code-generation prompt policy:**

> Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

## Tasks

- [x] 1. 建立純規則、驗證模型與 PBT 測試基礎
  - 所有純 helper 不得讀取 global world、Steam SDK 或真機狀態；以 immutable input/output model 支援 Unreal automation 與外部 manifest harness。測試資料必須使用 generated inputs，不能只測 requirements 中的 named examples；每個 PBT 至少執行 100 iterations，並使用 `Feature: spirits-calling-requirements, Property N:` 標籤。
  - [x] 1.1 建立可被 runtime、automation 與外部 harness 共用的純規則介面
    - **目標：** 定義 `FMatchSettings`、`FSummonValidation`、`FSummonTransactionResult`、`FHeavyAttackResult` 與 achievement、asset manifest、package/readiness 的純資料邊界；提供 `BuildCivLoadout`、`NormalizeMapIndex`、`ValidateSummon`、`EvaluateHeavyAttack` 等無 world side effect 的 seam。
    - **涉及檔案/模組：** `Source/SpiritsCalling/SpiritsTypes.h`、新增或調整 `SpiritsRules.h/.cpp`、`SpiritsCalling.Build.cs`，以及測試模組的共用 fixtures。
    - **實作重點：** 保留 `FMinionArchetype` 現有欄位與 HUD 讀取相容性；固定四文明/三 archetype、MapIndex `[0,1]`、summon failure code、heavy attack constants 與 release enum；純函式不得依賴 Actor、GEngine、OSS 或 Editor-only API。
    - **驗證方式：** 編譯 C++ target；以最小 fake input 執行每個 seam 的 smoke assertions，確認可在沒有 world、Steam client、Editor 的環境建立結果。
    - **完成條件：** 介面與穩定 machine-readable result 已可被後續 runtime、PBT、manifest validator 引用，且沒有孤立未接線的 helper。
    - _Requirements: 1.2, 1.3, 1.5, 1.6, 2.10, 3.3–3.16, 4.1–4.11, 5.9–5.12, 6.6, 6.8–6.10; Design test seams_

  - [x]* 1.2 撰寫 Property P1：文明 loadout shape、欄位有效性與 entry distinctness
    - **目標：** 以 generated Civilization 與 archetype index 驗證每個文明恰有三筆 summonable entries，所有 health/attack/range/interval/movement speed/cost/tint/mesh scale 已配置，且同文明任兩筆至少一個 stat vector 欄位不同。
    - **涉及檔案/模組：** `Source/SpiritsCalling/SpiritsRules*`、新增 `Tests/PropertyP1LoadoutTests.*` 或 Unreal automation/property harness。
    - **實作重點：** 產生四文明與邊界 index；oracle 檢查長度、欄位 predicates 與 pairwise inequality，不以四個固定 fixture 取代 generator。
    - **驗證方式：** 執行 PBT 100+ iterations；失敗輸出 seed、文明、index 與完整 stat vector。
    - **完成條件：** 測試通過且明確標記 `Property 1`，失敗時能重現最小 counterexample。
    - **Property 1；Validates: Requirements 1.2**

  - [x]* 1.3 撰寫 Property P2：Map selection、MapIndex replication 與 failed join
    - **目標：** 驗證任意整數 map selection 都 normalize 到 `[0,1]`，host、`ASpiritsGameState::MapIndex`、所有 simulated clients 與 Void/Sands ground/sky hook 一致；Join IP 失敗時 host 保持可操作且不建立 connected Match。
    - **涉及檔案/模組：** `Source/SpiritsCalling/SpiritsGameState.*`、`ArenaBuilder.*`、`SpiritsRules*`、新增 `Tests/PropertyP2MapReplicationTests.*`。
    - **實作重點：** 產生負值、0、1、最大值與 out-of-range map index，client count 1–4，以及成功/失敗 Join IP；以 authoritative snapshot 作 oracle。
    - **驗證方式：** 執行 PBT 100+ iterations；檢查 clamp、style/asset pair、host liveness 與 connection state。
    - **完成條件：** 通過所有生成案例，且 failed join 不會被誤判為 connected Match。
    - **Property 2；Validates: Requirements 2.10, 4.4, 4.10**

  - [x]* 1.4 撰寫 Property P3：server summon validation、扣款與 exactly-once refund
    - **目標：** 驗證只有 phase、team loadout、index、Soul、location/spawn 均有效且 spawn 成功時才扣除精確 cost；validated spawn failure 精確退款一次；所有 invalid request 不 spawn、不扣 Soul 並產生 failure indication。
    - **涉及檔案/模組：** `SpiritsRules*`、`SpiritsGameMode.*` 的 transaction seam、`SpiritsPlayerController.*`、新增 `Tests/PropertyP3SummonTransactionTests.*`。
    - **實作重點：** 產生非負 balance、合法/非法 loadout、所有 phase、`-1/0/2/3` 附近 index、validation/spawn success/failure 與重入 refund 事件。
    - **驗證方式：** oracle 比對 pre/post Soul、spawn count、`bRefundApplied`、rejection code 與 owner-facing failure。
    - **完成條件：** Property 3 100+ iterations 通過，且同一 transaction token 不會二次 refund。
    - **Property 3；Validates: Requirements 1.3, 1.4, 1.5**

  - [x]* 1.5 撰寫 Property P4：heavy attack wind-up、hit-stop、倍率與 cancellation
    - **目標：** 驗證 accepted heavy 在 0.4 秒 resolve 時套用 `base damage × 2.2`、knockback `×2.0`、hit-stop `0.12s`；0.4 秒前被取消不得產生 heavy hit。
    - **涉及檔案/模組：** `Source/SpiritsCalling/UnitBase.*`、`SpiritsRules*`、新增 `Tests/PropertyP4HeavyAttackTests.*` 與 fake clock/timer fixtures。
    - **實作重點：** 產生正 damage、knockback magnitude、target distance、cooldown/interruption state 與 `<0.4/==0.4/>0.4` cancellation time；timer tolerance 必須明確化。
    - **驗證方式：** 檢查 accepted/hit state、damage event、impulse magnitude、resolve timestamp 與 hit-stop duration。
    - **完成條件：** Property 4 通過，並能分辨 cancel、invalid cooldown 與正常 resolve。
    - **Property 4；Validates: Requirements 1.6**

  - [x]* 1.6 撰寫 Property P5：Steam achievement exact IDs、semantics、threshold、ownership 與 dedup
    - **目標：** 驗證 achievement event router 只使用八個 exact case-sensitive IDs，query-before-write、difficulty/LAN semantics、50/100/四文明 threshold、user/session dedup、owner identity 與 fallback behavior。
    - **涉及檔案/模組：** `Source/SpiritsCalling/SpiritsAchievements.*`、fake OSS/identity/definition backend、新增 `Tests/PropertyP5AchievementTests.*`。
    - **實作重點：** 產生 wins、難度、文明、LAN flag、重複事件、identity/definition query success/failure、local/remote owner 與 fallback path；unknown ID/query failure 必須 zero Steam writes 但保留 local record。
    - **驗證方式：** oracle 比對 emitted ID set、每場一個 difficulty ID、LAN condition、threshold crossing、每 user/session/ID write count ≤1 與 backend user ID。
    - **完成條件：** Property 5 100+ iterations 通過；fallback development pass 不會被當作 release Steam acceptance pass。
    - **Property 5；Validates: Requirements 3.3–3.16**

  - [x]* 1.7 撰寫 Property P6：generated asset manifest、hook、dimension 與 cook classification
    - **目標：** 驗證 canonical/mutated manifest 的 exact source path、category、deterministic runtime path、one-to-one civilization hook、Void/Sands pair、Power-of-two/2048 validation、skybox exception、invalid reason 與 store-only exclusion。
    - **涉及檔案/模組：** `Scripts/asset_manifest_validator.py`、`Scripts/CheckTextureSettings.py`、`RawAssets/AI` manifest、新增 `Tests/PropertyP6AssetManifestTests.py`。
    - **實作重點：** 產生 missing、duplicate、wrong category/path/hook、non-power-of-two、over-size、undocumented exception、invalid 與 store/runtime mutation；canonical manifest 僅接受九個指定 asset 類別。
    - **驗證方式：** 執行 PBT 100+ iterations；檢查每個 mutation 被拒絕，canonical exact-path manifest 被接受。
    - **完成條件：** Property 6 通過，且 invalid entry 永不標記 `runtimeReady=true`。
    - **Property 6；Validates: Requirements 4.1–4.4, 4.6–4.8, 4.11**

  - [x]* 1.8 撰寫 Property P7：LAN replicated match convergence 與 remaining-client liveness
    - **目標：** 驗證 host authoritative state 經 event-by-event replication 後，所有 client 對 team、difficulty、Map_Style、civilization/loadout、phase、winner、summon、possession、combat 一致；disconnect 後剩餘 client 仍能輸入並可達 Ended；failed join 保持 host 可操作。
    - **涉及檔案/模組：** `SpiritsGameState.*`、`SpiritsGameMode.*`、`SpiritsPlayerController.*`、新增 `Tests/PropertyP7LanConvergenceTests.*` 與 `ReplicatedMatchModel` fake transport。
    - **實作重點：** 產生延遲/重排的 non-authoritative commands、optional disconnect point、成功/失敗 Join IP；以 host snapshot、connection state 與 liveness 作 oracle。
    - **驗證方式：** 執行 PBT 100+ iterations，逐事件等待 stable snapshot 後比對所有 clients。
    - **完成條件：** Property 7 通過；disconnect/join failure 不會 freeze 或虛構 connected state。
    - **Property 7；Validates: Requirements 1.10, 2.8–2.10, 4.10**

  - [x]* 1.9 撰寫 Property P8：PC/PCVR interaction、menu lock、snap-turn gate 與 scope
    - **目標：** 驗證 generated PC/VR action sequence 覆蓋移動、召喚、附身、輕/重攻擊、選單、restart、VR pointed actions、summon cycle、return；VR menu routing 與 player transform lock；snap turn 間隔小於 0.35 秒時拒絕；scope 僅 LAN/friend、排除 public matchmaking 等非目標。
    - **涉及檔案/模組：** `SpiritPawn.*`、`SpiritVRPawn.*`、`MainMenuWidget.*`、新增 `Tests/PropertyP8PlatformActionTests.*` 與 `PlatformActionRouter`/`ComfortTurnGate` tests。
    - **實作重點：** 以 action adapter 與 generated timestamps 測試，不把每個 hardware key 寫成獨立 gameplay implementation；menu-open input 不可到達 movement handler。
    - **驗證方式：** oracle 檢查 action completion、hover/click target、transform 穩定、snap acceptance interval 與 scope declaration。
    - **完成條件：** Property 8 通過且 scope text 沒有宣稱 dedicated/public/Nakama/anti-cheat。
    - **Property 8；Validates: Requirements 2.2, 2.5, 2.6, 2.11**

  - [x]* 1.10 撰寫 Property P9：package closure 與 acceptance record invariant
    - **目標：** 驗證所有 accepted Windows package 使用 project code、Shipping、IoStore、`Builds/Windows/`、DemoMap 與兩 Map_Style dependencies；runtime references closed 且無 editor-only/store-only object；readiness record 欄位與 blocked/ready invariant 完整。
    - **涉及檔案/模組：** `Scripts/package_closure_validator.py`、`Scripts/readiness_record_validator.py`、`Scripts/smoke_preflight.py`、新增 `Tests/PropertyP9PackageRecordTests.py`。
    - **實作重點：** 產生 missing/duplicate/editor-only/store-only/wrong config/disabled IoStore/missing map/incomplete record/malformed failure mutations；ready 只允許所有 gates pass、evidence locatable 且無 unresolved issue。
    - **驗證方式：** 執行 PBT 100+ iterations；檢查 closure error、earliest failure、failure reason/log path 與 readiness state。
    - **完成條件：** Property 9 通過，且所有 malformed failure records 維持 blocked/not-ready。
    - **Property 9；Validates: Requirements 5.1–5.3, 5.9–5.12, 6.6, 6.8, 6.9**

- [x] 2. 實作 Unreal C++ core runtime 與既有玩法保存
  - [x] 2.1 完成 Match FSM、server snapshot、文明 loadout、MapIndex 與 replication
    - **目標：** 保持 `WaitingToStart → InProgress → Ended → restart` 狀態機，完成 phase/winner/difficulty/civilization/loadout/MapIndex snapshot 與 OnRep presentation，並保留四文明各三 entry。
    - **涉及檔案/模組：** `SpiritsGameMode.*`、`SpiritsGameState.*`、`SpiritsTypes.*`、`PDA_MinionData.*`、`ArenaBuilder.*`。
    - **實作重點：** `StartBattle` 在 arena collision 建立後才進 InProgress；MapIndex clamp；保持 `SummonOptions`/`SummonOptionsB` 相容；EndMatch exactly-once、複製 winner/result、restart 清除 units/shrines/timers/wave/achievement event。
    - **驗證方式：** Unreal automation 驗證 phase transition、replicated snapshots、四文明 loadout shape、兩 Map_Style resolve 與 restart cleanup。
    - **完成條件：** R1.1、R1.2、R1.7、R1.10、R1.12 與 Map replication 基礎通過，且 client 不可本地覆蓋 authoritative state。
    - _Requirements: 1.1, 1.2, 1.7, 1.10, 1.12, 4.10_

  - [x] 2.2 接通 server-authoritative summon transaction 與 Souls economy
    - **目標：** 將 PC/VR summon request 接至 server validation、atomic cost deduction、spawn commit 或 exactly-once refund，維持既有 income/kill reward/recipient/trigger rules。
    - **涉及檔案/模組：** `SpiritsPlayerController.*`、`SpiritsPlayerState.*`、`SpiritsGameMode.*`、`UnitBase.*`、`SpiritsHUDWidget.*`。
    - **實作重點：** `Server_SummonUnit` 只接受 owner request；驗證 phase/team/index/Soul/location/spawn policy；使用 transaction token/guard；AI wave 不消耗 human Soul；owner-only failure code/presentation。
    - **驗證方式：** Unreal automation + P3 harness；測 invalid phase/loadout/index/balance、spawn failure、double callback 與 successful replication。
    - **完成條件：** R1.3–R1.5、R1.9 全部通過，pre/post Soul 與 spawn count 可追蹤且沒有 duplicate refund。
    - _Requirements: 1.3, 1.4, 1.5, 1.9_

  - [x] 2.3 保存 possession、light/heavy combat、Soul Shrine victory 與死亡 exactly-once
    - **目標：** 保留附身 eligibility、light attack 與重攻擊行為，完成 heavy 0.4 秒 wind-up、0.12 秒 hit-stop、2.2 damage、2.0 knockback，並以 Soul Shrine destruction 作為唯一勝負觸發。
    - **涉及檔案/模組：** `SpiritsPlayerController.*`、`UnitBase.*`、`SoulShrine.*`、`UnitAIController.*`、`SpiritsGameMode.*`、`SpiritsVFX.h`/`SpiritsAudio.h`。
    - **實作重點：** server 驗證存活/非 structure/同隊/未被控制；heavy state `Idle → Windup → Resolve/Cancelled → Cooldown`；server 在 resolve 才 sweep/damage/knockback；HandleDeath exactly-once；EndMatch 設定 opposite team winner。
    - **驗證方式：** P4 harness、Unreal functional combat tests、heavy cancellation、enemy filter、Shrine end-state 與 duplicated death notification tests。
    - **完成條件：** R1.1、R1.6、R1.10、kill feed/warning trigger 的 runtime events 保持可觀測，combat 不由 client 結算。
    - _Requirements: 1.1, 1.6, 1.10, 1.11_

  - [x] 2.4 接回 difficulty snapshot、AI wave deadline/stop 與 AI behavior
    - **目標：** 在 Match 開始前套用 Easy/Normal/Hard 且每對至少一個 pressure/economy 差異；single-player 15 秒內啟動 Team B wave；human Team B 加入後停止後續 AI wave。
    - **涉及檔案/模組：** `SpiritsGameMode.*`、`UnitAIController.*`、`SpiritsGameState.*`、`SpiritsPlayerState.*`。
    - **實作重點：** snapshot 後才進 InProgress；保留 target scoring、Shrine fallback、separation/obstacle probe；PostLogin 清除 wave timer 並設 no-future-wave guard；維持 Souls per second、kill 25、personal bonus 與 comeback bonus。
    - **驗證方式：** Unreal timer/AI automation，以 fake clock 驗證 15 秒 deadline、difficulty parameter difference、human join cancellation 與 economy recipients。
    - **完成條件：** R1.7–R1.9 行為在單機與有人類 Team B 時皆可重現，沒有 client-side AI 或 human Soul 被 AI 消耗。
    - _Requirements: 1.7, 1.8, 1.9_

  - [x] 2.5 接通 kill feed、warning、HUD presentation 與 restart flow
    - **目標：** 將 match/kill/warning/end events 接至既有 HUD/menu，並讓 Ended participant 可不重啟 application 發起下一場。
    - **涉及檔案/模組：** `SpiritsHUD.*`、`SpiritsHUDWidget.*`、`MainMenuWidget.*`、`SpiritsGameState.*`、`SpiritsPlayerController.*`。
    - **實作重點：** OnRep phase/winner/presentation event 更新 UI；restart request 走 server reset/travel seam；presentation failure 不改 authority outcome；保留 PC 與 VR menu shared contract。
    - **驗證方式：** Unreal automation 驗證 kill feed/warning 出現、Ended result、restart 後第二局 phase/Soul/wave/achievement state clean。
    - **完成條件：** R1.11、R1.12 與 game result presentation 通過，且所有 UI action 都回到 controller authority。
    - _Requirements: 1.11, 1.12_

  - [x]* 2.6 撰寫 core runtime Unreal automation regression suite
    - **目標：** 以 fake GameWorld 或 Unreal automation 補足 spawn、replication、timers、OnRep、combat、restart 與 HUD routing，不用昂貴真機代替純/功能測試。
    - **涉及檔案/模組：** `Source/SpiritsCalling/Tests` 或既有 automation test target、`SpiritsGameMode.*`、`SpiritsGameState.*`、`UnitBase.*`、`SpiritsHUD.*`。
    - **實作重點：** 覆蓋 R1.1–R1.12 的例外與 end-state，測試名稱包含 requirement/property traceability。
    - **驗證方式：** UE automation commandlet/Editor test run；所有 core tests pass 且輸出 log 可定位。
    - **完成條件：** runtime regression suite 可在 CI/開發機重跑，失敗不需要人工讀畫面才能定位。
    - _Requirements: 1.1–1.12_

- [x] 3. Checkpoint — 完成純規則與 core runtime 後，確保編譯、PBT/automation 與既有玩法回歸測試通過；若出現設計問題，先修正對應 seam 再進入平台與 backend。

- [ ] 4. 完成 PC、PCVR 與 LAN listen-server 體驗
  - [ ] 4.1 接通 PC_Mode 啟動、PC input contract 與 mode selection
    - **目標：** 無 HMD 的 Windows 啟動 `DemoMap` 並進入 PC menu/match；完成 RTS movement、selection、summon placement、possession、light/heavy、menu、restart action routing。
    - **涉及檔案/模組：** `SpiritPawn.*`、`SpiritsPlayerController.*`、`SpiritsInputBuilder.h`、`MainMenuWidget.*`、`Config/DefaultInput.ini`。
    - **實作重點：** BeginPlay 依 XR state 先決定 pawn/mode；所有 input 只建立 controller request；保留既有 key/mouse mapping 與 possessed mode action。
    - **驗證方式：** PlatformActionRouter/P8 test + Windows packaged PC smoke automation；逐項記錄 action completion 與無 HMD mode。
    - **完成條件：** R2.1–R2.2 的 PC action sequence 可完成，且不透過 client 直接修改 authority。
    - _Requirements: 2.1, 2.2_

  - [ ] 4.2 接通 OpenXR PCVR pawn、控制器 action 與 comfort/snap-turn gate
    - **目標：** Quest Link/SteamVR HMD 在可操作流程前選 PCVR_Mode，支援 spirit movement、turn、pointed possession/summon、summon cycle、unpossess、heavy attack，並提供 comfort vignette 與 0.35 秒 snap-turn rejection。
    - **涉及檔案/模組：** `SpiritVRPawn.*`、`SpiritsPlayerController.*`、`SpiritsInputBuilder.h`、OpenXR/XRBase/HeadMountedDisplay dependencies、`Config/DefaultEngine.ini`/input config。
    - **實作重點：** 使用 motion controller、OpenXR tracking state、action adapter；comfort layer 依移動狀態控制 vignette；`LastSnapTurnTime` 使用 monotonic local time，menu/gameplay state 分流。
    - **驗證方式：** P8 action/turn harness；packaged integration logs 檢查 mode selection、每項 VR action 與 snap interval。
    - **完成條件：** R2.3、R2.6 及 PCVR interaction contract 通過，未連 HMD 時不誤選 VR。
    - _Requirements: 2.3, 2.6_

  - [ ] 4.3 完成世界空間 VR menu、WidgetInteraction 與 menu input lock
    - **目標：** VR menu 顯示 Play、difficulty、map、civilization、Host LAN、Join IP、Resume、Quit；right controller hover/click 正確路由，menu 開啟期間 movement 不改變玩家位置。
    - **涉及檔案/模組：** `MainMenuWidget.*`、`SpiritVRPawn.*`、`SpiritsPlayerController.*`、VR menu `UWidgetComponent`/`UWidgetInteractionComponent`、`Config/DefaultEngine.ini` collision channels。
    - **實作重點：** 保留 `ECC_Visibility` trace 與 `3DWidget` 設定；pointer hover/press/release 不得同時送 possession；`bMenuOpen` 使 movement/vertical/summon handlers return；join failure 顯示 local error。
    - **驗證方式：** WidgetInteraction automation/fake pointer test + P8；檢查 targeted item、player transform、menu close 後 input restore。
    - **完成條件：** R2.4–R2.5、R2.10 的 menu/error behavior 可重現，且不依賴畫面文字作唯一 oracle。
    - _Requirements: 2.4, 2.5, 2.10_

  - [ ] 4.4 完成 LAN host/join、authoritative replication、disconnect 與 failed-join handling
    - **目標：** 使用 listen server `OpenLevel(...?listen)` 與 IP `ClientTravel`，同步 team、difficulty、MapIndex/style、civ/loadout、phase、winner、summon、possession、combat；disconnect 後 remaining client 可繼續，join failure 保持 host operable。
    - **涉及檔案/模組：** `SpiritsGameMode.*`、`SpiritsGameState.*`、`SpiritsPlayerController.*`、`SpiritsPlayerState.*`、`UnitBase.*`、`MainMenuWidget.*`。
    - **實作重點：** server snapshot/RPC authority；replicate actor movement/stats/health/team/structure 與 possession mirror；清理 disconnect bookkeeping、寫 `Match.Disconnected`；travel failure/timeout 寫 `Match.JoinFailed` 且 `bMatchConnected=false`；不引入 public matchmaking/dedicated server/Nakama/anti-cheat。
    - **驗證方式：** P2/P7 fake transport + 兩 packaged Windows instances；逐事件比對 host snapshot、client state、remaining-client input liveness 與 failed join presentation。
    - **完成條件：** R2.8–R2.11 通過；兩 instance 可在 60 秒測試窗口內建立一致 Match，scope 宣告誠實。
    - _Requirements: 2.8, 2.9, 2.10, 2.11_

  - [ ]* 4.5 建立 PC/PCVR/LAN Unreal functional 與 packaged smoke automation
    - **目標：** 將平台 action、VR menu、LAN event convergence、disconnect 與 5 分鐘 arena/active-wave frame logging 接到可產生 evidence 的測試 runner。
    - **涉及檔案/模組：** `Scripts/smoke_preflight.py`、新增 `Scripts/platform_smoke_runner.py`、Unreal automation tests、`Source/SpiritsCalling/Tests`。
    - **實作重點：** PC action list、PCVR 五案例、Quest Link/SteamVR adapter、LAN host/join/disconnect、完整 5 分鐘 frame log 與平均 ≥90 FPS 欄位；測試只能將實測結果寫入 record，不可由未執行項目推導 Pass。
    - **驗證方式：** dry-run fake adapters 驗證 schema；實機/packaged run 由 release gate 讀取 evidence。
    - **完成條件：** R2.3、R2.7、R2.8 的 smoke evidence 可透過同一 record schema 匯入，且缺 evidence 保持 Fail/blocked。
    - _Requirements: 2.3, 2.7, 2.8_

- [x] 5. 完成 Steamworks 成就正式接線與 fallback 邊界
  - [x] 5.1 完成 UE 5.8 OnlineSubsystemSteam dependency、App ID readiness 與 backend state machine
    - **目標：** 讓非零、非 placeholder 且核准的 App ID 才能進入 `ConfigValid → OSSReady → IdentityReady → DefinitionsReady → WriteEligible`；Steam 不可用時保留 fallback 且不阻擋 PC/LAN。
    - **涉及檔案/模組：** `SpiritsCalling.Build.cs`、`SpiritsAchievements.*`、`Config/DefaultEngine.ini`、Steam plugin/`steam_appid.txt`（由 release 環境提供，不在未核准時提交真 ID）。
    - **實作重點：** 驗證 UE 5.8 callback/API compatibility；區分 development fallback pass 與 `SteamReleaseAcceptance`；記錄 `Steam.AppIdInvalid`、`Steam.SubsystemUnavailable`、`Steam.IdentityUnavailable`。
    - **驗證方式：** fake OSS state tests、development fallback test、配置 static check；正式 App ID/Steam client 留作 hardware/release gate。
    - **完成條件：** R3.1、R3.14、R3.15 的狀態與 error record 明確，沒有把 `480` 當上架通過條件。
    - _Requirements: 3.1, 3.2, 3.14, 3.15_

  - [x] 5.2 實作 query-before-write、八個 exact IDs、事件 semantics、threshold 與 owner routing
    - **目標：** 完成八個 exact Achievement_ID 的定義查詢、寫入、win/difficulty/LAN/threshold event router，且 client-generated LAN event 只寫 owning Steam identity。
    - **涉及檔案/模組：** `SpiritsAchievements.*`、`SpiritsGameMode.*`、`SpiritsPlayerController.*`、`SpiritsPlayerState.*`、`SpiritsGameState.*`。
    - **實作重點：** `RegisterDefinitionSet` exact set；`EnsureDefinitionsQueried` 成功前不得 write；每場 win 寫 first + 一個 normalized difficulty；LAN only `ACH_LAN_WIN`；50 possession kills、100 summons、四文明 win bitmask；owner-only RPC 綁定來源 PlayerState/Steam identity。
    - **驗證方式：** P5 fake backend + UE event tests；query fail/unknown ID zero writes、duplicate session event ≤1、remote owner mismatch error、fallback progress preserved。
    - **完成條件：** R3.3–R3.13、R3.16 通過，Steam write 不會對任意 server player identity 發送。
    - _Requirements: 3.3–3.13, 3.16_

  - [x]* 5.3 建立 Steam/fallback integration regression suite
    - **目標：** 覆蓋 Steam client/identity/definitions/write callback、fallback logging、local debug、session travel persistence 與 release-vs-development status。
    - **涉及檔案/模組：** `SpiritsAchievements.*`、fake OnlineSubsystem backend、`Scripts/readiness_record_validator.py`、automation tests。
    - **實作重點：** 測 backend unavailable 不阻擋 match、query failure no-write、write success/failure evidence、exact eight ID static check 與 owner route。
    - **驗證方式：** fake backend automation；若有 approved test App ID 再跑 packaged Steam integration，結果寫入 record。
    - **完成條件：** 每個 Steam gate 都有可定位 log/evidence；沒有 Steam credentials 時明確保持未通過而非假 Pass。
    - _Requirements: 3.1–3.16_

- [ ] 6. 建立生成素材 Editor import pipeline、material hooks 與 cook 分類
  - [x] 6.1 建立 canonical Generated_Asset manifest 與 deterministic import mapping
    - **目標：** 固定九個 AI source exact path/category，建立 source→`Content/Textures/Civilizations` 或 `Content/Textures/Arenas` 的 deterministic mapping、hash/timestamp/import result 與 store-only classification。
    - **涉及檔案/模組：** 新增版本化 `RawAssets/AI/asset_manifest.json`（或 design-approved canonical path）、`Scripts/asset_manifest_validator.py`、`Scripts/OrganizeAssets.py`/`SetupAssetFolders.py`、`Content/Textures/**`。
    - **實作重點：** civilization pattern 四筆、Void/Sands ground/sky 四筆、Store capsule 一筆；re-import 使用 source path/name/idempotent replace，不產生 duplicate runtime asset；store concept 不可被 runtime reference。
    - **驗證方式：** manifest static/P6 tests、重跑 import 命令並比較 destination/path count/hash。
    - **完成條件：** 九個 source path 全部有唯一 category/runtimePath/cookClass；store asset 明確 `store_only`。
    - _Requirements: 4.1, 4.2, 4.7_

  - [x] 6.2 實作 texture import validation、failure record 與 skybox exception gate
    - **目標：** gameplay texture 僅接受 power-of-two 且每維 ≤2048；skybox 超限必須先有 documented exception；失敗 asset 寫 exact source、non-empty reason、hook 或 `no-hook-assigned` 並保持非 runtime-ready。
    - **涉及檔案/模組：** `Scripts/CheckTextureSettings.py`、新增/調整 `Scripts/asset_manifest_validator.py`、`Scripts/wire_civ_materials.py`、`Release_Readiness_Record` schema/validator。
    - **實作重點：** 將現有 4096 audit 與正式 2048 gameplay profile 分離；不得以 sky category 自動豁免；error taxonomy 使用 `Asset.SourceMissing`、`Asset.InvalidDimensions`、`Asset.MissingHook` 等 stable codes。
    - **驗證方式：** P6 mutation suite、canonical asset scan、invalid manifest fixture；確認 failure 會使 package gate blocked。
    - **完成條件：** R4.6、R4.8、R4.11 可自動判斷，且任何 invalid asset 不會被標成 imported/runtime-ready。
    - _Requirements: 4.6, 4.8, 4.11_

  - [x] 6.3 接通 BodyMID、SoulShrine 與 ArenaMaterialHook
    - **目標：** 將 East/Norse/Egypt/Cyber pattern one-to-one 綁至 unit BodyMID/shrine；Void/Sands 各自綁 ground/sky pair；保留 blue Team A/red Team B 可同時辨識。
    - **涉及檔案/模組：** `UnitBase.*`、`SoulShrine.*`、`ArenaBuilder.*`、`SpiritsAssets.*`、`Scripts/wire_civ_materials.py`、`Content/Materials/**`、`Content/Textures/**`。
    - **實作重點：** `ApplyVisuals` 依 civilization snapshot 設 PatternTex；team color 由 `SpiritsTeams::GetTeamColor` 乘 pattern/tint；Arena style 依 replicated MapIndex resolve canonical pair；缺 hook 不得 silent default 假通過。
    - **驗證方式：** Editor utility/Unreal asset load test、同場 Team A/B scene validation、MapIndex LAN client resolve test。
    - **完成條件：** R4.3、R4.4、R4.9、R4.10 通過；四文明不共享錯誤 pattern，兩 Map_Style 不交叉 ground/sky。
    - _Requirements: 4.3, 4.4, 4.9, 4.10_

  - [ ] 6.4 接通 PC/PCVR runtime asset references 與 cook readiness classification
    - **目標：** 確保 imported pattern、arena textures、materials、menu/PCVR references 在 PC/PCVR runtime 可解析並進 cooked package；store-only concept 永不進 runtime cook。
    - **涉及檔案/模組：** `SpiritsAssets.*`、`UnitBase.*`、`SoulShrine.*`、`ArenaBuilder.*`、`Content/**`、`Config/DefaultGame.ini`、package closure validator。
    - **實作重點：** 以 hard/soft reference 清單建立 closure root；required missing/black/default/omitted asset 產生 `Asset.MissingCookReference` 並 block acceptance；prototype fallback 只能是非-required cosmetic path。
    - **驗證方式：** Editor load validation、cook manifest inspection、P6/P9 closure test；PC/PCVR packaged smoke 檢查無 missing reference。
    - **完成條件：** R4.5 與 R4.7 的 runtime/cook classification 可由 validator 證明，store concept 不在 cook set。
    - _Requirements: 4.5, 4.7, 4.8_

  - [ ]* 6.5 建立 Editor asset pipeline automation tests
    - **目標：** 自動測 import idempotency、manifest bijection、hook resolution、dimension validation、team color visibility、store-only exclusion 與 map variant resolution。
    - **涉及檔案/模組：** `Scripts/asset_manifest_validator.py`、`Scripts/wire_civ_materials.py`、新增 Editor utility test、canonical manifest fixtures。
    - **實作重點：** 測 canonical 與每一種 mutation；輸出可定位 source/runtime/hook/evidence path，不用人工 Content Browser 截圖作唯一證據。
    - **驗證方式：** Unreal Editor Python/automation 與外部 Python validator 雙邊執行。
    - **完成條件：** Asset import gate 可在 clean checkout 重跑，所有 invalid fixture 都 fail closed。
    - _Requirements: 4.1–4.11_

- [ ] 7. 建立 Shipping/IoStore packaging、closure、launch 與 readiness record automation
  - [x] 7.1 固定 UE 5.8 toolchain、version source-of-truth 與 BuildCookRun script
    - **目標：** 以版本化 script 產生使用 project code、Shipping、IoStore、`Builds/Windows/`、`/Game/Maps/DemoMap` 的可重現 Windows package。
    - **涉及檔案/模組：** 新增 `Scripts/build_shipping.ps1` 或等效 UAT wrapper、`Config/DefaultGame.ini`、`Config/DefaultEngine.ini`、`.uproject`、version metadata source、`Builds/Windows/`。
    - **實作重點：** 固定 UE 5.8；統一 `-build -cook -stage -pak -iostore -archive -map=/Game/Maps/DemoMap`；closure 包含 Void/Sands、four civ hooks、PC/PCVR menu、achievement fallback、九 audio assets 與 `S_Ambient` loop/fallback；保存 source revision/toolchain/package manifest。
    - **驗證方式：** static command/config test、一次 non-destructive dry-run argument check；實際長時間 build 由 release gate 執行。
    - **完成條件：** script 是唯一正式 packaging entry point，設定仍保留 ProjectID、`Spirits Calling`、`XiuJiang Studio`，且版本 source 可投影到 project/menu/HUD/end-match。
    - _Requirements: 5.1, 5.2, 5.3, 5.10_

  - [x] 7.2 實作 package closure validator 與 runtime/store classification checker
    - **目標：** 從 DemoMap、GameMode/GameState、PC/VR pawns、menu、material hooks、achievement fallback、audio fallback 遍歷 required references，拒絕 missing/editor-only/store-only object。
    - **涉及檔案/模組：** 新增 `Scripts/package_closure_validator.py`、`Scripts/asset_manifest_validator.py`、BuildCookRun staged manifest/IoStore container readers、`Config/DefaultGame.ini`。
    - **實作重點：** 檢查 cooked object closure、Map_Style variants、Imported_Asset references、achievement local path、S_Ambient fallback；錯誤使用 `Package.MissingMap/Class/Asset` 或 `Asset.StoreAssetInRuntime`。
    - **驗證方式：** P9 mutation fixtures、staged package manifest scan、dry-run closure report。
    - **完成條件：** P9 closure oracle 能列出每個 missing reference，且 store capsule/Editor-only asset 永不被 accepted。
    - _Requirements: 5.3, 5.11, 5.12, 6.8, 6.9_

  - [ ] 7.3 實作 clean Windows launch、PC match、PCVR/LAN deadline 與 Smoke_Matrix record ingestion
    - **目標：** 自動化 title/menu 120 秒、PC InProgress 120 秒、LAN connection 60 秒與 PCVR 五案例的 evidence capture，接入同一 `Release_Readiness_Record`。
    - **涉及檔案/模組：** `Scripts/smoke_preflight.py`、新增 `Scripts/package_launch_smoke.py`、新增 `Docs/Release/Smoke_Matrix.schema.json` 或 design-approved record schema、`Builds/Windows/` evidence outputs。
    - **實作重點：** clean machine 不依賴 Editor；log grep missing-map/class/asset；五個 PCVR cases 各自 Pass/Fail；Smoke_Matrix 未執行項為 Fail/NotRun 而不是自動 Pass。
    - **驗證方式：** fake launch/log fixtures、package smoke runner schema tests；accepted package 在 clean Windows/Quest Link/SteamVR/LAN 實測時寫入定位 evidence。
    - **完成條件：** R5.4–R5.8 的 deadline 與 missing error gate 可重跑，record 包含 launch log、package path 與每項 Smoke_Matrix result。
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [x] 7.4 實作 Release_Readiness_Record schema、earliest-failure 與 ready/blocked validator
    - **目標：** 建立 JSON source、Markdown human-readable output、stable gate id/owner/status/evidence/timestamp/failure reason/resolution status，並實作 blocked/not-ready/ready invariant。
    - **涉及檔案/模組：** 新增 `Scripts/readiness_record_validator.py`、`Scripts/readiness_record_writer.py`、`Docs/Release/Release_Readiness_Record.schema.json`（或實際決定路徑）、`Scripts/smoke_preflight.py`。
    - **實作重點：** 強制 package version、source revision、engine 5.8、cook maps、platform/configuration/IoStore/package path/launch log/Smoke_Matrix/machine fields；failure 必須保留 validation sequence 最早 step、reason、log path；P0 fail 或缺欄位維持 blocked。
    - **驗證方式：** P9 record mutation tests、JSON schema validation、valid-ready/blocked examples；ready 必須所有 gates pass、evidence locatable、unresolvedIssues empty。
    - **完成條件：** R5.9、R5.11、R5.12、R6.8、R6.9 的 acceptance 判定完全自動化。
    - _Requirements: 5.9, 5.11, 5.12, 6.8, 6.9_

  - [ ] 7.5 接入 nine audio one-time import、S_Ambient loop/fallback 與 package metadata checks
    - **目標：** 將九個 `RawAssets/Audio/*.wav` 的 documented one-time import、`Content/Audio` 對應與 `S_Ambient` loop 或 documented runtime fallback 變成獨立 gate，並檢查 version/title/company consistency。
    - **涉及檔案/模組：** `RawAssets/Audio/**`、`Content/Audio/**`、`SpiritsAudio.h`、`Scripts/smoke_preflight.py`、`Scripts/readiness_record_writer.py`、version/menu/HUD/end-match runtime metadata modules。
    - **實作重點：** import check idempotent、每檔 pass/fail/evidence；ambient loop/fallback 明確記錄；project settings、menu、HUD、end-match 使用同一 resolved version。
    - **驗證方式：** audio asset inventory/static check、runtime audio smoke fixture、record schema validation。
    - **完成條件：** R5.10、R6.10 的 audio/version gate 可定位且不會因已存在檔案而跳過 evidence。
    - _Requirements: 5.10, 6.10_

- [x] 8. 建立硬體整合與非程式 release gate 的 evidence 接口
  - [x] 8.1 建立 PCVR hardware evidence adapter（Quest Link/SteamVR）
    - **目標：** 提供可匯入 Quest Link 與 SteamVR run 的 machine profile、mode selection、menu/possession/summon/heavy/return evidence、screenshot/log/video path 與 Pass/Fail 狀態的 adapter；不以 fake HMD 宣稱實機通過。
    - **涉及檔案/模組：** `Scripts/platform_smoke_runner.py`、`Scripts/readiness_record_writer.py`、`Docs/Release/Smoke_Matrix` schema、`Source/SpiritsCalling/SpiritVRPawn.*` logs。
    - **實作重點：** Quest Link 必列；SteamVR 硬體可用時另列；每 run 保存 build version/source revision、HMD/runtime、OS、GPU/CPU/RAM、可定位 evidence；缺硬體維持 NotRun/Fail，不自動通過。
    - **驗證方式：** adapter fixture/schema tests；實際 Quest Link/SteamVR run 由人工執行並匯入 record。
    - **完成條件：** R2.3、R2.7、R5.6、R5.7、R6.3、R6.4 的硬體證據格式穩定且可追溯。
    - _Requirements: 2.3, 2.7, 5.6, 5.7, 6.3, 6.4_

  - [x] 8.2 建立 30 分鐘 stability telemetry runner 與 memory evidence
    - **目標：** 產生 30 分鐘 stability record：每次 input/state query ≤5 秒、無 crash、無連續 >10 秒 hang、第 5 分鐘與結束 private working set 增幅 ≤20%，並記錄 OS/CPU/GPU/RAM。
    - **涉及檔案/模組：** 新增 `Scripts/stability_runner.py`、`Scripts/readiness_record_writer.py`、package runtime log/telemetry output。
    - **實作重點：** 固定 clock/sample schema、hang/crash detector、5 分鐘與結束 timestamp/value、machine profile；測量工具與 build machine 若未固定，record 必須標示待人工決定而非假造結果。
    - **驗證方式：** deterministic telemetry fixtures、threshold boundary tests；accepted Shipping package 上實跑 30 分鐘後匯入 evidence。
    - **完成條件：** R6.5 可由 record validator 判斷，缺任一讀值或 machine field 時不可 ready。
    - _Requirements: 6.5_

  - [x] 8.3 建立非程式 Steam/store/legal/audio release gate schema 與 scope validator
    - **目標：** 將 Steamworks account/App ID approval、capsule art、6–10 screenshots、30–60 秒 trailer、content-rating、EULA/privacy、Early Access scope、nine audio imports 各列獨立 owner/evidence/status gate，並驗證商店 scope 誠實包含 PC single-player、LAN/friend、PCVR、排除 public matchmaking。
    - **涉及檔案/模組：** `Docs/Release/Release_Readiness_Record.schema.json`、`Scripts/readiness_record_validator.py`、`Scripts/smoke_preflight.py`、`Docs/Release/Release_Materials` scope text。
    - **實作重點：** 每 gate stable id、non-empty owner/evidence path/status；missing legal/store material 不得由 runtime code 代替；scope scanner 拒絕 public matchmaking/dedicated/Nakama/anti-cheat shipped claim。
    - **驗證方式：** schema/fixture tests、scope text static scan；實際 owner/evidence 由人工 release process 提供。
    - **完成條件：** R6.6、R6.7 gate 可獨立顯示 Pass/Fail，P0 fail 會保留 unresolved issue 與 resolution status。
    - _Requirements: 6.6, 6.7, 6.8, 6.9, 6.10_

  - [x] 8.4 建立最終 release gate aggregation 與 record reconciliation
    - **目標：** 將 packaging、Steamworks、asset、PC/PCVR/LAN、Smoke_Matrix、stability、audio、store/legal gates 聚合為唯一 `ready/not_ready/blocked` 判定，且禁止以 source code existence 推導通過。
    - **涉及檔案/模組：** `Scripts/readiness_record_validator.py`、`Scripts/smoke_preflight.py`、`Scripts/package_closure_validator.py`、Release record schema/output。
    - **實作重點：** gate dependencies 與 P0/P1 status 明確；任一 P0 fail 產生 unresolved issue（gate、原因/evidence、resolution）；ready 僅在所有 gate pass、所有 evidence locatable、unresolved empty。
    - **驗證方式：** full record fixtures：all-pass ready、missing evidence blocked、earliest failure blocked、Steam fallback development pass但 Steam release fail、store asset runtime mutation fail。
    - **完成條件：** `Release_Readiness_Record` 能重建每次 package acceptance 決策，且最後未測項不會被誤判為 Pass。
    - _Requirements: 5.9, 5.11, 5.12, 6.1–6.10; Property 9_

- [ ] 9. Final checkpoint — 確保所有 automated tests、PBT、Unreal automation、Editor validators、package closure 與 record fixtures 通過；只在實際硬體、Steam account/App ID、clean Windows package、LAN 雙機、SteamVR（若硬體可用）與 30 分鐘 stability evidence 完成後，才可將 `Release_Readiness_Record` 轉為 ready。不得在本任務中修改產品程式碼以外的需求範圍，且本規劃階段不執行實作。

## Notes

- Tasks marked with `*` are optional automated test subtasks for faster MVP；核心實作任務不得跳過。
- 每個 leaf task 都包含目標、涉及檔案/模組、實作重點、驗證方式與完成條件；實作者應保留 requirements/property traceability。
- P1–P9 已分別拆成獨立 PBT task，並與 runtime、Editor asset pipeline、packaging、hardware/release evidence 分開；PBT 使用 generated inputs，不能以固定 named examples 取代。
- Unreal runtime 以目前實際 `Source/SpiritsCalling` C++ 類別與 UE 5.8 為基線；Void/Sands 是 `DemoMap` 內的 runtime `MapIndex` variant，不可假設第二個 `.umap`。
- Steamworks 正式 gate 需要核准 App ID、八個 backend definitions、Steam identity 與測試帳號；`480` 只能作 development placeholder，不能使 release gate 通過。
- Quest Link、SteamVR、LAN 雙機、clean Windows launch、5 分鐘 ≥90 FPS 與 30 分鐘 memory stability 是人工/硬體整合證據；自動化任務只能提供 runner、schema、log/evidence ingestion，不能偽造 Pass。
- `Release_Readiness_Record` 必須保存 earliest reproducible failure、reason、log/evidence path；缺欄位、缺 evidence、未測項與 P0 failure 都保持 blocked/not-ready。
- 本 checkpoint 記錄實際 implementation/build/test evidence；未取得 accepted package、硬體或外部 owner evidence 的項目必須維持未完成或 blocked。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "6.1", "7.1", "7.4"] },
    { "id": 1, "tasks": ["6.2", "8.2", "8.3"] },
    { "id": 2, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10", "2.1", "5.1", "6.3", "7.2", "8.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "4.1", "4.2", "5.2", "6.4", "7.5"] },
    { "id": 4, "tasks": ["2.5", "4.3", "4.4", "5.3", "6.5", "7.3"] },
    { "id": 5, "tasks": ["2.6", "4.5"] },
    { "id": 6, "tasks": ["8.4"] }
  ]
}
```
