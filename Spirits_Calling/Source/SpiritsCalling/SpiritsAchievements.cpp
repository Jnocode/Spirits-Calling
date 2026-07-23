#include "SpiritsAchievements.h"

#include "Engine/Engine.h"
#include "Interfaces/OnlineAchievementsInterface.h"
#include "Interfaces/OnlineIdentityInterface.h"
#include "OnlineSubsystem.h"
#include "Misc/ConfigCacheIni.h"

namespace
{
	static const FName SteamSubsystemName(TEXT("Steam"));
	static const TCHAR* SteamSection = TEXT("OnlineSubsystemSteam");
	static const TCHAR* AchievementsSection = TEXT("SpiritsAchievements");
	static const TCHAR* ApprovedAppIdsKey = TEXT("ApprovedSteamAppIds");
	static const TCHAR* SteamAppIdKey = TEXT("SteamDevAppId");
	static const TCHAR* SteamEnabledKey = TEXT("bEnabled");
}

void USpiritsAchievements::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	RefreshBackendReadiness();
}

void USpiritsAchievements::Deinitialize()
{
	BackendOwnerId.Reset();
	BackendDefinitionIds.Reset();
	PendingBackendWrites.Reset();
	BackendWritesInFlight.Reset();
	BackendWritesCompleted.Reset();
	Super::Deinitialize();
}

TArray<int32> USpiritsAchievements::ReadApprovedAppIds() const
{
	TArray<int32> ApprovedAppIds;
	if (!GConfig)
	{
		return ApprovedAppIds;
	}

	FString SerializedAppIds;
	if (!GConfig->GetString(AchievementsSection, ApprovedAppIdsKey, SerializedAppIds, GEngineIni))
	{
		return ApprovedAppIds;
	}

	TArray<FString> Tokens;
	SerializedAppIds.ParseIntoArray(Tokens, TEXT(","), true);
	for (FString Token : Tokens)
	{
		Token = Token.TrimStartAndEnd();
		if (Token.IsNumeric())
		{
			ApprovedAppIds.AddUnique(FCString::Atoi(*Token));
		}
	}
	return ApprovedAppIds;
}

void USpiritsAchievements::LogBackendFailure(const FString& Code) const
{
	if (!Code.IsEmpty())
	{
		UE_LOG(LogTemp, Warning, TEXT("[SteamAchievements] %s"), *Code);
	}
}

void USpiritsAchievements::RecordFallback(const FString& Id, const FString& Code) const
{
	const FString EffectiveCode = Code.IsEmpty() ? TEXT("Steam.SubsystemUnavailable") : Code;
	UE_LOG(LogTemp, Log, TEXT("[Achievement] fallback unlock owner=%s id=%s code=%s"),
		BackendOwnerId.IsEmpty() ? TEXT("local") : *BackendOwnerId,
		*Id,
		*EffectiveCode);
	if (GEngine)
	{
		GEngine->AddOnScreenDebugMessage(-1, 4.f, FColor::Yellow,
			FString::Printf(TEXT("Achievement fallback: %s"), *Id));
	}
}

void USpiritsAchievements::RefreshBackendReadiness()
{
	BackendOwnerId.Reset();
	BackendDefinitionIds.Reset();

	SpiritsRules::FAchievementBackendProbe Probe;
	Probe.ApprovedAppIds = ReadApprovedAppIds();
	if (GConfig)
	{
		GConfig->GetInt(SteamSection, SteamAppIdKey, Probe.AppId, GEngineIni);
		GConfig->GetBool(SteamSection, SteamEnabledKey, Probe.bConfigEnabled, GEngineIni);
	}

	// Do not touch Steam until the project explicitly supplies an approved,
	// non-placeholder ID. This keeps PC/LAN fallback independent of Steam.
	if (!Probe.bConfigEnabled || Probe.AppId <= 0 || Probe.AppId == 480 || !Probe.ApprovedAppIds.Contains(Probe.AppId))
	{
		BackendReadiness = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
		LogBackendFailure(BackendReadiness.FailureCode);
		return;
	}

	IOnlineSubsystem* Steam = IOnlineSubsystem::Get(SteamSubsystemName);
	IOnlineIdentityPtr Identity = Steam ? Steam->GetIdentityInterface() : nullptr;
	IOnlineAchievementsPtr Achievements = Steam ? Steam->GetAchievementsInterface() : nullptr;
	Probe.bOSSAvailable = Steam != nullptr && Identity.IsValid() && Achievements.IsValid();
	if (!Probe.bOSSAvailable)
	{
		BackendReadiness = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
		LogBackendFailure(BackendReadiness.FailureCode);
		return;
	}

	FUniqueNetIdPtr UserId = Identity->GetUniquePlayerId(0);
	Probe.bIdentityAvailable = UserId.IsValid();
	if (!Probe.bIdentityAvailable)
	{
		BackendReadiness = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
		LogBackendFailure(BackendReadiness.FailureCode);
		return;
	}

	BackendOwnerId = UserId->ToString();
	BackendReadiness = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	BackendReadiness.State = SpiritsRules::EAchievementBackendState::IdentityReady;
	BackendReadiness.bIdentityAvailable = true;
	BackendReadiness.FailureCode.Reset();
	Achievements->QueryAchievements(
		*UserId,
		FOnQueryAchievementsCompleteDelegate::CreateUObject(
			this, &USpiritsAchievements::OnAchievementsQueryComplete));
	UE_LOG(LogTemp, Log, TEXT("[SteamAchievements] query started for Steam user %s"), *BackendOwnerId);
}

void USpiritsAchievements::OnAchievementsQueryComplete(const FUniqueNetId& UserId, bool bWasSuccessful)
{
	if (BackendOwnerId.IsEmpty() || BackendOwnerId != UserId.ToString())
	{
		BackendReadiness.State = SpiritsRules::EAchievementBackendState::IdentityReady;
		BackendReadiness.bDefinitionsAvailable = false;
		BackendReadiness.bSteamReleaseAcceptance = false;
		BackendReadiness.FailureCode = TEXT("Steam.IdentityUnavailable");
		for (const FString& PendingId : PendingBackendWrites)
		{
			RecordFallback(PendingId, BackendReadiness.FailureCode);
		}
		PendingBackendWrites.Reset();
		LogBackendFailure(BackendReadiness.FailureCode);
		return;
	}

	IOnlineSubsystem* Steam = IOnlineSubsystem::Get(SteamSubsystemName);
	IOnlineAchievementsPtr Achievements = Steam ? Steam->GetAchievementsInterface() : nullptr;
	TArray<FOnlineAchievement> CachedAchievements;
	const bool bCacheAvailable =
		bWasSuccessful && Achievements.IsValid() &&
		Achievements->GetCachedAchievements(UserId, CachedAchievements) == EOnlineCachedResult::Success;

	TSet<FString> QueriedIds;
	if (bCacheAvailable)
	{
		for (const FOnlineAchievement& Achievement : CachedAchievements)
		{
			QueriedIds.Add(Achievement.Id);
			if (Achievement.Progress >= 100.0)
			{
				BackendWritesCompleted.Add(Achievement.Id);
			}
		}
	}

	const TArray<FString>& CanonicalIds = SpiritsRules::GetAchievementIds();
	bool bExactDefinitionSet = bCacheAvailable && QueriedIds.Num() == CanonicalIds.Num();
	for (const FString& CanonicalId : CanonicalIds)
	{
		bExactDefinitionSet = bExactDefinitionSet && QueriedIds.Contains(CanonicalId);
	}

	SpiritsRules::FAchievementBackendProbe Probe;
	if (GConfig)
	{
		GConfig->GetInt(SteamSection, SteamAppIdKey, Probe.AppId, GEngineIni);
		GConfig->GetBool(SteamSection, SteamEnabledKey, Probe.bConfigEnabled, GEngineIni);
	}
	Probe.ApprovedAppIds = ReadApprovedAppIds();
	Probe.bOSSAvailable = Steam != nullptr && Achievements.IsValid();
	Probe.bIdentityAvailable = true;
	Probe.bDefinitionsQuerySucceeded = bExactDefinitionSet;
	BackendReadiness = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	if (!bExactDefinitionSet)
	{
		BackendReadiness.FailureCode = bCacheAvailable
			? TEXT("Steam.DefinitionMismatch")
			: TEXT("Steam.DefinitionQueryFailed");
		for (const FString& PendingId : PendingBackendWrites)
		{
			RecordFallback(PendingId, BackendReadiness.FailureCode);
		}
		PendingBackendWrites.Reset();
		LogBackendFailure(BackendReadiness.FailureCode);
		return;
	}

	BackendDefinitionIds = MoveTemp(QueriedIds);
	UE_LOG(LogTemp, Log, TEXT("[SteamAchievements] exact eight-ID definition set is WriteEligible for owner %s; release acceptance remains evidence-driven"), *BackendOwnerId);
	FlushPendingBackendWrites();
}

void USpiritsAchievements::UnlockAchievement(const FString& Id)
{
	if (!SpiritsRules::GetAchievementIds().Contains(Id))
	{
		RecordFallback(Id, TEXT("Steam.UnknownAchievementId"));
		return;
	}
	if (Unlocked.Contains(Id))
	{
		return;
	}
	Unlocked.Add(Id);
	WriteToBackend(Id);
}

void USpiritsAchievements::ReportPossessKill()
{
	if (++PossessKills >= 50)
	{
		UnlockAchievement(SpiritsAch::PossessKill50);
	}
}

void USpiritsAchievements::ReportSummon()
{
	if (++Summons >= 100)
	{
		UnlockAchievement(SpiritsAch::Summon100);
	}
}

void USpiritsAchievements::ReportWin(int32 Difficulty, int32 Civ, bool bLan)
{
	UnlockAchievement(SpiritsAch::FirstWin);

	switch (FMath::Clamp(Difficulty, 0, 2))
	{
	case 0:  UnlockAchievement(SpiritsAch::WinEasy);   break;
	case 2:  UnlockAchievement(SpiritsAch::WinHard);   break;
	default: UnlockAchievement(SpiritsAch::WinNormal); break;
	}

	if (bLan)
	{
		UnlockAchievement(SpiritsAch::LanWin);
	}

	CivWinMask |= static_cast<uint8>(1 << FMath::Clamp(Civ, 0, 3));
	if (CivWinMask == 0x0F)
	{
		UnlockAchievement(SpiritsAch::WinAllCivs);
	}
}

void USpiritsAchievements::FlushPendingBackendWrites()
{
	const TArray<FString> PendingIds = PendingBackendWrites.Array();
	PendingBackendWrites.Reset();
	for (const FString& Id : PendingIds)
	{
		WriteToBackend(Id);
	}
}

void USpiritsAchievements::WriteToBackend(const FString& Id)
{
	if (BackendWritesCompleted.Contains(Id) || BackendWritesInFlight.Contains(Id))
	{
		return;
	}
	if (!IsSteamWriteEligible())
	{
		// IdentityReady with no failure means QueryAchievements is still in flight.
		// Preserve the local unlock and defer exactly one backend write until the
		// query callback validates the exact definition set.
		if (BackendReadiness.State == SpiritsRules::EAchievementBackendState::IdentityReady &&
			BackendReadiness.FailureCode.IsEmpty() && !BackendOwnerId.IsEmpty())
		{
			PendingBackendWrites.Add(Id);
			UE_LOG(LogTemp, Log, TEXT("[SteamAchievements] write queued pending definition query: %s"), *Id);
			return;
		}
		RecordFallback(Id, BackendReadiness.FailureCode);
		return;
	}
	if (!BackendDefinitionIds.Contains(Id))
	{
		RecordFallback(Id, TEXT("Steam.UnknownAchievementId"));
		return;
	}

	IOnlineSubsystem* Steam = IOnlineSubsystem::Get(SteamSubsystemName);
	IOnlineIdentityPtr Identity = Steam ? Steam->GetIdentityInterface() : nullptr;
	IOnlineAchievementsPtr Achievements = Steam ? Steam->GetAchievementsInterface() : nullptr;
	FUniqueNetIdPtr UserId = Identity.IsValid() ? Identity->GetUniquePlayerId(0) : nullptr;
	if (!Achievements.IsValid() || !UserId.IsValid() || UserId->ToString() != BackendOwnerId)
	{
		RecordFallback(Id, TEXT("Steam.IdentityUnavailable"));
		return;
	}

	FOnlineAchievementsWriteRef WriteObject = MakeShared<FOnlineAchievementsWrite, ESPMode::ThreadSafe>();
	WriteObject->SetFloatStat(Id, 100.f);
	BackendWritesInFlight.Add(Id);
	Achievements->WriteAchievements(
		*UserId,
		WriteObject,
		FOnAchievementsWrittenDelegate::CreateUObject(
			this, &USpiritsAchievements::OnAchievementWriteComplete, Id));
	UE_LOG(LogTemp, Log, TEXT("[SteamAchievements] write started owner=%s id=%s"), *BackendOwnerId, *Id);
}

void USpiritsAchievements::OnAchievementWriteComplete(
	const FUniqueNetId& UserId,
	bool bWasSuccessful,
	FString AchievementId)
{
	BackendWritesInFlight.Remove(AchievementId);
	if (BackendOwnerId.IsEmpty() || BackendOwnerId != UserId.ToString())
	{
		RecordFallback(AchievementId, TEXT("Steam.IdentityUnavailable"));
		return;
	}
	if (!bWasSuccessful)
	{
		RecordFallback(AchievementId, TEXT("Steam.WriteFailed"));
		return;
	}

	BackendWritesCompleted.Add(AchievementId);
	UE_LOG(LogTemp, Log, TEXT("[SteamAchievements] write completed owner=%s id=%s"), *BackendOwnerId, *AchievementId);
}
