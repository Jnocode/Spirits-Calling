# ComfyUI 生成式素材產線

> 對接 v0.9→v1.0 計畫「線 5」。目標:用本機 ComfyUI 批次產生四文明紋樣、兩地圖地面/天空、商店主圖,匯入 UE 後餵進現有動態材質(MID)。

## 一鍵生成

前置:本機已啟動 ComfyUI(`python main.py`,預設 `http://127.0.0.1:8188`),且 `models/checkpoints/` 內有一個 SDXL 類 checkpoint。

```bash
cd Spirits_Calling/Scripts/AI

python comfyui_generate.py --list                 # 看會產哪些檔
python comfyui_generate.py --dry-run              # 只印佇列,不生成
python comfyui_generate.py --checkpoint <你的.safetensors>          # 全部生成
python comfyui_generate.py --checkpoint <...> --only East_pattern,Cyber_pattern
```

輸出落點:`RawAssets/AI/<category>/<name>.png`(script 自動建資料夾)。
提示詞與尺寸集中在 `prompts_civilizations.json`,可直接改。

## 設計原則:讓引擎上色,不要在貼圖上色

單位/聖壇的顏色在引擎裡是「隊色(藍/紅)× 文明色調 × 單位亮度」相乘算出來的(見 `SpiritsCiv::GetHue` 與 `AUnitBase::ApplyVisuals`)。所以生成的**紋樣貼圖請偏中性/灰階**,把文明識別放在「圖案本身」(雲雷紋 / 盧恩 / 象形 / 電路),顏色交給引擎——這樣藍紅隊在 LAN 仍然分得清。

## 匯入與掛點(在 UE 編輯器)

1. 把 `RawAssets/AI/…` 的 PNG 拖進 `Content/Textures/<分類>`。
2. 文明紋樣:做一個 Emissive/Detail 材質參數(例如 `PatternTex`),接到單位 Body 材質;`ApplyVisuals` 時依單位所屬文明選對應貼圖(下一輪 S 會把 `ECivilization` 存進 `FMinionArchetype` 一起傳)。
3. 地面/天空:餵進 `AArenaBuilder` 的地板材質與 sky material(對接線 1A 的 `FArenaStyle`)。
4. 商店主圖 `Store_capsule_concept.png`:當 Steam 首圖草稿/截圖底(SHIP_CHECKLIST 標記為最值得外包精修的一項)。

## 注意

- 腳本只跟本機 ComfyUI API 溝通,不抓網路素材。
- `seamless tileable` 靠提示詞達到約九成;要完全無縫可在 ComfyUI 端加 tiling VAE 或後製。
- checkpoint 檔名要跟 ComfyUI 內看到的完全一致(含副檔名)。
