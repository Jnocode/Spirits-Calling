# 把 sprite sheet 接成 Niagara 特效(UE 端逐步)

> C++ 已接好:輕攻擊 spawn `/Game/VFX/NS_SlashLight`、重攻擊 spawn `/Game/VFX/NS_SlashHeavy`,並用隊色設它們的 `Color` 使用者參數。空值保護:資產沒建好也照跑(只是沒特效)。
> 你只要在編輯器按下面把資產建好、命名一致、放對路徑,遊戲裡攻擊就會自動播。

## 0. 先重編譯(加了 Niagara 模組)

雙擊 `_build_s2s3.bat`,確認 `Result: Succeeded`。(已把 Niagara 外掛加進 `.uproject`、`Build.cs` 加了 `"Niagara"` 模組。)

## 1. 匯入 sprite sheet

- 把 `RawAssets/AI/VFX/sheets/slash_light_sheet.png` 拖進 `Content/VFX/Textures/`。
- 雙擊貼圖:**Compression 設 `UserInterface2D (RGBA)`**、**取消勾選 sRGB**(加成發光要線性亮度)。

## 2. 建 flipbook 材質

- `Content/VFX/` 右鍵 → Material,命名 `M_SlashFlipbook`。
- Material 設定:**Blend Mode = Additive**、**Shading Model = Unlit**。
- 節點:
  - `Texture Sample`(那張 sprite sheet)。
  - **SubUV / Flipbook**:用 `Particle SubUV` 節點(粒子系統會餵 UV),或用 Material 的 `Flipbook` 節點,`Frames X=4, Frames Y=4`。把 SubUV 的 UV 接到 Texture Sample 的 UV。
  - 加一個 **Vector Parameter `Color`**(給 C++ 染隊色),乘到貼圖 RGB。
  - 結果接 **Emissive Color**;貼圖的亮度(或 R 通道)可當 **Opacity**(additive 下等於發光強度)。

## 3. 建 Niagara 系統(命名很重要)

- `Content/VFX/` 右鍵 → FX → Niagara System → 選 **Fountain** 或空模板 → 命名 **`NS_SlashLight`**(要跟 C++ 一致)。
- Emitter 設定:
  - **Sprite Renderer** → Material 選 `M_SlashFlipbook`;開 **Sub UV**,`Sub Image Size = (4, 4)`。
  - **Sub UV Animation** 模組:模式 Linear,0 → 16(整段),播放一次。
  - Spawn:改成 **Spawn Burst Instantaneous**(1 顆),關掉持續 spawn。
  - Lifetime ~0.28s(配合輕攻擊節奏);Size 依需要(如 120)。
  - 加一個 **User Parameter**:型別 LinearColor、命名 **`Color`**(C++ 用 `SetVariableLinearColor("Color")` 染色);在 Sprite Renderer 或 Color 模組把它乘進去。
- 存到 `Content/VFX/NS_SlashLight`。

## 4. 重攻擊版

- 複製 `NS_SlashLight` → 命名 **`NS_SlashHeavy`**,材質換成 `slash_heavy_sheet` 的版本(生成後同樣流程),Lifetime 拉長一點、Size 大一點。C++ 重攻擊會用 1.6 倍 scale spawn 它。

## 5. 測試

- PIE 進遊戲,附身一個單位左鍵攻擊 → 應該在身前播出 sprite sheet 動畫、顏色是隊色。
- 沒看到?檢查:資產路徑/命名是否為 `/Game/VFX/NS_SlashLight`、材質是否 Additive+SubUV(4,4)、Niagara 是否 Burst 1 顆且 Lifetime>0。

## 之後

- 對了就照同法把 `summon_burst`、`impact_spark` 做成 Niagara,掛到 `BeginPlay` 召喚點與命中點(我可以再幫你在 C++ 加對應 spawn)。
- 循環類(`spirit_aura`/`shrine_pillar`)用 `--pingpong` 版 sprite sheet,SubUV 設 Loop。
