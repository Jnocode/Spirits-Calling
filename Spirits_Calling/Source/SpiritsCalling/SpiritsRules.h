#pragma once

#include "CoreMinimal.h"
#include "SpiritsTypes.h"

/**
 * Pure, world-independent rules used by runtime, automation, and external
 * harnesses. This header intentionally has no Actor, Steam, or Editor API
 * dependencies.
 */
namespace SpiritsRules
{
	constexpr int32 Civilizations = 4;
	constexpr int32 ArchetypesPerCivilization = 3;
	constexpr int32 MinDifficulty = 0;
	constexpr int32 MaxDifficulty = 2;
	constexpr int32 MinMapIndex = 0;
	constexpr int32 MaxMapIndex = 1;
	constexpr float HeavyAttackWindupSeconds = 0.40f;
	constexpr float HeavyAttackHitStopSeconds = 0.12f;
	constexpr float HeavyAttackDamageMultiplier = 2.20f;
	constexpr float HeavyAttackKnockbackMultiplier = 2.00f;

	namespace FailureCodes
	{
		inline constexpr TCHAR InvalidPhase[] = TEXT("Summon.InvalidPhase");
		inline constexpr TCHAR InvalidLoadout[] = TEXT("Summon.InvalidLoadout");
		inline constexpr TCHAR InvalidIndex[] = TEXT("Summon.InvalidIndex");
		inline constexpr TCHAR InvalidSouls[] = TEXT("Summon.InvalidSouls");
		inline constexpr TCHAR InsufficientSouls[] = TEXT("Summon.InsufficientSouls");
		inline constexpr TCHAR InvalidLocation[] = TEXT("Summon.InvalidLocation");
		inline constexpr TCHAR SpawnFailedRefunded[] = TEXT("Summon.SpawnFailedRefunded");
	}

	/** Immutable match inputs consumed by pure validation seams. */
	struct FMatchSettings
	{
		ESpiritsMatchPhase Phase = ESpiritsMatchPhase::WaitingToStart;
		int32 Difficulty = 1;
		int32 MapIndex = 0;
		ECivilization TeamACiv = ECivilization::East;
		ECivilization TeamBCiv = ECivilization::Norse;
		bool bLan = false;
	};

	struct FSummonValidation
	{
		bool bAccepted = false;
		int32 Cost = 0;
		FString FailureCode;

		bool IsRejected() const { return !bAccepted; }
	};

	/** Immutable transaction snapshot carried between spawn/refund callbacks. */
	struct FSummonTransactionState
	{
		FString TransactionToken;
		int32 SoulsBefore = 0;
		int32 SoulsAfter = 0;
		bool bCostDeducted = false;
		bool bSpawned = false;
		bool bRefundApplied = false;
		bool bSettled = false;
	};

	struct FSummonTransactionResult
	{
		bool bSpawned = false;
		int32 SoulsBefore = 0;
		int32 SoulsAfter = 0;
		bool bRefundApplied = false;
		/** True only for the callback that emits the refund event. */
		bool bRefundEventEmitted = false;
		/** Invalid requests and spawn failures always expose a failure indication. */
		bool bFailureIndicated = false;
		/** A repeated callback for an already settled token is ignored. */
		bool bAlreadySettled = false;
		FString TransactionToken;
		FString FailureCode;
		FSummonTransactionState State;
	};

	struct FHeavyAttackResult
	{
		bool bAccepted = false;
		bool bHit = false;
		float ResolveTime = 0.f;
		float Damage = 0.f;
		float KnockbackMagnitude = 0.f;
		float HitStopSeconds = 0.f;
	};

	/** Authoritative difficulty snapshot consumed before the match enters InProgress. */
	struct FDifficultyTuning
	{
		int32 Difficulty = 1;
		float AIWaveInterval = 30.f;
		int32 MaxWaveSize = 6;
		int32 SoulsPerSecond = 3;
	};

	/** Returns the normalized Easy/Normal/Hard pressure and economy snapshot. */
	SPIRITSCALLING_API FDifficultyTuning ResolveDifficultyTuning(int32 Difficulty);

	/** Pure authority gate: a Team B human permanently suppresses AI waves for the match. */
	SPIRITSCALLING_API bool ShouldRunAIWaves(
		ESpiritsMatchPhase Phase,
		bool bHumanTeamBSeen,
		bool bTeamBHasHuman);

	/** Pure authority gate used by both light and heavy runtime attack paths. */
	SPIRITSCALLING_API bool CanResolveCombat(
		ESpiritsMatchPhase Phase,
		bool bAlive,
		bool bIsStructure);

	/** Pure arena mapping returned after MapIndex normalization. */
	struct FMapStyleHooks
	{
		int32 MapIndex = 0;
		FString Style;
		FString GroundHook;
		FString SkyHook;
	};

	/** Stable, case-sensitive IDs shared by runtime adapters and external harnesses. */
	namespace AchievementIds
	{
		inline constexpr TCHAR FirstWin[] = TEXT("ACH_FIRST_WIN");
		inline constexpr TCHAR WinEasy[] = TEXT("ACH_WIN_EASY");
		inline constexpr TCHAR WinNormal[] = TEXT("ACH_WIN_NORMAL");
		inline constexpr TCHAR WinHard[] = TEXT("ACH_WIN_HARD");
		inline constexpr TCHAR PossessKill50[] = TEXT("ACH_POSSESS_KILL_50");
		inline constexpr TCHAR Summon100[] = TEXT("ACH_SUMMON_100");
		inline constexpr TCHAR WinAllCivilizations[] = TEXT("ACH_WIN_ALL_CIVS");
		inline constexpr TCHAR LanWin[] = TEXT("ACH_LAN_WIN");
	}

	enum class EAchievementBackendState : uint8
	{
		Disabled,
		ConfigValid,
		OSSReady,
		IdentityReady,
		DefinitionsReady,
		WriteEligible
	};

	enum class EAchievementId : uint8
	{
		FirstWin,
		WinEasy,
		WinNormal,
		WinHard,
		PossessKill50,
		Summon100,
		WinAllCivilizations,
		LanWin
	};

	struct FAchievementDefinition
	{
		FString Id;
		FString DisplayName;
		int32 Threshold = 0;
	};

	enum class EAchievementEventType : uint8
	{
		Win,
		PossessionKill,
		Summon,
		Unlock
	};

	/** Backend-neutral gameplay event; OwnerId is always the event owner's identity. */
	struct FAchievementEvent
	{
		EAchievementEventType Type = EAchievementEventType::Win;
		FString AchievementId;
		FString OwnerId;
		bool bLan = false;
		int32 Difficulty = 1;
		int32 Civilization = 0;
	};

	struct FAchievementLocalRecord
	{
		FString AchievementId;
		FString OwnerId;
		FString Code;
		bool bFallback = false;
	};

	/** Backend-neutral unlock intent; the caller supplies the owning identity. */
	struct FAchievementUnlockRequest
	{
		FString AchievementId;
		FString OwnerId;
		bool bDefinitionKnown = false;
		bool bAlreadyWrittenThisSession = false;
	};

	/**
	 * Backend-neutral adapter seam. Production Steam code and tests provide an
	 * implementation; this interface intentionally knows nothing about Steam SDK.
	 */
	class SPIRITSCALLING_API IAchievementBackend
	{
	public:
		virtual ~IAchievementBackend() = default;
		virtual bool IsIdentityAvailable(const FString& OwnerId) const = 0;
		virtual bool QueryDefinitions(const FString& OwnerId, TSet<FString>& OutDefinitions) = 0;
		virtual bool WriteAchievement(const FString& OwnerId, const FString& AchievementId) = 0;
		virtual void RecordFallback(const FAchievementLocalRecord& Record) = 0;
	};

	/** Pure session event router used by runtime adapters and fake backends. */
	class SPIRITSCALLING_API FAchievementEventRouter
	{
	public:
		explicit FAchievementEventRouter(IAchievementBackend& InBackend);

		void ProcessEvent(const FAchievementEvent& Event);
		void RequestUnlock(const FString& OwnerId, const FString& AchievementId);

		const TArray<FAchievementUnlockRequest>& GetUnlockIntents() const { return UnlockIntents; }
		const TArray<FAchievementLocalRecord>& GetLocalRecords() const { return LocalRecords; }

	private:
		struct FUserProgress
		{
			int32 PossessKills = 0;
			int32 Summons = 0;
			uint8 CivWinMask = 0;
		};

		bool EnsureDefinitions(const FString& OwnerId);
		void RecordFallback(const FString& OwnerId, const FString& AchievementId, const FString& Code);
		static FString MakeDedupKey(const FString& OwnerId, const FString& AchievementId);

		IAchievementBackend& Backend;
		TMap<FString, FUserProgress> ProgressByUser;
		TSet<FString> AttemptedUnlocks;
		TSet<FString> QueriedUsers;
		TSet<FString> FailedQueries;
		TMap<FString, TSet<FString>> DefinitionsByUser;
		TArray<FAchievementUnlockRequest> UnlockIntents;
		TArray<FAchievementLocalRecord> LocalRecords;
	};

	/** Pure snapshot of backend readiness; adapters update it, rules never query OSS. */
	struct FAchievementBackendReadiness
	{
		EAchievementBackendState State = EAchievementBackendState::Disabled;
		bool bIdentityAvailable = false;
		bool bDefinitionsAvailable = false;
		/** Development fallback is intentionally independent from Steam release acceptance. */
		bool bDevelopmentFallbackPass = true;
		/** This is evidence-driven and is never inferred from fallback or source configuration. */
		bool bSteamReleaseAcceptance = false;
		FString FailureCode;
	};

	/** Inputs used by the fake OSS/readiness tests and by the runtime adapter. */
	struct FAchievementBackendProbe
	{
		int32 AppId = 0;
		TArray<int32> ApprovedAppIds;
		/** Defaults to enabled for source-level probes; runtime fills this from DefaultEngine.ini. */
		bool bConfigEnabled = true;
		bool bOSSAvailable = false;
		bool bIdentityAvailable = false;
		bool bDefinitionsQuerySucceeded = false;
	};

	enum class EAssetValidationState : uint8
	{
		Unvalidated,
		Valid,
		Invalid
	};

	namespace CanonicalAssetSources
	{
		inline constexpr TCHAR EastPattern[] = TEXT("RawAssets/AI/Civilizations/East/East_pattern.png");
		inline constexpr TCHAR NorsePattern[] = TEXT("RawAssets/AI/Civilizations/Norse/Norse_pattern.png");
		inline constexpr TCHAR EgyptPattern[] = TEXT("RawAssets/AI/Civilizations/Egypt/Egypt_pattern.png");
		inline constexpr TCHAR CyberPattern[] = TEXT("RawAssets/AI/Civilizations/Cyber/Cyber_pattern.png");
		inline constexpr TCHAR VoidGround[] = TEXT("RawAssets/AI/Arenas/Void/Arena_Void_ground.png");
		inline constexpr TCHAR VoidSky[] = TEXT("RawAssets/AI/Arenas/Void/Arena_Void_sky.png");
		inline constexpr TCHAR SandsGround[] = TEXT("RawAssets/AI/Arenas/Sands/Arena_Sands_ground.png");
		inline constexpr TCHAR SandsSky[] = TEXT("RawAssets/AI/Arenas/Sands/Arena_Sands_sky.png");
		inline constexpr TCHAR StoreCapsule[] = TEXT("RawAssets/AI/Store/Store_capsule_concept.png");
	}

	enum class EAssetCategory : uint8
	{
		CivilizationPattern,
		ArenaGround,
		ArenaSky,
		StoreDraft
	};

	enum class ECookClass : uint8
	{
		Runtime,
		StoreOnly
	};

	/** Engine-agnostic manifest boundary; file import and hashing stay outside this seam. */
	struct FAssetManifestEntry
	{
		FString Source;
		EAssetCategory Category = EAssetCategory::CivilizationPattern;
		FString RuntimePath;
		FString Hook;
		ECookClass CookClass = ECookClass::Runtime;
		EAssetValidationState ValidationState = EAssetValidationState::Unvalidated;
		int32 Width = 0;
		int32 Height = 0;
		bool bRuntimeReady = false;
		bool bSkyboxExceptionDocumented = false;
		FString FailureCode;
		FString FailureReason;
	};

	enum class EReleaseGateStatus : uint8
	{
		NotRun,
		Pass,
		Fail,
		Blocked
	};

	enum class EPackageAcceptanceState : uint8
	{
		Blocked,
		NotReady,
		Ready
	};

	struct FReleaseGate
	{
		FString Id;
		FString Owner;
		EReleaseGateStatus GateStatus = EReleaseGateStatus::NotRun;
		/** Serialized status retained for JSON/Markdown adapters. */
		FString Status;
		FString EvidencePath;
		FString Timestamp;
		FString FailureReason;
		FString ResolutionStatus;
	};

	struct FMachineProfile
	{
		FString OperatingSystem;
		FString CPU;
		FString GPU;
		FString RAM;
	};

	struct FPackageManifest
	{
		FString PackageVersion;
		FString SourceRevision;
		FString EngineVersion;
		TArray<FString> CookMaps;
		FString Platform;
		FString Configuration;
		bool bProjectCodeBuild = false;
		bool bIoStore = false;
		FString PackagePath;
		FString LaunchLog;
		TArray<FString> CookedRuntimeObjects;
		TArray<FString> StoreOnlyObjects;
	};

	struct FReadinessRecord
	{
		EPackageAcceptanceState PackageAcceptance = EPackageAcceptanceState::Blocked;
		FPackageManifest Package;
		TArray<FReleaseGate> Gates;
		TArray<FReleaseGate> SmokeMatrix;
		TArray<FString> UnresolvedIssues;
		FString EarliestFailureStep;
		FString EarliestFailureReason;
		FString EarliestFailureLogPath;
		FMachineProfile Machine;
	};

	/** Returns exactly three configured entries for every civilization value. */
	SPIRITSCALLING_API TArray<FMinionArchetype> BuildCivLoadout(ECivilization Civilization);
	SPIRITSCALLING_API TArray<FMinionArchetype> BuildCivLoadout(int32 Civilization);

	/** Clamps arbitrary host input to the two supported runtime map variants. */
	SPIRITSCALLING_API int32 NormalizeMapIndex(int32 MapIndex);
	SPIRITSCALLING_API FMapStyleHooks ResolveMapStyle(int32 MapIndex);

	/** Validates only data supplied by the caller; no world or spawn query occurs here. */
	SPIRITSCALLING_API FSummonValidation ValidateSummon(
		const FMatchSettings& Settings,
		const TArray<FMinionArchetype>& TeamLoadout,
		int32 ArchetypeIndex,
		int32 Souls,
		bool bSpawnLocationValid = true);

	/** Starts an accepted summon transaction without mutating world/player state. */
	SPIRITSCALLING_API FSummonTransactionState BeginSummonTransaction(
		const FSummonValidation& Validation,
		int32 SoulsBefore,
		const FString& TransactionToken);

	/**
	 * Applies one external spawn outcome to an immutable transaction snapshot.
	 * Passing the returned State to a later callback makes refund emission
	 * exactly-once for the transaction token.
	 */
	SPIRITSCALLING_API FSummonTransactionResult EvaluateSummonTransaction(
		const FSummonValidation& Validation,
		const FSummonTransactionState& PreviousState,
		bool bSpawnSucceeded);

	/** Backward-compatible one-shot transaction seam. */
	SPIRITSCALLING_API FSummonTransactionResult EvaluateSummonTransaction(
		const FSummonValidation& Validation,
		int32 SoulsBefore,
		bool bSpawnSucceeded);

	/** Evaluates timing and multipliers without scheduling an engine timer. */
	SPIRITSCALLING_API FHeavyAttackResult EvaluateHeavyAttack(
		float BaseDamage,
		float BaseKnockbackMagnitude,
		bool bCanAttack,
		float CancellationTimeSeconds = -1.f);

	/** Exact case-sensitive achievement IDs; no OnlineSubsystem dependency. */
	SPIRITSCALLING_API const TArray<FString>& GetAchievementIds();
	SPIRITSCALLING_API FString GetAchievementId(EAchievementId Id);

	/**
	 * Advances the Steam readiness state machine using only caller-provided probe
	 * results. App ID 0 and the development placeholder 480 are always rejected,
	 * even if they appear in the approved list.
	 */
	SPIRITSCALLING_API FAchievementBackendReadiness EvaluateAchievementBackendReadiness(
		const FAchievementBackendProbe& Probe);
}
