# Requirements Document — Spirits Calling Redesign (v2)

## Introduction

本文件定義 **Spirits Calling** 從「兩隊互K RTS」pivot 為「**弱靈魂潛行探索 → 攢心靈 → 附身/義體 → roguelite 求生**」的需求基線。pivot 根因：專案負責人親自試玩打包版判定「很無聊」——沒有成長弧線、附身無回報、沒有決策與張力。

本需求以今晚（2026-07-24）設計會談收斂的**五根設計柱**為準（見 `design.md`）：節奏脊椎（反向縮圈）、核心動詞（魂體⇄義體）、核心資源（心靈）、召喚重生（義體庫存）、社交地基（Nakama）。

**重要 — 數據誠信**：本需求只把**已談定的設計方向**寫成可驗收約束；今晚未談定的具體數值（心靈門檻、技能數、義體耗損、擴張時序等）列為 §Open Design Decisions，**不在本文件憑空發明**。P0 設計鎖定階段由 Jun 拍板後，才把它們補成可測 EARS 準則。

本需求也承接前一輪已建置且保留重用的基礎設施（見 `design.md` §5）：`ASpiritPawn/ASpiritVRPawn`、`AUnitBase` 附身戰鬥、Match FSM、`AArenaBuilder`、四文明系統、`Backend/Nakama` scaffold、`build_shipping.ps1` 打包/驗證鏈。

## Glossary

- **Soul_Form（魂體）**：玩家初始且死亡後回歸的脆弱靈魂狀態；可探索、穿過迷霧、吸收心靈，但無法直接高強度戰鬥，且會被危險地帶與敵靈「擊散」。
- **Vessel（義體）**：玩家透過心靈門檻附身的軀殼（雜兵/精英英雄/中立守衛/終局級）；安全且強大、能戰鬥，但不成長且會耗損，是消耗性資源。
- **Psyche（心靈）**：核心資源，靠探索累積，決定可附身的義體階級。
- **Possession_Threshold（附身門檻）**：附身某階級義體所需的最低心靈值。
- **Danger_Zone（危險地帶）**：會消滅裸奔魂體的區域；隨 run 進程從無 → 出現 → 擴張 → 吞沒全圖。
- **Run**：一場從安全探索到終局窒息的完整遊玩，具起承轉合，死亡/終局結束後可再開一場。
- **Spirit_Vision（靈視）**：四文明各自的靈界視覺覆蓋層，在同一張地圖揭示不同隱藏內容。
- **Spirit_Fog（靈界迷霧）**：遮蔽資訊的戰爭迷霧；附身單位可獲得其視野。
- **Vessel_Inventory（義體庫存）**：玩家事先準備、待命的義體（重定義後的「召喚」）。
- **Nakama_Backend**：開源自架遊戲後端，提供帳號、排行榜、好友、聊天、錦標賽、線上多人、購買驗證。
- **Bartle_Coverage**：四象限（成就者/探索者/社交者/殺手）皆被服務、不偏科的設計約束。

## Requirements

> 註記：以下準則中，**[DECIDED]** = 今晚談定的方向性約束（可直接驗收）；**[TBD]** = 依賴 §Open Design Decisions 的數值，鎖定後補完。

### Requirement 1 — 成長弧線與核心資源（心靈）

**User Story:** 作為 roguelite 玩家，我要一條「開場脆弱 → 探索變強 → 附身翻盤」的弧線，讓每一場都有從弱到強的過程。

#### Acceptance Criteria

1. [DECIDED] WHEN 一場 Run 開始，THE Game SHALL 讓玩家處於 Soul_Form，且**不得**在開場即提供高階附身或直接召喚戰鬥單位的能力。
2. [DECIDED] THE Game SHALL 以 Psyche 作為單一核心成長資源，且 Psyche SHALL 只能透過探索行為（吸收靈脈/發現秘密/淨化封印/擊散敵靈等）累積，不得靠被動時間流逝白給。
3. [DECIDED] WHEN 玩家的 Psyche 未達某義體階級的 Possession_Threshold，THE Game SHALL 拒絕附身該階級義體並向玩家明確指示原因。
4. [DECIDED] THE Game SHALL 提供至少兩個由 Psyche 區分的附身階級（低階脆弱 → 高階強大），且高階義體的戰鬥能力 SHALL 明顯高於低階。
5. [TBD] 各 Possession_Threshold 的具體數值、階級數量 SHALL 依 §Open Design Decisions 鎖定後定義並可測。

### Requirement 2 — 節奏脊椎（反向縮圈）

**User Story:** 作為玩家，我要一場有「悠閒 → 壓力 → 窒息」節奏的 Run，讓前期能學習、後期有腎上腺素。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 以空間化的 Danger_Zone 推進取代純數字計時器：Run SHALL 經歷 安全（無 Danger_Zone）→ Danger_Zone 出現 → 擴張 → 終局（Danger_Zone 吞沒全圖）四個階段。
2. [DECIDED] WHILE 玩家的 Soul_Form 位於 Danger_Zone 內，THE Game SHALL 施加會消滅魂體的威脅（損失 Psyche 或結束 Run）。
3. [DECIDED] WHILE Run 處於安全階段，THE Game SHALL 允許玩家無威脅地自由探索與學習操作（環境式教學，取代缺席的新手引導）。
4. [DECIDED] WHEN Run 進入終局階段，THE Game SHALL 使裸奔的 Soul_Form 無法在全圖 Danger_Zone 中長時間存活，令附身/義體成為生存剛需而非可選增益。
5. [TBD] Danger_Zone 出現時間、擴張速率、Run 總長 SHALL 依 §Open Design Decisions 鎖定。

### Requirement 3 — 魂體 ⇄ 義體 推幣式抉擇（核心動詞）

**User Story:** 作為玩家，我要在「出魂冒險成長」與「縮進義體保命」之間反覆賭命，讓每一刻都有抉擇。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 讓玩家在 Soul_Form（可成長、脆弱）與 Vessel（保命、強大、消耗、不成長）之間主動切換。
2. [DECIDED] WHILE 玩家處於 Vessel，THE Game SHALL 不允許 Psyche 透過探索繼續成長（保命與成長互斥，逼出抉擇）。
3. [DECIDED] THE Vessel SHALL 是消耗性資源（會耗損/有限），使「撤回義體」是有代價的承諾而非無限苟命。
4. [DECIDED] WHEN 玩家的 Vessel 被摧毀或耗盡，THE Game SHALL 使玩家回到 Soul_Form 並繼續 Run（死亡=轉場，不是立即 game over），直到 Soul_Form 亦被消滅才結束 Run。
5. [TBD] Vessel 耗損模型、撤回/再出魂成本 SHALL 依 §Open Design Decisions 鎖定。

### Requirement 4 — 召喚重生為義體庫存

**User Story:** 作為玩家，我要「召喚」是準備救命義體的資源管理，而不是無腦生兵互K。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 將召喚重定義為準備 Vessel_Inventory（事先備妥、待命的義體），而非在場上直接生成自動互K的戰鬥單位。
2. [DECIDED] THE Game SHALL 不在 Run 開場即開放召喚/義體準備；該能力 SHALL 由 Psyche 成長解鎖。
3. [DECIDED] WHEN 危險逼近，THE Game SHALL 允許玩家撤回至事先備妥的 Vessel 作為救命手段。

### Requirement 5 — 探索即附身（雙層地圖）

**User Story:** 作為探索者，我要探索深度長在「附身」這個獨門動詞上，而不是又一個通用道具系統。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 提供靈魂層（探索：無形穿越 Spirit_Fog、看見靈界物件）與物理層（戰鬥：附身後實體化）的雙層體驗，並以附身/死亡作為兩層之間的轉場。
2. [DECIDED] THE Game SHALL 允許玩家附身「多種對象」而非僅自方單位（至少涵蓋：一般義體、以及一種以上的地圖特殊附身目標，如中立守衛或地形物件）。
3. [DECIDED] WHEN 玩家附身一個具視野的對象，THE Game SHALL 將該對象的視野提供給玩家（資訊即資源：附身同時是戰鬥與偵察決策）。
4. [DECIDED] THE Game SHALL 以四文明各自的 Spirit_Vision 在同一張地圖揭示不同的隱藏內容，使同圖以不同文明重玩具有不同探索價值。
5. [TBD] 各文明 Spirit_Vision 的具體隱藏內容、可附身特殊目標清單 SHALL 依 §Open Design Decisions 鎖定。

### Requirement 6 — 四象限融合（不偏科）

**User Story:** 作為一個成熟產品，它不能偏科——成就者、探索者、社交者、殺手都要被服務。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 以「單一核心循環（魂體探索→攢心靈→附身義體→翻盤→死回魂體）」同時服務四個 Bartle 象限，而非為單一象限硬做設計。
2. [DECIDED] THE Game SHALL 服務成就者：Psyche 成長、難度階、四文明精通、排行榜等可量化進度。
3. [DECIDED] THE Game SHALL 服務探索者：附身萬物、四文明靈視、build 組合等結構性探索（探索是生存必要，非外接可選系統）。
4. [DECIDED] THE Game SHALL 服務殺手：對 AI 兵潮的 1打多碾壓支配感；並以 Nakama 提供真線上 PvP（EA 期間逐步長，非 v1 首發門檻）。
5. [DECIDED] THE Game SHALL 服務社交者：以 Nakama 提供帳號/排行榜/好友/聊天/錦標賽，並使每場 Run 產出可炫耀/可分享的內容（build、翻盤、破紀錄）以餵外部社群傳播。
6. [DECIDED] THE Game SHALL NOT 以「遊戲內從零自刻的社交基建」或「深度 RTS」服務任一象限（scope 紀律，見 §Non-Goals）。

### Requirement 7 — 社交地基（Nakama）

**User Story:** 作為發行者，基礎的社交/競技功能要有，且用開源自架、零授權費。

#### Acceptance Criteria

1. [DECIDED] THE Game SHALL 以 Nakama_Backend（開源、可自架）提供帳號、排行榜、好友、聊天、錦標賽、線上多人與購買驗證的基礎能力，採「接現成」而非「自刻」。
2. [DECIDED] THE Nakama 整合 SHALL 先交付 day-1 骨架（帳號 + 排行榜 + build 分享），其餘（好友/聊天/錦標賽/線上 PvP）SHALL 於 EA 期間逐步啟用。
3. [DECIDED] THE Game SHALL 只在核心循環已證明可玩後才擴充社交深度（避免空排行榜/無人社交層）。
4. [DECIDED] THE 出貨 scope 文字 SHALL 誠實呈現線上能力的實際狀態，不得把未完成的 public matchmaking/線上 PvP 呈現為已出貨。

### Requirement 8 — 重用既有基礎設施

**User Story:** 作為專案負責人，前一輪工程（引擎/打包/後端 scaffold 全綠）不能白做。

#### Acceptance Criteria

1. [DECIDED] THE Redesign SHALL 重用既有 `ASpiritPawn/ASpiritVRPawn`（魂體 pawn）、`AUnitBase`（義體戰鬥基底）、Match FSM（run 階段推進）、`AArenaBuilder`（可探索地圖 + Danger_Zone 承載面）、四文明系統（靈視/義體風格）、`Backend/Nakama` scaffold 與 `build_shipping.ps1` 打包/驗證鏈。
2. [DECIDED] THE Redesign SHALL NOT 廢棄前一輪已驗證全綠的 packaging/closure/audio gate 驗證鏈，而是沿用其為發布驗證基礎。
3. [DECIDED] 舊 spec `spirits-calling-requirements` SHALL 保留為基礎設施歷史紀錄，不被本 spec 覆寫刪除。

## Open Design Decisions（P0 設計鎖定，Jun 拍板前不得憑空發明）

1. **心靈門檻數值 + 附身階級數量**（Req 1.5）
2. **義體耗損模型 + 撤回/再出魂成本**（Req 3.5）
3. **Run 長度 + Danger_Zone 出現/擴張時序**（Req 2.5）
4. **每英雄技能數量**（會談曾提 3：位移/AOE/大招，未確認）
5. **roguelite 天賦形式**（附身三選一 / 場中升級 / 開局配裝；曾傾向前者，未確認）
6. **RTS 層去留程度**（「召喚=義體庫存」已隱含 RTS-light；深度 RTS 明確排除）
7. **終局反挫折護欄**（義體可管理、消滅前有警訊/逃生窗口、心靈可淨化小塊危險區；**死亡永遠是玩家賭輸而非地圖宣判**——終局生死線）
8. **四文明靈視各揭示什麼 + 可附身特殊目標清單**（Req 5.5）

## Non-Goals

- 深度 RTS（經濟/兵種搭配/推線）——單人開發 scope 陷阱，排除。
- 遊戲內從零自刻的社交基建（公會/房屋/即時聊天 UI）——用 Nakama 接。
- 線上即時 PvP 作為 v1 首發必需——列 EA 逐步長。
- 以「遊戲內社交系統」服務社交者——本作靠「可傳播/可炫耀」+ Nakama 服務。

## Known Assumptions

- 引擎鎖定 UE `5.8`（`.uproject` EngineAssociation=5.8）；舊文件殘留 5.7 已於前一輪修正。
- Nakama 自架於既有 Synology NAS（Docker + Postgres），符合零預算/local-first 原則。
- 本 spec 為 game-design pivot 的**設計階段**產物；P0 設計鎖定完成前不進行大規模實作。
