# 你的 ComfyUI 工作流盤點(對 Spirits Calling 的用途)

> 2026-07-05。逐一查過清單裡的工作流,標出各自幹嘛、VRAM/雲端、以及對本專案「靜圖素材 / VFX 影片 / 音訊」的推薦。⭐ = 建議用。

## 🖼 靜態圖(素材、貼圖、商店圖)

| 工作流 | 是什麼 | 對我們的用途 |
|---|---|---|
| `image_krea2_turbo_t2i` ⭐ | **Krea 2 Turbo**,12B,8 步、約 2 秒出 2K,獨立評測 T2I 排名頂尖,美感最好 | **商店主圖/截圖底、四文明紋樣升級版**(比 SDXL Turbo 質感好一截,VRAM 較重、可接受) |
| `image_flux2_klein_image_edit_4b_distilled` ⭐ | **Flux.2 Klein 4B**「影像編輯」蒸餾版,輕、指令遵從好 | **編輯/精修既有圖**:把帶色紋樣改中性灰階、清乾淨 VFX 關鍵影格、局部改圖 |
| `sdxlturbo_example` | 我們現在用的 SDXL Turbo,最輕最快 | 快速草稿、量產底圖(已在用) |

## 🎬 影片(拿來做 VFX,抽幀→sprite sheet→Niagara)

| 工作流 | 是什麼 | 對我們的用途 |
|---|---|---|
| `Wan2.2_T2I_to_I2V_Integrated` ⭐⭐ | **Wan 2.2** 文字→圖→影像轉影片,一條龍 | **一次性 VFX 最省事**:一句提示詞直接產「關鍵影格+動畫」(光刃/召喚爆發/命中火花),不用手動接關鍵影格 |
| `Wan2.2_I2V_Grok_Vision` ⭐ | Wan 2.2 影像轉影片 + Grok 視覺輔助提示 | 把我們 Krea/SDXL 生的**黑底關鍵影格**動起來 |
| `SVI-2-3-ksampler_civitai` ⭐ | **Stable Video Infinity(Wan 2.2)**,長片/無限長、首尾影格控制、無縫接合 | **循環 VFX 最佳解**:靈魂光環、聖壇光柱設「首影格=尾影格」→ 真無縫循環(勝過 ping-pong) |
| `LTX2.3文生MV工作流` ⭐ | **LTX 2.3**,快(4090 上 5 秒片約 25–40s)、GGUF 可壓到低 VRAM、含原生音訊 | **VRAM 吃緊/要快速迭代時的首選**;先用它試效果、定案再上 Wan |
| `video_wan2_2_14B_t2v` | Wan 2.2 14B 文字轉影片,電影級動態但重、慢 | 英雄級一次性鏡頭(VRAM 夠再用) |
| `Seedance2.0全能參考視頻(创建ID)` / `template_seedance_2_0_plus_llm_prompt_helper` | **Seedance 2.0**,**雲端 API**(ByteDance),品質最高、2K、音畫同步、多鏡頭 | **不是本地跑**,要 API/額度;拿來做 **trailer/行銷鏡頭** 最值,不適合量產 VFX |

## 🔊 音訊(沒要求,但對遊戲有用)

| 工作流 | 是什麼 | 對我們的用途 |
|---|---|---|
| `audio_ace_step1_5_xl_turbo` | **ACE-Step** 音樂生成 | 可生 BGM/環境樂(目前遊戲是程序合成音效,這是升級路徑) |
| `LongCat-AudioDIT-TTS_workflow` | 文字轉語音(TTS) | 旁白/語音(若之後要) |

## ⛔ 與本專案無關

- `TASTYSIN_Q8_GGUF_NSFW_LOW_VRAM` — NSFW 模型,遊戲用不到也不合適,略過。
- `unsloth_flowers` / `Dev/` — Unsloth 多為 LLM 微調示範 / 你自己的開發用,與素材產線無關。

---

## 給 VFX 的最終建議(依你 GPU 狀況)

1. **一次性效果**(光刃輕/重、召喚爆發、命中火花):
   - 省事 → `Wan2.2_T2I_to_I2V_Integrated`(一句話出動畫)
   - 要控黑底/造型 → Krea2 或 SDXL 生黑底關鍵影格(我已做好 `prompts_vfx.json`)→ `Wan2.2_I2V_Grok_Vision`
   - VRAM 緊/要快 → `LTX2.3`
2. **循環效果**(靈魂光環、聖壇光柱):`SVI-2-3`,首影格=尾影格 → 無縫循環。
3. **靜圖升級**:商店主圖與四文明紋樣改用 `Krea2 Turbo`;要乾淨隊色上色就用 `Flux.2 Klein edit` 把紋樣改中性。
4. **下游不變**:抽幀 → sprite sheet → UE Niagara SubUV、additive、染隊色/文明色。

> 我可以對著你任一個工作流(建議先 `Wan2.2_T2I_to_I2V_Integrated` 或 `LTX2.3`)的節點圖,幫你把「生成 → 抽幀 → sprite sheet」那段串成能直接載入的 JSON;或把 `comfyui_generate.py` 擴成能直接呼叫它。

## 來源

- [Krea 2 Turbo 評測](https://www.buildfastwithai.com/blogs/krea-2-open-source-review-raw-turbo) · [VentureBeat Krea 2](https://venturebeat.com/technology/enterprise-grade-ai-image-generation-in-2-seconds-is-here-krea-2-raw-and-turbo-available-as-open-weights-under-custom-license)
- [Flux.2 Klein(RunDiffusion)](https://www.rundiffusion.com/flux-2-klein-three-new-models)
- [LTX 2.3 vs Wan 2.2 比較](https://wavespeed.ai/blog/posts/ltx-2-3-vs-wan-2-2-comparison-2026/) · [neurocanvas](https://neurocanvas.net/blog/wan-2-2-vs-ltx-2-comparison/)
- [Seedance 2.0 in ComfyUI(雲端 API)](https://blog.comfy.org/p/seedance-20-is-now-available-in-comfyui)
- [Stable Video Infinity(GitHub)](https://github.com/vita-epfl/Stable-Video-Infinity) · [SVI 2 Pro 首尾影格節點](https://github.com/Well-Made/ComfyUI-Wan-SVI2Pro-FLF)
