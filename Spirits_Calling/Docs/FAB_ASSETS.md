# Fab / Marketplace 素材清單（不入 git，本機保留）

> 這些是從 Epic Fab 加入的第三方素材，體積大且非本專案 IP，
> 已在根 `.gitignore` 排除，不推上 GitHub。fresh clone 後需從 Fab 重新加入。
> 使用者 Epic 帳號：`Jnoworldline`。

## 已加入的素材

| 素材 | Fab 名稱 | 本機路徑 | 體積 | 用途 |
|------|---------|---------|------|------|
| Big Niagara Bundle | Big Niagara Bundle (SoerGame) | `Content/BigNiagaraBundle/` | ~789 MB | 攻擊/技能 Niagara VFX，補 debug-line 佔位 |
| Basic Pickups VFX Set | Basic Pickups VFX Set (Fateloom) | `Content/sA_PickupSet_1/` | ~45 MB | 發光 icon 特效，用於召喚提示 / Soul Shrine 光柱 |

## 重新加入方式（fresh clone 後）

1. 開 Epic Launcher → 或編輯器內 **Window → Fab**
2. 登入 `Jnoworldline` → 我的收藏庫
3. 對上表素材按 **Add to Project** → 選 `Spirits_Calling` (UE 5.8)
4. 確認落點路徑與上表一致（C++/藍圖引用才對得上）

## 授權提醒（上架前必查）

上 Steam 販售前，逐一確認每個 Fab 素材的 license **允許商用發布**（多數 Epic/Marketplace 內容可，少數僅限個人）。授權狀態應記入 `Release_Readiness_Record` 的對應 gate。

## 若日後要讓 repo 自帶素材（可選）

零預算前提下建議維持「gitignore + 本機保留」。若要 self-contained，改用 **Git LFS**（注意 GitHub 免費 LFS 限 1GB 儲存/1GB 頻寬，超量計費）——與零帳單原則衝突，非必要不採用。
