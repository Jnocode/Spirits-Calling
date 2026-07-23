# VFX 尾巴:影片工作流 → Sprite Sheet(接在你現有工作流後面)

> 你 ComfyUI 已有能跑的影片工作流(LTX2.3 / Wan2.2 I2V / SVI)與所有需要的節點。
> 不用重寫整條——只在**產生影格的那條 IMAGE 線**後面接三個節點,就能吐出 UE 可用的 sprite sheet。

## 一次性效果(光刃 / 召喚爆發 / 命中火花)

用你的 **Wan2.2_I2V_Grok_Vision** 或 **LTX2.3** 工作流,把黑底關鍵影格(`RawAssets/AI/VFX/keyframes/*.png`,用 `LoadImage` 載入)轉成影片。找到它輸出**影格批次(IMAGE)**、原本接去 `VHS_VideoCombine` 的那條線,額外接:

```
[影格批次 IMAGE]
   ├─→ VHS_VideoCombine        (可留著,方便你預覽 gif)
   └─→ VHS_SelectEveryNthImage (select_every_nth = 總幀數 / 16,例如 81 幀就填 5 → 約16幀)
          └─→ ImageGrid        (columns = 4  → 產生 4×N 方格)
                 └─→ SaveImage (filename_prefix = "vfx_slash_light_sheet")
```

- 目標約 **16 幀 → 4×4**(或 25 幀→5×5)。`VHS_SelectEveryNthImage` 用來把影片模型輸出的幀數降到剛好。
- `ImageGrid` 的 `columns` 設 4(16 幀)或 5(25 幀);它會把批次排成一張大圖。
- 輸出到 ComfyUI 的 output 目錄;複製到 `RawAssets/AI/VFX/sheets/`。

## 循環效果(靈魂光環 / 聖壇光柱)

要真無縫循環,用 **`WanFirstLastFrameToVideo`**:把 **first_frame 和 last_frame 設成同一張**(你的黑底關鍵影格),模型會生出「頭尾接得起來」的一段 → 抽幀後循環播放不跳。之後一樣接 `VHS_SelectEveryNthImage → ImageGrid → SaveImage`。

> 沒有 first/last 節點時的備援:正常生一段 → 用 `ImageBatch` 把「正播 + 倒播」接起來做 ping-pong,再拼圖。

## 幀數 / 格數對照(給 UE SubUV 用)

| 幀數 | ImageGrid columns | UE SubImages | 適合 |
|---|---|---|---|
| 16 | 4 | (4,4) | 快、檔案小,大多數效果夠用 |
| 25 | 5 | (5,5) | 較滑順的循環(光環/光柱) |
| 36 | 6 | (6,6) | 高品質關鍵特效 |

## UE 端(匯入 → Niagara)

1. sprite sheet PNG 拖進 `Content/VFX/Textures`(壓縮設 `UserInterface2D` 或關 sRGB 視情況;additive 發光圖建議關 sRGB 讓亮度線性)。
2. Niagara:Sprite Renderer + **Sub UV** 模組,`Sub Image Size = (4,4)`;用 `SubUVAnimation` 模組推進格數(loop 或 once)。
3. Blend Mode = **Additive**;顏色乘上隊色/文明色(`SpiritsTeams::GetTeamColor`)。
4. 把 C++ 的 `FXFlash` 佔位換成生成 VFX 的 Niagara 系統;或先把 flipbook 材質貼在既有 QuarterCylinder 上當攻擊光刃(最省)。

## 建議先做一顆驗證

1. 生 `slash_light` 關鍵影格(`_run_vfx_keyframes.bat`,若還沒生)。
2. 用 Wan I2V / LTX 把它轉影片 + 接上面尾巴 → 得到 `vfx_slash_light_sheet.png`。
3. 拖進 UE、做一個最小 Niagara SubUV(4×4、additive)貼在攻擊位置。
4. 對了再把其餘 5 個效果照抄。

> 你把任一條影片工作流的**節點圖截圖**給我(尤其影格 IMAGE 輸出到 VideoCombine 那段),我可以直接標「這條線接到這三個節點、參數填多少」,或幫你把接好尾巴的完整工作流存成 JSON。
