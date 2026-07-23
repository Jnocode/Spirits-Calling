#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "OnlineSubsystemTypes.h"
#include "SpiritsRules.h"
#include "SpiritsAchievements.generated.h"

/**
 * Steam achievement API keys. Create matching achievements in the Steamworks
 * partner site with these exact IDs. See Docs/STEAM_ACHIEVEMENTS.md.
 */
namespace SpiritsAch
{
	const FString FirstWin      = TEXT("ACH_FIRST_WIN");
	const FString WinEasy       = TEXT("ACH_WIN_EASY");
	const FString WinNormal     = TEXT("ACH_WIN_NORMAL");
	const FString WinHard       = TEXT("ACH_WIN_HARD");
	const FString PossessKill50 = TEXT("ACH_POSSESS_KILL_50");
	const FString Summon100     = TEXT("ACH_SUMMON_100");
	const FString WinAllCivs    = TEXT("ACH_WIN_ALL_CIVS");
	const FString LanWin        = TEXT("ACH_LAN_WIN");
}

/**
 * Per-player-machine achievement tracker (client side). Lives on the GameInstance
 * so its running counters survive level travel within a play session.
 *
 * The server detects gameplay events and forwards them to the owning client via
 * ASpiritsPlayerController Client RPCs. Steam writes are allowed only after the
 * local identity has queried an exact eight-ID definition set. Local fallback
 * progress remains available when Steam is unavailable and never implies Steam
 * release acceptance.
 */
UCLASS()
class SPIRITSCALLING_API USpiritsAchievements : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Current Steam readiness state; fallback remains usable when not eligible. */
	SpiritsRules::EAchievementBackendState GetBackendState() const { return BackendReadiness.State; }
	const SpiritsRules::FAchievementBackendReadiness& GetBackendReadiness() const { return BackendReadiness; }
	bool IsSteamWriteEligible() const
	{
		return BackendReadiness.State == SpiritsRules::EAchievementBackendState::WriteEligible;
	}
	bool IsDevelopmentFallbackPass() const { return BackendReadiness.bDevelopmentFallbackPass; }
	bool IsSteamReleaseAcceptance() const { return BackendReadiness.bSteamReleaseAcceptance; }

	/** Unlock once locally and route at most one owning-client Steam write. */
	void UnlockAchievement(const FString& Id);

	/** Running counters unlock their milestone achievement when crossed. */
	void ReportPossessKill();
	void ReportSummon();

	/** Match won: grants first-win, per-difficulty, LAN and all-civilizations achievements. */
	void ReportWin(int32 Difficulty, int32 Civ, bool bLan);

#if WITH_DEV_AUTOMATION_TESTS
	/** Dev-only seams so subsystem integration automation can drive the real router. */
	void InitializeForAutomation() { RefreshBackendReadiness(); }
	bool HasUnlockedForAutomation(const FString& Id) const { return Unlocked.Contains(Id); }
	int32 GetUnlockedCountForAutomation() const { return Unlocked.Num(); }
	int32 GetPossessKillsForAutomation() const { return PossessKills; }
	int32 GetSummonsForAutomation() const { return Summons; }
#endif

private:
	void RefreshBackendReadiness();
	void OnAchievementsQueryComplete(const FUniqueNetId& UserId, bool bWasSuccessful);
	void OnAchievementWriteComplete(const FUniqueNetId& UserId, bool bWasSuccessful, FString AchievementId);
	void FlushPendingBackendWrites();
	void WriteToBackend(const FString& Id);
	void RecordFallback(const FString& Id, const FString& Code) const;
	void LogBackendFailure(const FString& Code) const;
	TArray<int32> ReadApprovedAppIds() const;

	SpiritsRules::FAchievementBackendReadiness BackendReadiness;
	FString BackendOwnerId;
	TSet<FString> BackendDefinitionIds;
	TSet<FString> PendingBackendWrites;
	TSet<FString> BackendWritesInFlight;
	TSet<FString> BackendWritesCompleted;

	UPROPERTY()
	TSet<FString> Unlocked;

	int32 PossessKills = 0;
	int32 Summons = 0;
	uint8 CivWinMask = 0; // bit per civilization won with (4 civs -> 0b1111 == all)
};
