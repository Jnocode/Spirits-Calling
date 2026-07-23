# Spirits Calling — 上架檢查清單(v0.9)

> 四大師框架:陳星漢(情緒)/ 席德·梅爾(決策)/ 櫻井政博(手感)/ Jeff Kaplan(生態)
> 上架定位:**PC 單機 + 區網對戰 + PC VR**,搶先體驗(Early Access)定價帶 NT$150-250 / US$4.99-7.99

## ✅ 已完成(本次程式碼已含)

- 完整遊戲循環:召喚/附身/戰鬥/勝負 + 三段難度(主選單切換,影響波次間隔/上限/收入)
- 音效全掛鉤:攻擊/命中/召喚/死亡/警報/勝負/UI/環境風聲(程序化合成,見下方「唯一手動步驟」)
- 手感:hit stop、擊退、受擊閃白、傷害數字、攻擊突進
- 情緒曲線:動態霧色、危機脈動、聖壇陷落光柱、勝負氛圍收束
- UI:主選單(Play/難度/Host/Join/Quit)、HUD、倒數、警報、擊殺墊、結算重開;M 與 **Esc** 皆可開選單
- 打包:Shipping 組態、只烹飪 DemoMap、IoStore、輸出到 `Builds/`、應用程式圖示(Build/Windows/Application.ico)
- 版本資訊:v0.9.0、公司名、商店描述句

## ⚠️ 唯一手動步驟(打包前一次性)

1. 開編輯器,Content Browser 新建資料夾 `Audio`
2. 把 `Spirits_Calling/RawAssets/Audio/` 裡 9 個 .wav 全選拖進去(名稱不要改)
3. 雙擊 `S_Ambient` → 勾 Looping(可選,程式有備援重播)→ 全部儲存
   > 程式碼對音效全部空值保護,沒匯入也能跑,只是沒聲音

## 📦 打包流程

1. 編輯器 → Platforms → Windows → **Package Project**(已預設 Shipping)
2. 輸出在 `D:/Workspace/03_Dev_Projects/Spirits-Calling/Builds/Windows/`
3. 冒煙測試矩陣(每次出包必跑):
   - 單機三難度各一場打到分出勝負
   - 雙機 LAN:Host + Join,雙方附身/召喚/擊殺/斷線
   - PC VR(Quest Link/SteamVR):進出附身、召喚、90fps 檢查(`stat fps`)
   - 掛機 30 分鐘無 crash / 記憶體洩漏(工作管理員)

## 🚦 上架門檻(Steam 為例)

- [ ] Steamworks 帳號 + App 費用(US$100)
- [ ] 商店素材:膠囊圖(需真實美術,幾何體截圖可做首圖但轉化率低——這是目前最值得花錢外包的一項)、6-10 張截圖、30-60 秒 trailer(用 hit stop 和聖壇光柱當賣點鏡頭)
- [ ] 內容分級問卷(本作無血腥,Everyone 10+ 級距)
- [ ] EULA/隱私:目前無帳號無收集,用 Steam 標準模板即可
- [ ] Early Access 說明頁:誠實列出「單機+LAN,線上配對開發中(Nakama 路線圖見 Backend/Nakama/README)」

## 🔴 公網多人前的紅線(Kaplan 誠實邊界,EA 期間不做不騙)

- 無帳號系統/無反作弊/監聽伺服器信任主機——商店頁明寫「LAN & 好友連線」
- 上線公網配對的前置:nakama-unreal 認證 → 專用伺服器 → EAC/伺服器權威

## 🗺 v1.0 前的內容路線(梅爾:先核心後廣度)

1. ✅ 第二張地圖(S2 完成:ArenaBuilder 參數化為 `FArenaStyle`,Void 夜色 / Sands 黃沙日照兩風格,經 GameState.MapIndex 複寫保證全機一致)
2. ✅ 四文明差異化配表(S1 完成:每隊套自己文明 loadout,明顯不對稱;S2 補上文明選單)
3. ✅ 重攻擊(S1 完成:前搖 0.4s / hit stop 0.12s / 擊退 ×2 / 傷害 ×2.2;PC 右鍵、VR 左扳機)
4. ✅ 成就 8 個骨架(S4 完成:遊戲端邏輯/觸發點/子系統全接好,現寫本地 log;啟用 Steam 的步驟與 drop-in 線上寫入碼見 `STEAM_ACHIEVEMENTS.md`,需你的 Steamworks App)
5. ✅ 主選單(S2 完成:難度 / 地圖 / 文明 三顆循環鈕;設定於 Host 或新開局時套用)

> 進度細節見 `DEV_PLAN_v0.9_to_v1.0.md`。生成式美術產線見 `ComfyUI_Asset_Pipeline.md`。
