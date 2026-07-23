# 動態特效產線 — 影片模型(LTX / Wan)→ Sprite Sheet → UE Niagara

> 目標:把靜態除錯線特效換成 AI 生成的動態 VFX(攻擊光刃、靈魂光環、召喚爆發、聖壇光柱、命中火花)。
> 路線:**ComfyUI 內建影片模型(LTX-2.3 或 Wan 2.2)生短片 → 抽幀 → 組 sprite sheet → UE Niagara SubUV 播放**。

## 為什麼用影片模型,不用 AnimateDiff

AnimateDiff(2023)是舊法;你 ComfyUI 範本裡已內建 **LTX-2.3**、**Wan 2.2** 這類 2025–26 影片擴散模型,運動一致性、細節、時長都明顯更好,而且**免裝額外節點**。遊戲即時 VFX 仍需要**貼圖**(不能播影片),所以差別只在「上游用更好的生成器」,下游一樣抽幀烘成 sprite sheet。

## 最佳組合:靜圖打底 → 影像轉影片

我們已有的 SDXL 靜圖產線正好拿來當**關鍵影格**:

1. 用 SDXL(現有 `comfyui_generate.py`)生一張**純黑底的特效關鍵影格**(如一道能量光刃)。
2. 丟進 **LTX-2.3 圖像轉影片** 或 **Wan 2.2 14B 影像到影片**,讓它動起來——好處是黑底與造型由靜圖鎖定,動畫不亂跑。
3. 抽幀 → sprite sheet → UE。

> 也可直接用 **Wan 2.2 文字轉影片** 純文字生成,但 image-to-video 對「黑底、可疊加」的控制更穩。

### 模型選擇(依你的 GPU)

- **LTX-2.3**:輕、快,VRAM 友善 → **建議先用這個**(你機器生 SDXL 已偏吃緊,LTX 最不會卡)。
- **Wan 2.2 14B**:品質更高但 14B 很重,可能很慢或 OOM;若 LTX 品質夠就不必動它。有 Wan 2.2 5B 較輕的版本可折衷。

## 循環 vs 一次性

- **一次性效果**(攻擊光刃、召喚爆發、命中火花):播一次就好,影片模型天生適合,不需無縫循環。
- **持續效果**(靈魂光環、聖壇光柱):需要循環 → 用 **ping-pong**(正播+倒播接成一張 sprite sheet)偽裝無縫,或用首尾同影格的技巧。

## Spirits Calling 的 VFX 拍攝清單(建議優先序)

| VFX | 關鍵影格提示詞方向 | 類型 | 混合 | 對應現有掛點 |
|---|---|---|---|---|
| 攻擊光刃(輕/重) | crescent energy slash, pure black bg | 一次性 | additive | `Multicast_AttackFX / HeavyFX` 的 QuarterCylinder |
| 召喚爆發 | burst of rising light particles, black bg | 一次性 | additive | `AUnitBase::BeginPlay` summon flash |
| 命中火花 | small bright impact spark, black bg | 一次性 | additive | 命中 FX |
| 靈魂光環 | swirling ethereal aura ring, soft glow | 循環(ping-pong) | additive | BaseRing / GlowLight 疊層 |
| 聖壇光柱 | vertical light pillar with embers | 循環(ping-pong) | additive | 聖壇受擊/陷落 |

全部 **512×512、純黑底**;每效果一張 sprite sheet(如 16 幀 4×4 或 25 幀 5×5)。

## 流程(ComfyUI 端)

```
[SDXL 靜圖]  effect keyframe (black bg)   →  儲存到 RawAssets/AI/VFX/keyframes/
      │
      ▼
[LTX-2.3 / Wan 2.2  image-to-video]  →  N 幀短片
      │
      ▼
[抽幀 + (可選 ping-pong) + Grid 拼圖節點]  →  sprite sheet PNG  →  RawAssets/AI/VFX/<name>_sheet.png
```

- 抽幀:影片模型輸出常是 N 幀影像批次,取每隔幾幀降到 16/25 幀。
- 拼 sprite sheet:用 ComfyUI 的 image grid / SpriteSheetMaker 節點,或 ffmpeg。
- 我的 `comfyui_generate.py` 可加 `--mode vfx`:讀 VFX 提示詞表 → 生關鍵影格(SDXL)→ 之後手動或用工作流接影片模型。

## UE 端(匯入 → Niagara)

1. sprite sheet PNG 拖進 `Content/VFX/Textures`。
2. 材質:Sub UV / Flipbook 節點,`SubImages=(4,4)` 或 `(5,5)`;Niagara SubUVAnimation 模組推進格數。
3. Niagara:Sprite Renderer + SubUV 模組,Blend = **Additive**;染色接現有隊色/文明色(`SpiritsTeams::GetTeamColor`)。
4. 把 `FXFlash` 佔位換成 Niagara 系統,或先把 flipbook 材質貼在既有 QuarterCylinder 上(最省)。

## 我可以接著做的

- **A**:寫 `comfyui_generate.py --mode vfx` + 5 個特效的**黑底關鍵影格提示詞表**(先把靜圖打底自動化,你再接 LTX 影片模板)。
- **B**:等你在 ComfyUI 開好 LTX-2.3 image-to-video 範本,我對著它的節點給你**串接關鍵影格 + 抽幀 + sprite sheet 的工作流 JSON**。
- **C**:UE 端 sprite sheet → Niagara 的逐步編輯器指引。

## 來源

- ComfyUI 內建影片範本:LTX-2.3(圖像轉影片)、Wan 2.2 14B(影像到影片 / 文字轉影片)。
- [comfy.org — Sprite Sheet 模板](https://comfy.org/workflows/templates-sprite_sheet-fe5600667e2c/)
- [StraySpark — ComfyUI 遊戲素材產線 2026](https://www.strayspark.studio/blog/comfyui-game-asset-pipeline-indie-2026)
