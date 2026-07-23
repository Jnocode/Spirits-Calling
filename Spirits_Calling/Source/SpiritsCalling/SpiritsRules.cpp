#include "SpiritsRules.h"

namespace SpiritsRules
{
	namespace
	{
		FMinionArchetype MakeArchetype(
			const TCHAR* Name,
			float MaxHP,
			float AttackDamage,
			float AttackRange,
			float AttackInterval,
			float MoveSpeed,
			int32 SummonCost,
			const FLinearColor& Hue,
			float Brightness,
			float MeshScale)
		{
			FMinionArchetype Archetype;
			Archetype.DisplayName = Name;
			Archetype.MaxHP = MaxHP;
			Archetype.AttackDamage = AttackDamage;
			Archetype.AttackRange = AttackRange;
			Archetype.AttackInterval = AttackInterval;
			Archetype.MoveSpeed = MoveSpeed;
			Archetype.SummonCost = SummonCost;
			Archetype.Tint = Hue * Brightness;
			Archetype.MeshScale = MeshScale;
			return Archetype;
		}
	}

	TArray<FMinionArchetype> BuildCivLoadout(ECivilization Civilization)
	{
		const FLinearColor Hue = SpiritsCiv::GetHue(static_cast<int32>(Civilization));
		TArray<FMinionArchetype> Loadout;
		Loadout.Reserve(ArchetypesPerCivilization);

		switch (Civilization)
		{
		case ECivilization::East:
			Loadout.Add(MakeArchetype(TEXT("Sword Spirit"), 90.f, 16.f, 210.f, 0.85f, 560.f, 40, Hue, 1.0f, 0.90f));
			Loadout.Add(MakeArchetype(TEXT("Warding Monk"), 240.f, 10.f, 220.f, 1.40f, 440.f, 70, Hue, 0.55f, 1.20f));
			Loadout.Add(MakeArchetype(TEXT("Flying Sword"), 55.f, 20.f, 260.f, 0.70f, 760.f, 35, Hue, 1.6f, 0.70f));
			break;

		case ECivilization::Norse:
			Loadout.Add(MakeArchetype(TEXT("Berserker"), 180.f, 26.f, 190.f, 1.30f, 420.f, 60, Hue, 1.0f, 1.05f));
			Loadout.Add(MakeArchetype(TEXT("Shieldwall"), 460.f, 14.f, 200.f, 1.70f, 320.f, 95, Hue, 0.5f, 1.40f));
			Loadout.Add(MakeArchetype(TEXT("Axe Thrower"), 110.f, 24.f, 300.f, 1.50f, 400.f, 50, Hue, 1.3f, 0.95f));
			break;

		case ECivilization::Egypt:
			Loadout.Add(MakeArchetype(TEXT("Khopesh Guard"), 120.f, 16.f, 200.f, 1.05f, 460.f, 40, Hue, 1.0f, 1.00f));
			Loadout.Add(MakeArchetype(TEXT("Obelisk Sentinel"), 320.f, 12.f, 220.f, 1.50f, 360.f, 70, Hue, 0.55f, 1.30f));
			Loadout.Add(MakeArchetype(TEXT("Anubis Jackal"), 80.f, 15.f, 190.f, 0.85f, 620.f, 25, Hue, 1.5f, 0.80f));
			break;

		case ECivilization::Cyber:
			Loadout.Add(MakeArchetype(TEXT("Chainblade"), 95.f, 22.f, 230.f, 0.90f, 520.f, 45, Hue, 1.1f, 0.90f));
			Loadout.Add(MakeArchetype(TEXT("Mech Frame"), 300.f, 18.f, 250.f, 1.40f, 360.f, 90, Hue, 0.6f, 1.35f));
			Loadout.Add(MakeArchetype(TEXT("Railspear"), 60.f, 30.f, 340.f, 1.20f, 480.f, 50, Hue, 1.7f, 0.75f));
			break;
		}

		return Loadout;
	}

	TArray<FMinionArchetype> BuildCivLoadout(int32 Civilization)
	{
		const int32 NormalizedCivilization = SpiritsCiv::Clamp(Civilization);
		return BuildCivLoadout(static_cast<ECivilization>(NormalizedCivilization));
	}

	int32 NormalizeMapIndex(int32 MapIndex)
	{
		return FMath::Clamp(MapIndex, MinMapIndex, MaxMapIndex);
	}

	FMapStyleHooks ResolveMapStyle(int32 MapIndex)
	{
		FMapStyleHooks Result;
		Result.MapIndex = NormalizeMapIndex(MapIndex);
		if (Result.MapIndex == 0)
		{
			Result.Style = TEXT("Void");
			Result.GroundHook = TEXT("/Game/Textures/Arenas/Void/Arena_Void_ground");
			Result.SkyHook = TEXT("/Game/Textures/Arenas/Void/Arena_Void_sky");
		}
		else
		{
			Result.Style = TEXT("Sands");
			Result.GroundHook = TEXT("/Game/Textures/Arenas/Sands/Arena_Sands_ground");
			Result.SkyHook = TEXT("/Game/Textures/Arenas/Sands/Arena_Sands_sky");
		}
		return Result;
	}

	FSummonValidation ValidateSummon(
		const FMatchSettings& Settings,
		const TArray<FMinionArchetype>& TeamLoadout,
		int32 ArchetypeIndex,
		int32 Souls,
		bool bSpawnLocationValid)
	{
		FSummonValidation Result;
		if (Settings.Phase != ESpiritsMatchPhase::InProgress)
		{
			Result.FailureCode = FailureCodes::InvalidPhase;
			return Result;
		}
		if (TeamLoadout.Num() != ArchetypesPerCivilization)
		{
			Result.FailureCode = FailureCodes::InvalidLoadout;
			return Result;
		}
		if (!TeamLoadout.IsValidIndex(ArchetypeIndex))
		{
			Result.FailureCode = FailureCodes::InvalidIndex;
			return Result;
		}
		if (Souls < 0)
		{
			Result.FailureCode = FailureCodes::InvalidSouls;
			return Result;
		}
		const FMinionArchetype& Archetype = TeamLoadout[ArchetypeIndex];
		if (Archetype.SummonCost < 0)
		{
			Result.FailureCode = FailureCodes::InvalidLoadout;
			return Result;
		}
		if (Souls < Archetype.SummonCost)
		{
			Result.Cost = Archetype.SummonCost;
			Result.FailureCode = FailureCodes::InsufficientSouls;
			return Result;
		}
		if (!bSpawnLocationValid)
		{
			Result.Cost = Archetype.SummonCost;
			Result.FailureCode = FailureCodes::InvalidLocation;
			return Result;
		}

		Result.bAccepted = true;
		Result.Cost = Archetype.SummonCost;
		return Result;
	}

	FSummonTransactionState BeginSummonTransaction(
		const FSummonValidation& Validation,
		int32 SoulsBefore,
		const FString& TransactionToken)
	{
		FSummonTransactionState State;
		State.TransactionToken = TransactionToken;
		State.SoulsBefore = SoulsBefore;
		State.SoulsAfter = SoulsBefore;
		State.bCostDeducted = Validation.bAccepted;
		if (Validation.bAccepted)
		{
			State.SoulsAfter = SoulsBefore - Validation.Cost;
		}
		return State;
	}

	FSummonTransactionResult EvaluateSummonTransaction(
		const FSummonValidation& Validation,
		const FSummonTransactionState& PreviousState,
		bool bSpawnSucceeded)
	{
		FSummonTransactionResult Result;
		Result.TransactionToken = PreviousState.TransactionToken;
		Result.State = PreviousState;
		Result.SoulsBefore = PreviousState.SoulsBefore;
		Result.SoulsAfter = PreviousState.SoulsAfter;
		Result.FailureCode = Validation.FailureCode;

		if (!Validation.bAccepted)
		{
			Result.bFailureIndicated = !Result.FailureCode.IsEmpty();
			return Result;
		}

		if (PreviousState.bSettled)
		{
			Result.bAlreadySettled = true;
			Result.bSpawned = PreviousState.bSpawned;
			Result.bRefundApplied = PreviousState.bRefundApplied;
			if (PreviousState.bRefundApplied)
			{
				Result.FailureCode = FailureCodes::SpawnFailedRefunded;
			}
			Result.bFailureIndicated = !Result.FailureCode.IsEmpty();
			return Result;
		}

		if (bSpawnSucceeded)
		{
			Result.bSpawned = true;
			Result.State.bSpawned = true;
			Result.State.bSettled = true;
			Result.FailureCode.Reset();
			return Result;
		}

		Result.bRefundApplied = true;
		Result.bRefundEventEmitted = true;
		Result.bFailureIndicated = true;
		Result.FailureCode = FailureCodes::SpawnFailedRefunded;
		Result.State.SoulsAfter = PreviousState.SoulsBefore;
		Result.SoulsAfter = Result.State.SoulsAfter;
		Result.State.bRefundApplied = true;
		Result.State.bSettled = true;
		return Result;
	}

	FSummonTransactionResult EvaluateSummonTransaction(
		const FSummonValidation& Validation,
		int32 SoulsBefore,
		bool bSpawnSucceeded)
	{
		const FSummonTransactionState State = BeginSummonTransaction(
			Validation, SoulsBefore, TEXT("legacy-summon-transaction"));
		return EvaluateSummonTransaction(Validation, State, bSpawnSucceeded);
	}

	FHeavyAttackResult EvaluateHeavyAttack(
		float BaseDamage,
		float BaseKnockbackMagnitude,
		bool bCanAttack,
		float CancellationTimeSeconds)
	{
		FHeavyAttackResult Result;
		if (!bCanAttack || BaseDamage <= 0.f || BaseKnockbackMagnitude < 0.f)
		{
			return Result;
		}

		Result.bAccepted = true;
		const bool bCancelledBeforeResolve =
			CancellationTimeSeconds >= 0.f && CancellationTimeSeconds < HeavyAttackWindupSeconds;
		if (bCancelledBeforeResolve)
		{
			Result.ResolveTime = CancellationTimeSeconds;
			return Result;
		}

		Result.bHit = true;
		Result.ResolveTime = HeavyAttackWindupSeconds;
		Result.Damage = BaseDamage * HeavyAttackDamageMultiplier;
		Result.KnockbackMagnitude = BaseKnockbackMagnitude * HeavyAttackKnockbackMultiplier;
		Result.HitStopSeconds = HeavyAttackHitStopSeconds;
		return Result;
	}

	FDifficultyTuning ResolveDifficultyTuning(int32 Difficulty)
	{
		FDifficultyTuning Result;
		Result.Difficulty = FMath::Clamp(Difficulty, MinDifficulty, MaxDifficulty);
		switch (Result.Difficulty)
		{
		case 0:
			Result.AIWaveInterval = 40.f;
			Result.MaxWaveSize = 4;
			Result.SoulsPerSecond = 4;
			break;
		case 2:
			Result.AIWaveInterval = 22.f;
			Result.MaxWaveSize = 8;
			Result.SoulsPerSecond = 3;
			break;
		default:
			break;
		}
		return Result;
	}

	bool ShouldRunAIWaves(
		ESpiritsMatchPhase Phase,
		bool bHumanTeamBSeen,
		bool bTeamBHasHuman)
	{
		return Phase == ESpiritsMatchPhase::InProgress && !bHumanTeamBSeen && !bTeamBHasHuman;
	}

	bool CanResolveCombat(
		ESpiritsMatchPhase Phase,
		bool bAlive,
		bool bIsStructure)
	{
		return Phase == ESpiritsMatchPhase::InProgress && bAlive && !bIsStructure;
	}

	const TArray<FString>& GetAchievementIds()
	{
		static const TArray<FString> Ids =
		{
			AchievementIds::FirstWin,
			AchievementIds::WinEasy,
			AchievementIds::WinNormal,
			AchievementIds::WinHard,
			AchievementIds::PossessKill50,
			AchievementIds::Summon100,
			AchievementIds::WinAllCivilizations,
			AchievementIds::LanWin
		};
		return Ids;
	}

	FString GetAchievementId(EAchievementId Id)
	{
		const TArray<FString>& Ids = GetAchievementIds();
		const uint8 Index = static_cast<uint8>(Id);
		return Ids.IsValidIndex(Index) ? Ids[Index] : FString();
	}

	FAchievementEventRouter::FAchievementEventRouter(IAchievementBackend& InBackend)
		: Backend(InBackend)
	{
	}

	FString FAchievementEventRouter::MakeDedupKey(const FString& OwnerId, const FString& AchievementId)
	{
		return OwnerId + TEXT("\n") + AchievementId;
	}

	void FAchievementEventRouter::RecordFallback(
		const FString& OwnerId,
		const FString& AchievementId,
		const FString& Code)
	{
		FAchievementLocalRecord Record;
		Record.AchievementId = AchievementId;
		Record.OwnerId = OwnerId;
		Record.Code = Code;
		Record.bFallback = true;
		LocalRecords.Add(Record);
		Backend.RecordFallback(Record);
	}

	bool FAchievementEventRouter::EnsureDefinitions(const FString& OwnerId)
	{
		if (FailedQueries.Contains(OwnerId))
		{
			return false;
		}
		if (QueriedUsers.Contains(OwnerId))
		{
			return true;
		}

		TSet<FString> Definitions;
		QueriedUsers.Add(OwnerId);
		if (!Backend.QueryDefinitions(OwnerId, Definitions))
		{
			FailedQueries.Add(OwnerId);
			return false;
		}

		DefinitionsByUser.Add(OwnerId, MoveTemp(Definitions));
		return true;
	}

	void FAchievementEventRouter::RequestUnlock(const FString& OwnerId, const FString& AchievementId)
	{
		if (!GetAchievementIds().Contains(AchievementId))
		{
			RecordFallback(OwnerId, AchievementId, TEXT("Steam.UnknownAchievementId"));
			return;
		}

		const FString DedupKey = MakeDedupKey(OwnerId, AchievementId);
		if (AttemptedUnlocks.Contains(DedupKey))
		{
			return;
		}
		AttemptedUnlocks.Add(DedupKey);

		FAchievementUnlockRequest Intent;
		Intent.AchievementId = AchievementId;
		Intent.OwnerId = OwnerId;
		UnlockIntents.Add(Intent);

		if (OwnerId.IsEmpty() || !Backend.IsIdentityAvailable(OwnerId))
		{
			RecordFallback(OwnerId, AchievementId, TEXT("Steam.IdentityUnavailable"));
			return;
		}
		if (!EnsureDefinitions(OwnerId))
		{
			RecordFallback(OwnerId, AchievementId, TEXT("Steam.DefinitionQueryFailed"));
			return;
		}

		const TSet<FString>* Definitions = DefinitionsByUser.Find(OwnerId);
		if (Definitions == nullptr || !Definitions->Contains(AchievementId))
		{
			RecordFallback(OwnerId, AchievementId, TEXT("Steam.UnknownAchievementId"));
			return;
		}

		FAchievementUnlockRequest& StoredIntent = UnlockIntents.Last();
		StoredIntent.bDefinitionKnown = true;
		if (Backend.WriteAchievement(OwnerId, AchievementId))
		{
			StoredIntent.bAlreadyWrittenThisSession = true;
			return;
		}

		RecordFallback(OwnerId, AchievementId, TEXT("Steam.WriteFailed"));
	}

	void FAchievementEventRouter::ProcessEvent(const FAchievementEvent& Event)
	{
		FUserProgress& Progress = ProgressByUser.FindOrAdd(Event.OwnerId);
		switch (Event.Type)
		{
		case EAchievementEventType::Win:
			RequestUnlock(Event.OwnerId, AchievementIds::FirstWin);
			switch (FMath::Clamp(Event.Difficulty, MinDifficulty, MaxDifficulty))
			{
			case 0: RequestUnlock(Event.OwnerId, AchievementIds::WinEasy); break;
			case 2: RequestUnlock(Event.OwnerId, AchievementIds::WinHard); break;
			default: RequestUnlock(Event.OwnerId, AchievementIds::WinNormal); break;
			}
			if (Event.bLan)
			{
				RequestUnlock(Event.OwnerId, AchievementIds::LanWin);
			}
			{
				const int32 Civilization = FMath::Clamp(Event.Civilization, 0, Civilizations - 1);
				const uint8 PreviousMask = Progress.CivWinMask;
				Progress.CivWinMask |= static_cast<uint8>(1u << Civilization);
				if (PreviousMask != 0x0F && Progress.CivWinMask == 0x0F)
				{
					RequestUnlock(Event.OwnerId, AchievementIds::WinAllCivilizations);
				}
			}
			break;

		case EAchievementEventType::PossessionKill:
			++Progress.PossessKills;
			if (Progress.PossessKills == 50)
			{
				RequestUnlock(Event.OwnerId, AchievementIds::PossessKill50);
			}
			break;

		case EAchievementEventType::Summon:
			++Progress.Summons;
			if (Progress.Summons == 100)
			{
				RequestUnlock(Event.OwnerId, AchievementIds::Summon100);
			}
			break;

		case EAchievementEventType::Unlock:
			RequestUnlock(Event.OwnerId, Event.AchievementId);
			break;
		}
	}

	FAchievementBackendReadiness EvaluateAchievementBackendReadiness(
		const FAchievementBackendProbe& Probe)
	{
		FAchievementBackendReadiness Result;
		Result.bDevelopmentFallbackPass = true;
		Result.bSteamReleaseAcceptance = false;

		// 0 and 480 are never release-valid. A non-placeholder ID must also be
		// explicitly listed by the release environment as approved.
		const bool bAppIdApproved =
			Probe.AppId > 0 &&
			Probe.AppId != 480 &&
			Probe.ApprovedAppIds.Contains(Probe.AppId);
		if (!bAppIdApproved)
		{
			Result.State = EAchievementBackendState::Disabled;
			Result.FailureCode = TEXT("Steam.AppIdInvalid");
			return Result;
		}

		Result.State = EAchievementBackendState::ConfigValid;
		if (!Probe.bConfigEnabled || !Probe.bOSSAvailable)
		{
			Result.FailureCode = TEXT("Steam.SubsystemUnavailable");
			return Result;
		}

		Result.State = EAchievementBackendState::OSSReady;
		if (!Probe.bIdentityAvailable)
		{
			Result.FailureCode = TEXT("Steam.IdentityUnavailable");
			return Result;
		}

		Result.bIdentityAvailable = true;
		Result.State = EAchievementBackendState::IdentityReady;
		if (!Probe.bDefinitionsQuerySucceeded)
		{
			Result.FailureCode = TEXT("Steam.DefinitionQueryFailed");
			return Result;
		}

		Result.bDefinitionsAvailable = true;
		Result.bDevelopmentFallbackPass = false;
		Result.State = EAchievementBackendState::DefinitionsReady;
		Result.State = EAchievementBackendState::WriteEligible;
		Result.FailureCode.Reset();
		return Result;
	}
}
