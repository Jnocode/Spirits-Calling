# Requirements Document

## Introduction

本 Quick Spec 定義 **Spirits Calling** 從目前可玩原型到完整上架體驗的需求基線。範圍包含既有 runtime/玩法能力的保存、Windows PC、PC VR（Quest Link/SteamVR）與 LAN 體驗、Steamworks 成就正式接線、ComfyUI 生成素材匯入與 Unreal Engine 打包驗證，以及外部上架門檻的可追蹤驗收。

需求基線以以下既有文件與實際專案結構為準：`Docs/DEV_PLAN_v0.9_to_v1.0.md`、`Docs/LAUNCH_TODO.md`、`Docs/SHIP_CHECKLIST.md`、`Docs/BUILD_AND_PLAY.md`、`Docs/STEAM_ACHIEVEMENTS.md`、`Docs/ComfyUI_Asset_Pipeline.md`、`Docs/VR_Optimization_Guide.md`，以及 `Source/SpiritsCalling`、`Config`、`Content`、`RawAssets/AI`。`Docs/MVP_Logic_Guide.md` 已標記為過時 Blueprint-only 文件；本需求不得以該文件取代目前 C++ runtime 行為。

本文件是需求階段產物；本階段不要求修改產品程式碼。

## Glossary

- **Spirits_Game**：由 `SpiritsGameMode`、`SpiritsGameState`、`SpiritsPlayerController`、`SpiritsPlayerState` 與相關 C++ 類別組成的遊戲 runtime。
- **Match**：從 `InProgress` 開始至摧毀敵方 Soul Shrine 並進入 `Ended` 的一場對局。
- **Civilization**：`ECivilization` 的四個值：East、Norse、Egypt、Cyber。
- **Civ_Loadout**：某個 Civilization 的三個可召喚 `FMinionArchetype`，包含名稱、生命值、攻擊、距離、間隔、移速、花費、色調與比例。
- **Map_Style**：由 `GSpiritsMapIndex`/`ASpiritsGameState::MapIndex` 選定的程序化競技場樣式；目前包含 Void 與 Sands。
- **Possessed_Unit**：由玩家控制、正在附身中的我方 `AUnitBase`，可執行輕攻擊與重攻擊。
- **PC_Mode**：Windows 平面螢幕模式，包含 RTS 靈魂視角、滑鼠與鍵盤操作。
- **PCVR_Mode**：Windows 上透過 OpenXR 執行的頭戴式 VR 模式，驗證目標包含 Quest Link 與 SteamVR。
- **LAN_Match**：使用 Unreal listen server 與 IP 連線的區域網路對局；本範圍不包含公網配對、專用伺服器或反作弊。
- **Soul_Shrine**：每隊各有一座、被摧毀後決定勝負的 `ASoulShrine` 目標建築。
- **HMD**：Head-Mounted Display，供 OpenXR 偵測與 PCVR_Mode 選擇的頭戴式顯示器。
- **Steam_Client**：在測試或玩家 Windows 機器上執行、提供 Steam identity 與成就服務的 Steam 桌面程式。
- **Steamworks_Integration**：具備正式 Steamworks App ID、`OnlineSubsystemSteam`、OnlineSubsystem 成就 API、Steam_Client 與已建立成就定義的整合。
- **Achievement_ID**：Steamworks 後台與 runtime 必須完全一致的字串 ID。
- **Achievement_Backend**：Steamworks 成就服務；在沒有 Steam_Client 或測試 App 的開發環境中，runtime 可使用本地 fallback log，但 fallback 不得被視為上架驗收通過。
- **Generated_Asset**：由 ComfyUI 產出的 PNG/WAV 等檔案，來源位於 `RawAssets/AI`。
- **Imported_Asset**：已匯入 Unreal Content Browser、具有可驗證匯入設定並可被 cooked package 收錄的 Generated_Asset。
- **Asset_Import_Process**：負責 Generated_Asset 分類、匯入、設定驗證、材質掛接與來源 manifest 的編輯器作業流程。
- **Body_MID**：`AUnitBase` 使用的動態材質實例；文明紋樣與隊色/文明色調須透過此掛點呈現。
- **Arena_Material_Hook**：`ArenaBuilder` 的地面、牆面或天空材質掛點。
- **Unreal_Packaging_Process**：使用 Unreal Editor 或等效自動化命令執行 cook、build、stage、package 與啟動驗證的流程。
- **Shipping_Package**：以 Shipping 組態、IoStore、指定 cook map 產出的可啟動 Windows build，輸出目錄為 `Builds/Windows/`。
- **Smoke_Matrix**：涵蓋三難度單機、LAN 雙機、PCVR 與 30 分鐘穩定性的固定測試矩陣。
- **Release_Readiness_Record**：記錄測試日期、build 版本、結果、log/截圖位置與未通過項目的上架追蹤表。
- **Release_Materials**：商店膠囊圖、截圖、trailer、內容分級、EULA、隱私與 Early Access scope 等對外上架材料。
- **Release_Process**：管理 Release_Readiness_Record、外部上架門檻與最終提交決策的作業流程。

## Requirements

### Requirement 1 — 保存目前已完成的核心玩法

**User Story:** As a player, I want the current playable loop to remain intact, so that launch work does not regress the existing game.

#### Acceptance Criteria

1. WHEN a Match is in the `InProgress` phase, THE Spirits_Game SHALL allow a player to summon units, possess an eligible allied unit, engage opposing units in combat, and resolve the Match by destroying the opposing Soul Shrine, after which the Match SHALL expose either a Victory or Defeat result.
2. THE Spirits_Game SHALL expose exactly three summonable entries for each of the four Civilizations East, Norse, Egypt, and Cyber. For each Civilization, every summonable entry SHALL have configured values for health, attack, range, interval, movement speed, cost, tint, and mesh scale, and every pair of entries SHALL differ in at least one of those values.
3. WHEN a player explicitly requests a summon during an `InProgress` Match, THE Spirits_Game SHALL validate the team loadout, archetype index, Match phase, and Soul cost on the server before spawning the unit.
4. IF any summon request fails validation, THEN THE Spirits_Game SHALL reject the request, spawn no unit, deduct no Soul, and indicate the summon failure to the requesting player.
5. IF a validated summon spawn fails after Soul has been deducted, THEN THE Spirits_Game SHALL restore exactly the deducted amount once, and the requesting player's post-failure Soul balance SHALL equal the balance immediately before the deduction.
6. WHEN a player controls a Possessed_Unit and an attack is accepted under the existing interruption and cooldown rules, THE Spirits_Game SHALL preserve light attack behavior and heavy attack behavior. The heavy attack SHALL use a 0.4-second wind-up, a 0.12-second hit-stop, a 2.2 damage multiplier, and a 2.0 knockback multiplier.
7. WHEN a player selects Easy, Normal, or Hard before a Match begins, THE Spirits_Game SHALL apply that selection before the Match enters `InProgress`, and each pair of difficulty choices SHALL configure at least one different AI pressure or economy parameter.
8. WHEN a single-player Match enters the `InProgress` phase, THE Spirits_Game SHALL initiate the opposing AI wave flow no later than 15 seconds after that transition. IF a human Team B player joins the Match, THEN THE Spirits_Game SHALL not initiate any subsequent opposing AI wave.
9. THE Spirits_Game SHALL apply the existing Souls income and kill reward rules without changing their configured amounts, recipients, or triggering conditions.
10. WHEN the Match phase or winner changes, THE Spirits_Game SHALL replicate the updated Match phase and winner to the connected Match participants without requiring a Match restart or reconnection.
11. WHEN an existing kill-feed or warning-announcement trigger occurs, THE Spirits_Game SHALL expose the corresponding kill feed entry or warning announcement to the player.
12. WHEN a Match reaches its end state, THE Spirits_Game SHALL preserve the existing restart behavior by allowing a participant to request a new Match without relaunching the application.

### Requirement 2 — 保存 PC、PCVR 與 LAN 玩家體驗

**User Story:** 作為目標平台玩家，我希望同一場核心對局可在 PC、PCVR 與 LAN 上使用，讓 Early Access 宣稱的範圍與實際出貨版本一致。

#### Acceptance Criteria

1. WHEN Windows 玩家在未連接 HMD 的情況下啟動 PC_Mode，THE Spirits_Game SHALL 載入 DemoMap 並進入可遊玩的 PC 對局。
2. WHILE PC_Mode 對局進行中，THE Spirits_Game SHALL 透過已發布的 PC 控制配置，讓玩家各完成至少一次 RTS 移動、召喚選擇、召喚放置、附身、輕攻擊、重攻擊、選單開啟與對局重新開始。
3. WHEN Spirits_Game 在對局開始前偵測到透過 Quest Link 或 SteamVR 連接的 OpenXR HMD，THE Spirits_Game SHALL 選取 PCVR_Mode，並讓玩家透過 VR 控制器完成精靈移動、轉向、指向式附身、指向式召喚、召喚類型循環、退出附身與重攻擊各至少一次。
4. WHILE PCVR 選單開啟，THE Spirits_Game SHALL 顯示包含 Play、difficulty、map、civilization、Host LAN、Join IP、Resume 與 Quit 的世界空間選單。
5. WHILE PCVR 選單開啟，THE Spirits_Game SHALL 將右手控制器射線的 hover 與 click 輸入分別作用於被指向的選單項目，並 SHALL 阻止遊戲移動輸入改變玩家位置。
6. WHILE PCVR_Mode 正在移動或執行 snap turn，THE Spirits_Game SHALL 依目前啟用的舒適度設定顯示 comfort vignette，並 SHALL 拒絕距離前一次已接受 snap turn 少於 0.35 秒的後續 snap-turn 輸入。
7. WHEN PCVR_Mode 在指定的支援 PCVR 測試機上執行包含 5 分鐘競技場移動與一個進行中戰鬥波次的測試，THE Spirits_Game SHALL 產生涵蓋完整 5 分鐘的幀率紀錄，且該紀錄的平均渲染幀率 SHALL 至少為每秒 90 幀，並 SHALL 將該紀錄儲存於 Release_Readiness_Record。
8. WHEN 一個 Windows 執行個體以 Host 啟動 LAN_Match，且同一網路上的第二個 Windows 執行個體以 Join IP 加入，THE Spirits_Game SHALL 將兩個執行個體置於同一個 Match，並 SHALL 在每個已完成的下列事件後，讓兩個執行個體顯示一致的隊伍分配、Match 階段、勝者、地圖選擇、文明配置、召喚結果、附身狀態與戰鬥結果：隊伍分配、Match 階段變更、地圖選擇、文明配置、召喚、附身、戰鬥與對局結束。
9. WHEN LAN_Match 的其中一名已連線玩家中斷連線，THE Spirits_Game SHALL 讓剩餘執行個體繼續接受移動與選單輸入，並 SHALL 記錄中斷連線結果。
10. IF LAN_Match 的 Join IP 無法建立連線，THEN THE Spirits_Game SHALL 顯示指出連線失敗的錯誤提示，保留 Host 執行個體可繼續操作的狀態，並 SHALL 不將該對局呈現為已連線或已建立 Match。
11. THE Spirits_Game SHALL 將多人遊戲的出貨範圍描述為僅支援 LAN 與朋友連線，並 SHALL 不將 public matchmaking、dedicated servers、Nakama authentication 或 anti-cheat 呈現為已出貨能力。

### Requirement 3 — 完成 Steamworks 成就正式接線

**User Story:** 作為使用 Steam build 的玩家，我希望成就能解鎖至我的 Steam 帳戶，讓遊戲進度不只停留在本機除錯紀錄。

#### Acceptance Criteria

1. WHEN Steamworks_Integration 已配置為非零數值、非 placeholder 的正式 App ID 或經核准的測試 App ID，THE Spirits_Game SHALL 啟用 `OnlineSubsystemSteam`。
2. WHEN Steamworks_Integration 初始化完成，THE Spirits_Game SHALL 載入 Steam 身分介面與 Steam 成就介面，且目前使用者的 Steam 身分必須可被識別，才可處理 Steam 成就解鎖。
3. WHEN Steamworks_Integration 準備處理目前 Steam 使用者的成就解鎖，THE Steamworks_Integration SHALL 先查詢該使用者的成就定義，再處理任何解鎖寫入。
4. IF 成就定義查詢失敗，或待寫入的 Achievement_ID 不存在於查詢結果，THEN THE Steamworks_Integration SHALL 不發出該 Achievement_ID 的解鎖寫入，並保留本機進度與除錯紀錄。
5. WHEN Steamworks_Integration 註冊成就定義，THE Steamworks_Integration SHALL 僅註冊以下八個、且大小寫完全相同的 Achievement_ID：`ACH_FIRST_WIN`、`ACH_WIN_EASY`、`ACH_WIN_NORMAL`、`ACH_WIN_HARD`、`ACH_POSSESS_KILL_50`、`ACH_SUMMON_100`、`ACH_WIN_ALL_CIVS`、`ACH_LAN_WIN`。
6. WHEN 擁有該事件的玩家贏得一場 Match，THE Spirits_Game SHALL 寫入 `ACH_FIRST_WIN`。
7. WHEN 擁有該事件的玩家以 Easy、Normal 或 Hard 難度贏得一場 Match，THE Spirits_Game SHALL 僅寫入與該難度完全對應的 `ACH_WIN_EASY`、`ACH_WIN_NORMAL` 或 `ACH_WIN_HARD` 其中一個 Achievement_ID。
8. WHEN 擁有該事件的玩家在 LAN_Match 中獲勝，THE Spirits_Game SHALL 寫入 `ACH_LAN_WIN`。
9. IF Match 不是 LAN_Match，THEN THE Spirits_Game SHALL 不寫入 `ACH_LAN_WIN`。
10. WHEN 擁有該 Steam 使用者在已配置的 progress scope 中累計達到 50 次 possession kill，THE Spirits_Game SHALL 寫入 `ACH_POSSESS_KILL_50`，且每個 Steam 使用者最多成功寫入一次。
11. WHEN 擁有該 Steam 使用者在已配置的 progress scope 中累計達到 100 次 summon，THE Spirits_Game SHALL 寫入 `ACH_SUMMON_100`，且每個 Steam 使用者最多成功寫入一次。
12. WHEN 擁有該 Steam 使用者已使用四個 Civilizations 各至少贏得一場 Match，THE Spirits_Game SHALL 寫入 `ACH_WIN_ALL_CIVS`，且每個 Steam 使用者最多成功寫入一次。
13. WHEN 同一 Steam 使用者在同一個 Steam 使用者工作階段重複產生相同 Achievement_ID 的解鎖事件，THE Steamworks_Integration SHALL 僅產生一次該 Achievement_ID 的解鎖寫入要求。
14. IF Steamworks_Integration 無法使用，THEN THE Spirits_Game SHALL 保留本機 fallback logging 與畫面除錯回饋，並 SHALL 不阻擋可遊玩的 PC 或 LAN Match。
15. WHEN Steamworks_Integration 無法使用且開發驗證採用 fallback-compatible development path，THE Spirits_Game SHALL 將該路徑的 Steam 成就驗證標記為通過。
16. WHEN LAN_Match 的解鎖事件由 client 產生，THE Spirits_Game SHALL 將解鎖寫入發送至產生該事件之擁有玩家所對應的 Steam 使用者，且不得寫入任意 server player 的 Steam 使用者。

### Requirement 4 — 匯入並接通生成素材

**User Story:** As a release integrator, I want generated assets imported and visibly connected to runtime hooks, so that the shipped presentation reflects the documented four civilizations and two arenas.

#### Acceptance Criteria

1. THE Asset_Import_Process SHALL preserve the following source files at their exact paths and retain their category mapping: `RawAssets/AI/Civilizations/East/East_pattern.png`, `RawAssets/AI/Civilizations/Norse/Norse_pattern.png`, `RawAssets/AI/Civilizations/Egypt/Egypt_pattern.png`, `RawAssets/AI/Civilizations/Cyber/Cyber_pattern.png` as civilization patterns; `RawAssets/AI/Arenas/Void/Arena_Void_ground.png`, `RawAssets/AI/Arenas/Void/Arena_Void_sky.png`, `RawAssets/AI/Arenas/Sands/Arena_Sands_ground.png`, `RawAssets/AI/Arenas/Sands/Arena_Sands_sky.png` as arena textures; and `RawAssets/AI/Store/Store_capsule_concept.png` as a Steam store draft.
2. WHEN a Generated_Asset is imported, THE Asset_Import_Process SHALL place its runtime texture asset under `Content/Textures` in a civilization or arena subfolder, SHALL map the same source path to the same runtime location on repeated imports, and SHALL retain a manifest entry containing the exact source path for every Imported_Asset.
3. WHEN the four civilization pattern textures have been assigned and validation succeeds, THE Asset_Import_Process SHALL bind `East_pattern.png`, `Norse_pattern.png`, `Egypt_pattern.png`, and `Cyber_pattern.png` to the corresponding East, Norse, Egypt, and Cyber Body_MID or shrine material hook, with no two civilizations resolving to the same pattern texture.
4. WHEN the Void or Sands Map_Style is selected, THE Asset_Import_Process SHALL expose the corresponding ground texture and sky texture through the `Arena_Material_Hook`: Void SHALL resolve `Arena_Void_ground.png` and `Arena_Void_sky.png`, and Sands SHALL resolve `Arena_Sands_ground.png` and `Arena_Sands_sky.png`.
5. WHEN an Imported_Asset is referenced by the PC or PCVR runtime, THE Spirits_Game SHALL load and resolve that asset without a missing-reference error, a black or default-material fallback, or omission from the cooked runtime package.
6. THE Asset_Import_Process SHALL mark a gameplay texture as import-valid only when both its width and height are powers of two and each dimension is no greater than 2048 pixels.
7. WHEN `Store_capsule_concept.png` is imported, THE Asset_Import_Process SHALL keep it outside runtime-cooked gameplay assets and identify it as a Steam store draft until final capsule art, screenshots, and trailer assets have each been approved.
8. IF a Generated_Asset fails import validation, THEN THE Asset_Import_Process SHALL not mark it as successfully imported or runtime-ready and SHALL record its exact source path, a non-empty failure reason, and the affected hook in the `Release_Readiness_Record`; when no hook is assigned, the record SHALL explicitly identify that no hook is assigned.
9. WHEN a scene contains both Team A and Team B after the civilization pattern textures have passed validation, THE Asset_Import_Process SHALL make Team A identifiable by blue and Team B identifiable by red while both teams are simultaneously visible in that scene.
10. WHEN a Void or Sands Map_Style is selected for a LAN session, THE Spirits_Game SHALL replicate the resulting `MapIndex` to every connected LAN client, and every such client SHALL resolve the same selected Map_Style and its corresponding ground and sky textures.
11. WHERE a texture is explicitly documented as a skybox exception, THE Asset_Import_Process SHALL record that exception in the `Release_Readiness_Record` before allowing the texture to exceed the 2048-pixel gameplay-texture limit; textures without that documentation SHALL remain subject to the limit in criterion 6.

### Requirement 5 — 完成 Unreal 打包與啟動驗證

**User Story:** 身為發布負責人，我希望取得可重現的 Shipping package，以便在不依賴 Unreal Editor 的情況下完成測試與提交。

#### Acceptance Criteria

1. WHEN Windows package 產製完成，THE Unreal_Packaging_Process SHALL 使用 Shipping configuration 與 project code build，並將產出放置於 `Builds/Windows/`。
2. WHEN Windows package 產製完成，THE Unreal_Packaging_Process SHALL 啟用 IoStore。
3. WHEN Windows package 產製完成，THE Unreal_Packaging_Process SHALL cook `/Game/Maps/DemoMap`，並納入 Void 與 Sands 兩個 Map_Style variant 的 runtime dependencies 及其 Imported_Asset references。
4. WHEN Shipping_Package 在未安裝 Unreal Editor 的 Windows machine 上啟動，THE Spirits_Game SHALL 在 120 秒內進入 title/menu flow，且 launch log 與畫面不得出現 missing-map、missing-class 或 missing-asset error。
5. WHEN 使用者從 title/menu flow 啟動 PC Match，THE Spirits_Game SHALL 在 120 秒內進入 `InProgress`，且該轉換期間不得出現 missing-map、missing-class 或 missing-asset error。
6. WHEN Shipping_Package 透過 Quest Link 或 SteamVR 搭配 PCVR HMD 啟動，THE Spirits_Game SHALL 在進入可操作流程前選擇 `PCVR_Mode`。
7. WHEN PCVR smoke cases 執行完成，THE Spirits_Game SHALL 使 menu、possession、summon、heavy attack 與 return to spirit form 五個案例各自完成其指定動作、不中斷或產生 missing-map、missing-class 或 missing-asset error，且 Smoke_Matrix SHALL 將五個案例各記錄為 `Pass`。
8. WHEN 同一 LAN 上的兩個 Windows instances 執行 LAN_Match 測試，THE Unreal_Packaging_Process SHALL 在不使用 Unreal Editor 的情況下，使兩個 instances 在連線嘗試後 60 秒內完成 match connection，並使兩個 instances 顯示一致的 replicated match result。
9. WHEN 新的 Shipping_Package 進入接受驗證，THE Release_Readiness_Record SHALL 包含且填有 package version、source revision、cook maps、platform、configuration、IoStore status、package path、launch log 與 Smoke_Matrix results。
10. THE Unreal_Packaging_Process SHALL 保留 project settings 中已配置的 project identity、顯示標題 `Spirits Calling` 與 company name `XiuJiang Studio`，並使 version metadata 在 project settings、menu、HUD 及 end-of-match presentation 中使用同一版本值。
11. IF packaging 或 launch validation 失敗，THEN THE Release_Readiness_Record SHALL 將 package acceptance 狀態設為 blocked，並記錄已執行 validation sequence 中最早發生且可重現的失敗步驟、失敗原因及其 log path。
12. IF packaging 或 launch validation error 未記錄於 Release_Readiness_Record，或其記錄缺少失敗步驟、失敗原因或 log path，THEN THE Release_Readiness_Record SHALL 將 package acceptance 狀態維持為 blocked。

### Requirement 6 — 通過上架硬門檻並保持範圍誠實

**User Story:** 作為發行負責人，我希望記錄所有非程式碼的 Steam 與穩定性上架門檻，以便 Early Access 宣稱由證據支持，而不是僅以存在原始碼作為依據。

#### Acceptance Criteria

1. WHEN 在 accepted `Shipping_Package` 上執行 `Smoke_Matrix`，THE `Release_Readiness_Record` SHALL 在 Easy、Normal、Hard 三種難度各記錄一筆結果；每筆結果 SHALL 在該難度達到勝利或失敗的結束狀態後標記為 pass 或 fail。
2. WHEN 執行一次包含兩個遊戲實例的 `LAN_Match`，THE `Release_Readiness_Record` SHALL 分別記錄 Host、以 IP 加入、summon、possession、combat、victory 及 disconnect 的 pass 或 fail 結果。
3. WHEN 在 accepted `Shipping_Package` 上執行一次 Quest Link PCVR run，THE `Release_Readiness_Record` SHALL 記錄該次執行的 pass 或 fail 結果及其可定位的證據。
4. WHERE SteamVR 相容硬體可用，WHEN 在 accepted `Shipping_Package` 上執行一次 SteamVR PCVR run，THE `Release_Readiness_Record` SHALL 記錄該次執行的 pass 或 fail 結果及其可定位的證據。
5. WHEN 在 accepted `Shipping_Package` 上執行穩定性測試，THE `Spirits_Game` SHALL 連續運行 30 分鐘，且對每次測試輸入或狀態查詢在 5 秒內回應；期間 SHALL 不得發生崩潰，亦不得連續超過 10 秒無法回應。測試結束時的私有工作集相較於第 5 分鐘讀值的增幅 SHALL 不超過 20%，且測試 SHALL 將第 5 分鐘與結束時的讀值、讀值時間、作業系統版本及測試機器的 CPU、GPU、RAM 資訊記錄在 `Release_Readiness_Record` 中。
6. THE `Release_Readiness_Record` SHALL 將 Steamworks 帳號/App ID 核准、商店 capsule art、6–10 張商店截圖、30–60 秒預告片、content-rating questionnaire、EULA/privacy text、Early Access scope text，以及九個 `RawAssets/Audio/*.wav` 的音訊匯入與 `S_Ambient` 循環或已文件化 runtime fallback 驗證，各自列為獨立 gate；每個 gate SHALL 具備非空的 owner、可定位的 evidence path，以及 pass 或 fail 狀態。
7. WHEN `Release_Materials` 發布商店範圍，THE `Release_Materials` SHALL 明確載明 PC single-player、LAN/friend connection 及 PCVR 支援，並明確載明 public matchmaking 不包含在 shipped scope 中。
8. IF 任何 P0 gate 未通過，THEN THE `Release_Readiness_Record` SHALL 將 `Shipping_Package` 標記為 not ready for submission，並保留一筆明確的 unresolved issue；該 issue SHALL 指出未通過的 gate、失敗原因或證據參照，以及目前的 resolution status。
9. WHEN `Release_Readiness_Record` 將 `Shipping_Package` 標記為 ready，THE `Release_Readiness_Record` SHALL 顯示每一個 gate 均已通過，且不得存在 unresolved issue；每一個已通過 gate 的證據 SHALL 仍可被定位與查閱。
10. WHEN final packaging 開始，THE `Release_Process` SHALL 保留針對九個 `RawAssets/Audio/*.wav` 檔案的 documented one-time audio import check，記錄該檢查的 pass 或 fail 結果，並驗證 `S_Ambient` 在 runtime 中循環播放或使用已文件化的 runtime fallback；該驗證結果 SHALL 可在 `Release_Readiness_Record` 的對應 gate 中查閱。

## Correctness Properties and PBT Directions

The following properties are executable test directions. Property tests MAY use isolated C++ helper seams, Unreal automation tests, editor utility tests, or an external manifest harness; they MUST use generated inputs rather than only the named examples.

### Property P1 — Civilization loadout shape, configured values, and distinct entries

For every generated Civilization value in `{East, Norse, Egypt, Cyber}`, `BuildCivLoadout(Civilization)` returns exactly three summonable entries. Every entry has configured health, attack, range, interval, movement speed, cost, tint, and mesh scale values, and every pair of entries within one Civilization differs in at least one of those values.

**Generator:** four Civilization values and random valid archetype indices. **Oracle:** array length, configured-field predicates, and pairwise inequality across the required stat vector.

### Property P2 — Map selection and replication consistency

For every generated integer map selection, the host maps the value into `[0, 1]`, publishes that value as `ASpiritsGameState::MapIndex`, and every simulated client builds the same Map_Style and arena ground/sky hook pair as the host. A LAN join failure leaves the host operable and does not produce a connected Match state.

**Generator:** integers including negative, zero, one, maximum, and out-of-range values; simulated client count 1–4; successful and failed Join IP attempts. **Oracle:** clamped value, identical style/asset mapping on all connected instances, and host/Match state after failed join.

### Property P3 — Server summon validation and economy invariant

For every generated player Soul balance, team loadout, archetype index, Match phase, spawn outcome, and validation outcome, a summon spawns and changes Souls by exactly the archetype cost only when team loadout, index, phase, and balance are valid and spawning succeeds. A validated spawn failure restores the original balance exactly once. Any invalid request rejects the request, spawns no unit, deducts no Soul, and produces a failure indication.

**Generator:** non-negative balances, valid and invalid team loadouts, all phase enum values, indices around `-1`, `0`, `2`, `3`, and random validation/spawn success or failure. **Oracle:** pre/post Soul balance, spawn count, rejection state, and player-facing failure indication.

### Property P4 — Heavy attack timing and multiplier invariant

For every generated positive base damage and knockback vector, a heavy attack accepted under interruption and cooldown rules that reaches its hit time applies damage equal to `base damage × 2.2` and knockback magnitude equal to `base magnitude × 2.0`, while a heavy attack cancelled before 0.4 seconds applies no heavy hit. The heavy hit-stop duration is 0.12 seconds within the engine timer tolerance.

**Generator:** positive damage values, valid target distances, cancellation times below/at/above 0.4 seconds, and interruption/cooldown states. **Oracle:** accepted attack state, damage event, impulse magnitude, and timestamp/timer duration.

### Property P5 — Achievement definition, event semantics, threshold, ownership, and deduplication invariant

For every generated event sequence containing wins, difficulty values, civilization values, LAN flags, summon events, possession-kill events, repeated events, Steam identity availability, achievement-definition query results, and fallback availability, every emitted ID belongs to the exact eight-ID set. A win emits `ACH_FIRST_WIN` and exactly one matching difficulty ID; `ACH_LAN_WIN` is emitted only for LAN wins; threshold achievements appear when and only when their configured thresholds are crossed; every ID is written at most once per user session; and a client-generated LAN event writes only to the owning Steam user. Failed definition queries or unknown IDs produce no Steam unlock write while retaining fallback records. The fallback-compatible development path may mark development verification as passed without implying Steamworks release acceptance.

**Generator:** random bounded event sequences with duplicate events, out-of-range difficulty/civilization values, local/remote player ownership, identity and definition query success/failure, and fallback-compatible development paths. **Oracle:** exact emitted-ID set, one difficulty ID per qualifying win, LAN condition, threshold crossing, backend user ID, per-ID write count ≤ 1, and fallback record when Steam is unavailable.

### Property P6 — Generated-asset manifest, hook, validation, and cook classification

For every required Generated_Asset manifest entry, exactly one Imported_Asset path, category, exact source path, and runtime hook exists where a hook is required; civilization patterns resolve to their matching civilization Body_MID or shrine hook without duplicate pattern textures; Void and Sands each resolve their matching ground and sky pair; all gameplay textures satisfy power-of-two dimensions and the 2048-pixel limit unless marked as the documented skybox exception; invalid entries are not runtime-ready and record a non-empty failure reason plus the affected hook or explicit no-hook value; and the store-only asset is absent from the runtime cook set.

**Generator:** required asset manifest plus injected missing, duplicate, wrong-category, wrong-source-path, wrong-hook, non-power-of-two, over-size, undocumented-skybox-exception, invalid, and store/runtime classification mutations. **Oracle:** validator rejects every injected mutation and accepts the canonical exact-path manifest.

### Property P7 — LAN replicated match and remaining-client liveness invariant

For every generated valid host/client sequence of menu selections and gameplay commands, all connected clients converge on the host's team assignment, difficulty, Map_Style, Civilization loadout selection, Match phase, winner, accepted summon, possession, and combat outcomes after each specified event. A disconnected client is removed from active replication without preventing the remaining client from accepting movement and menu input or reaching `Ended`; a failed Join IP leaves the host operable and does not claim a connected Match.

**Generator:** two-player command sequences with delayed/reordered non-authoritative requests, one optional disconnect point, and successful or failed Join IP attempts. **Oracle:** authoritative host state, event-by-event replicated state, client connection state, remaining-client liveness, and failed-join presentation.

### Property P8 — Platform interaction and release-scope invariant

For every generated PC and PCVR input sequence, PC_Mode exposes the documented movement, summon, possession, combat, menu, and restart actions; PCVR_Mode exposes spirit movement, turn, pointed possession/summoning, summon cycling, return from possession, and heavy attack; while the PCVR menu is open, right-controller hover/click targets menu items and movement input does not move the player; snap turns are rejected when less than 0.35 seconds apart; and the published multiplayer scope contains LAN/friend connection but not public matchmaking, dedicated servers, Nakama authentication, or anti-cheat.

**Generator:** generated PC/VR action sequences, menu-open states, snap-turn timestamps, and multiplayer capability declarations. **Oracle:** action completion, menu routing, player transform stability, snap-turn acceptance interval, and scope declaration.

### Property P9 — Packaging manifest closure and acceptance-record invariant

For every accepted Windows package manifest, the package uses Shipping configuration, project code build, IoStore, output path `Builds/Windows/`, and cooks `/Game/Maps/DemoMap` with both Map_Style variants and their Imported_Asset references. Every cooked runtime reference reachable from the DemoMap, PCVR menu, achievements fallback, and audio fallback resolves to a packaged object; no required runtime object is editor-only; and store-only assets are absent. A valid acceptance record contains package version, source revision, cook maps, platform, configuration, IoStore status, package path, launch log, and Smoke_Matrix results. A packaging or launch failure blocks acceptance and records the earliest reproducible step, reason, and log path; a ready record has no unresolved issue.

**Generator:** package manifests and acceptance records with missing, duplicate, editor-only, store-only, wrong-configuration, disabled-IoStore, missing-map, incomplete-record, and malformed-failure entries. **Oracle:** closure checker reports all missing runtime references; package and record validators reject every invalid manifest, block incomplete failure records, and accept only complete ready records.

## Known Uncertainties and Assumptions

- The repository is currently configured for Unreal Engine `5.8`, while `BUILD_AND_PLAY.md` lists UE `5.7`; the accepted engine version and matching toolchain must be fixed before the final Shipping_Package is validated.
- `Config/DefaultGame.ini` currently cooks `/Game/Maps/DemoMap`; the second arena is implemented as a runtime `Map_Style` inside the same map, not as a separately observed `.umap` in the current tree. The packaging requirement therefore treats Void/Sands as two runtime variants unless a separate `.umap` is deliberately added later.
- The repository currently has no official Steamworks App ID in the inspected configuration. `SteamDevAppId=480` is documented as a development placeholder only; Steamworks acceptance cannot pass until the approved App ID, backend definitions, test accounts, and legal/store materials are supplied.
- The existing achievement implementation documents `QueryAchievements` and `WriteSteamAchievement`, but the inspected `SpiritsAchievements.cpp` currently compiles only the local fallback path. Formal API compatibility and callback/error behavior must be verified against the selected UE 5.8 OnlineSubsystemSteam integration.
- The generated asset folders contain one pattern PNG per Civilization, one ground PNG and one sky PNG per Map_Style, and one store concept image. The requirement does not assume separate base-color and emissive files until the asset manifest confirms them.
- The current project contains a `3DWidget` collision channel and uses Visibility for the VR menu widget interaction; PCVR hardware validation must confirm that this configuration works on both Quest Link and SteamVR.
- The exact acceptable memory-growth measurement method and the final build machine profile are not specified in the source documents; this spec fixes a provisional 20 percent private-working-set threshold so the stability gate is measurable and reviewable.
