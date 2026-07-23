# Steam 成就 — 啟用步驟(S4)

> 目前狀態:**遊戲端骨架已完成並可跑**。成就在達成時會寫本地 log +螢幕黃字提示(免 Steam 可測)。
> 下面是等你有 Steamworks App ID 後,把它接上真正 Steam 成就的步驟。這些步驟會動到連線設定,請一次做完再測 LAN。

## 已接好的遊戲端(這輪完成)

- `USpiritsAchievements`(GameInstance 子系統,跨關卡存活整個遊玩 session):去重、計數、解鎖邏輯。
- 伺服器偵測事件 → 經 `ASpiritsPlayerController` 的 Client RPC → 擁有端本機解鎖(單機/LAN 都正確,Steam 是 per-user client-side)。
- 觸發點:`SpawnUnitForPlayer`(召喚)、`NotifyUnitDied`(附身擊殺)、`EndMatch`(勝利/難度/文明/LAN)。

## 成就清單(8 個,ID 需在 Steamworks 建一致)

| ID | 條件 |
|---|---|
| `ACH_FIRST_WIN` | 首次獲勝 |
| `ACH_WIN_EASY` / `ACH_WIN_NORMAL` / `ACH_WIN_HARD` | 各難度獲勝 |
| `ACH_POSSESS_KILL_50` | 累計附身擊殺 50(session 內累計) |
| `ACH_SUMMON_100` | 累計召喚 100 |
| `ACH_WIN_ALL_CIVS` | 用四文明各贏過一場 |
| `ACH_LAN_WIN` | 連線對戰中獲勝 |

> 累計型(擊殺/召喚)目前在 session 內累計;接上 Steam Stats 後可跨啟動持久化(見下方進階)。

## 啟用步驟

1. **Steamworks**:建立 App、拿到 AppID,在後台建上表 8 個成就(ID 完全一致)。
2. **外掛**:`Spirits_Calling.uproject` 的 `Plugins` 加入
   ```json
   { "Name": "OnlineSubsystemSteam", "Enabled": true }
   ```
3. **Build.cs**:`SpiritsCalling.Build.cs` 的 `PublicDependencyModuleNames` 加 `"OnlineSubsystem"`。
4. **DefaultEngine.ini** 追加(先不要動 `DefaultPlatformService`,以免影響現有 LAN 直連;成就用具名子系統即可):
   ```ini
   [OnlineSubsystemSteam]
   bEnabled=true
   SteamDevAppId=480        ; 開發測試用 480(Spacewar);上線換成你的 AppID
   ```
   > 若之後要用 Steam 大廳配對再考慮把 `[OnlineSubsystem] DefaultPlatformService=Steam` 打開,並回歸測試 LAN。
5. **steam_appid.txt**:在編輯器/打包執行目錄放一個內容為 AppID 的 `steam_appid.txt`,並確保 Steam 客戶端在跑。
6. 在 `SpiritsAchievements.cpp` 頂部把 `SPIRITS_USE_STEAM_ACHIEVEMENTS` 設為 `1`,並把 `WriteToBackend` 的 `WriteSteamAchievement(Id)` 換成下面的實作。

## Drop-in:`WriteSteamAchievement` 實作

在 `SpiritsAchievements.cpp` 加上 includes 與函式:

```cpp
#include "OnlineSubsystem.h"
#include "Interfaces/OnlineAchievementsInterface.h"
#include "Interfaces/OnlineIdentityInterface.h"

void USpiritsAchievements::WriteSteamAchievement(const FString& Id)
{
    IOnlineSubsystem* OSS = IOnlineSubsystem::Get(STEAM_SUBSYSTEM);
    if (!OSS) { UE_LOG(LogTemp, Warning, TEXT("[Achievement] Steam OSS unavailable: %s"), *Id); return; }

    IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
    IOnlineAchievementsPtr Achievements = OSS->GetAchievementsInterface();
    if (!Identity.IsValid() || !Achievements.IsValid()) { return; }

    FUniqueNetIdPtr UserId = Identity->GetUniquePlayerId(0);
    if (!UserId.IsValid()) { return; }

    FOnlineAchievementsWritePtr WriteObject = MakeShareable(new FOnlineAchievementsWrite());
    WriteObject->SetFloatStat(*Id, 100.0f);   // 100% == unlocked
    FOnlineAchievementsWriteRef WriteRef = WriteObject.ToSharedRef();
    Achievements->WriteAchievements(*UserId, WriteRef);
}
```

在標頭 `SpiritsAchievements.h` 的 private 區加宣告:
```cpp
void WriteSteamAchievement(const FString& Id);
```

> `STEAM_SUBSYSTEM` 定義在 OnlineSubsystemSteam;若編譯找不到,用 `FName(TEXT("Steam"))` 取代。
> 需先呼叫 `Achievements->QueryAchievements(*UserId, ...)` 至少一次以載入定義;可在子系統 `Initialize` 時做。

## 進階(持久化累計統計)

附身擊殺/召喚等累計型,接上後建議改用 Steam Stats(`WriteObject->SetIntStat`)並在 Steamworks 設 stat→achievement 觸發,讓進度跨遊戲啟動累積,而非只在單一 session。
