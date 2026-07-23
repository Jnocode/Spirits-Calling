#include "SpiritsGameMode.h"

#include "EngineUtils.h"
#include "ArenaBuilder.h"
#include "Engine/World.h"
#include "GameFramework/PlayerStart.h"
#include "Kismet/GameplayStatics.h"
#include "SoulShrine.h"
#include "SpiritPawn.h"
#include "SpiritsGameState.h"
#include "SpiritsHUD.h"
#include "SpiritsPlayerController.h"
#include "SpiritsPlayerState.h"
#include "SpiritVRPawn.h"
#include "SpiritsRules.h"
#include "TimerManager.h"
#include "UnitBase.h"

// Main-menu difficulty selection (host authoritative): 0 Easy, 1 Normal, 2 Hard.
int32 GSpiritsDifficulty = 1;

// Main-menu civilization selection (host authoritative). Defaults to an
// asymmetric matchup so single-player already showcases the differences.
int32 GSpiritsCivTeamA = static_cast<int32>(ECivilization::East);   // player
int32 GSpiritsCivTeamB = static_cast<int32>(ECivilization::Norse);  // AI / red

// Main-menu battlefield selection: 0 = Void (night), 1 = Sands (day).
int32 GSpiritsMapIndex = 0;

ASpiritsGameMode::ASpiritsGameMode()
{
	GameStateClass = ASpiritsGameState::StaticClass();
	PlayerStateClass = ASpiritsPlayerState::StaticClass();
	PlayerControllerClass = ASpiritsPlayerController::StaticClass();
	HUDClass = ASpiritsHUD::StaticClass();
	DefaultPawnClass = ASpiritPawn::StaticClass();

	UnitClass = AUnitBase::StaticClass();
	ShrineClass = ASoulShrine::StaticClass();
	PCSpiritPawnClass = ASpiritPawn::StaticClass();
	VRSpiritPawnClass = ASpiritVRPawn::StaticClass();

	// Fully playable without any Data Assets: build both teams' civilization
	// loadouts from the current selection (menu-driven, sane defaults).
	RebuildLoadouts();
}

void ASpiritsGameMode::BuildCivLoadout(int32 Civ, TArray<FMinionArchetype>& Out) const
{
	Out = SpiritsRules::BuildCivLoadout(Civ);
}

void ASpiritsGameMode::RebuildLoadouts()
{
	BuildCivLoadout(GSpiritsCivTeamA, SummonOptions);
	BuildCivLoadout(GSpiritsCivTeamB, SummonOptionsB);
}

void ASpiritsGameMode::InitGameState()
{
	Super::InitGameState();

	// Reflect the latest main-menu civilization choice (globals may have changed
	// after construction) and publish both teams' lists to clients for their HUDs.
	RebuildLoadouts();

	if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
	{
		PublishMatchSnapshot(GS);
	}
}

void ASpiritsGameMode::PublishMatchSnapshot(ASpiritsGameState* GS)
{
	if (!GS || !HasAuthority())
	{
		return;
	}

	GSpiritsDifficulty = FMath::Clamp(GSpiritsDifficulty, SpiritsRules::MinDifficulty, SpiritsRules::MaxDifficulty);
	GSpiritsCivTeamA = SpiritsCiv::Clamp(GSpiritsCivTeamA);
	GSpiritsCivTeamB = SpiritsCiv::Clamp(GSpiritsCivTeamB);
	GSpiritsMapIndex = SpiritsRules::NormalizeMapIndex(GSpiritsMapIndex);

	RebuildLoadouts();
	GS->Difficulty = static_cast<uint8>(GSpiritsDifficulty);
	GS->TeamACivilization = static_cast<uint8>(GSpiritsCivTeamA);
	GS->TeamBCivilization = static_cast<uint8>(GSpiritsCivTeamB);
	GS->MapIndex = static_cast<uint8>(GSpiritsMapIndex);
	GS->SummonOptions = SummonOptions;
	GS->SummonOptionsB = SummonOptionsB;
	GS->MatchGeneration = MatchGeneration;
}

void ASpiritsGameMode::BeginPlay()
{
	Super::BeginPlay();

	CleanupLegacyActors();

	// Give the procedurally-built arena time to register its collision. StartBattle
	// retries until the authoritative arena reports ready instead of entering a
	// match against an ungrounded or non-colliding arena.
	GetWorldTimerManager().SetTimer(StartBattleTimerHandle, this, &ASpiritsGameMode::StartBattle, 0.3f, false);
}

void ASpiritsGameMode::StartBattle()
{
	if (!HasAuthority())
	{
		return;
	}

	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	if (!GS || GS->Phase != ESpiritsMatchPhase::WaitingToStart)
	{
		return;
	}

	bool bArenaReady = false;
	for (TActorIterator<AArenaBuilder> It(GetWorld()); It; ++It)
	{
		bArenaReady = It->IsCollisionReady();
		if (bArenaReady)
		{
			break;
		}
	}
	if (!bArenaReady)
	{
		GetWorldTimerManager().SetTimer(StartBattleTimerHandle, this, &ASpiritsGameMode::StartBattle, 0.1f, false);
		return;
	}

	PublishMatchSnapshot(GS);
	GSpiritsDifficulty = GS->Difficulty;
	GS->WinningTeam = SpiritsTeams::NoTeam;
	GS->CurrentWave = 0;
	GS->NextWaveTime = 0.f;
	bEndMatchProcessed = false;

	const SpiritsRules::FDifficultyTuning DifficultyTuning =
		SpiritsRules::ResolveDifficultyTuning(GSpiritsDifficulty);
	GSpiritsDifficulty = DifficultyTuning.Difficulty;
	GS->Difficulty = static_cast<uint8>(DifficultyTuning.Difficulty);
	AIWaveInterval = DifficultyTuning.AIWaveInterval;
	MaxWaveSize = DifficultyTuning.MaxWaveSize;
	SoulsPerSecond = DifficultyTuning.SoulsPerSecond;

	SpawnShrines();

	GS->Phase = ESpiritsMatchPhase::InProgress;
	GS->ForceNetUpdate();
	GS->Multicast_Announce(TEXT("The battle begins — destroy the enemy shrine!"), FLinearColor(1.f, 0.82f, 0.35f));

	// Stable, greppable smoke marker for the packaged launch runner. It records a
	// runtime stage only; it is not a release Pass by itself.
	UE_LOG(LogTemp, Display, TEXT("[SpiritsSmoke] Stage=MatchInProgress"));

	GetWorldTimerManager().SetTimer(SoulTimerHandle, this, &ASpiritsGameMode::SoulIncomeTick, 1.f, true);
	bHumanTeamBSeen = HasHumanTeamB();
	if (!bHumanTeamBSeen)
	{
		GetWorldTimerManager().SetTimer(WaveStartTimerHandle, this, &ASpiritsGameMode::MaybeStartAIWaves, 15.f, false);
	}
}

void ASpiritsGameMode::CleanupLegacyActors()
{
	// The old prototype map contains placeholder BP_Orc actors — remove them.
	TArray<AActor*> ToDestroy;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->GetName().Contains(TEXT("BP_Orc")))
		{
			ToDestroy.Add(*It);
		}
	}
	for (AActor* Actor : ToDestroy)
	{
		Actor->Destroy();
	}
}

void ASpiritsGameMode::PostLogin(APlayerController* NewPlayer)
{
	Super::PostLogin(NewPlayer);

	if (ASpiritsPlayerState* PS = NewPlayer ? NewPlayer->GetPlayerState<ASpiritsPlayerState>() : nullptr)
	{
		PS->TeamId = static_cast<uint8>(NextTeamToAssign % 2);
		NextTeamToAssign++;

		// A human joined Team B: permanently stop every pending/future AI wave
		// for this match, including the initial 15-second start timer.
		if (PS->TeamId == SpiritsTeams::TeamB)
		{
			StopAIWavesForHumanTeamB();
			if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
			{
				GS->Multicast_Announce(TEXT("A challenger has joined the battle!"), FLinearColor(1.f, 0.82f, 0.35f));
			}
			UE_LOG(LogTemp, Log, TEXT("[Spirits] Team B human joined: AI waves permanently deactivated for this match."));
		}
	}
}

UClass* ASpiritsGameMode::GetDefaultPawnClassForController_Implementation(AController* InController)
{
	if (const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(InController))
	{
		if (PC->IsVRPlayer() && VRSpiritPawnClass)
		{
			return VRSpiritPawnClass;
		}
	}
	return PCSpiritPawnClass ? PCSpiritPawnClass.Get() : Super::GetDefaultPawnClassForController_Implementation(InController);
}

void ASpiritsGameMode::RegisterUnit(AUnitBase* Unit)
{
	if (Unit)
	{
		AllUnits.AddUnique(Unit);
	}
}

void ASpiritsGameMode::UnregisterUnit(AUnitBase* Unit)
{
	AllUnits.RemoveAll([Unit](const TWeakObjectPtr<AUnitBase>& Ptr)
	{
		return !Ptr.IsValid() || Ptr.Get() == Unit;
	});
}

void ASpiritsGameMode::NotifyUnitDied(AUnitBase* Unit, AController* Killer)
{
	if (!Unit)
	{
		return;
	}

	// Only a registered Soul Shrine is a victory objective. A generic actor
	// marked as structure must never end the match accidentally.
	ASoulShrine* ShrineObjective = Cast<ASoulShrine>(Unit);
	if (ShrineObjective && Shrines.Contains(ShrineObjective))
	{
		EndMatch(Unit->TeamId == SpiritsTeams::TeamA ? SpiritsTeams::TeamB : SpiritsTeams::TeamA);
		return;
	}

	// Reward the killer's team.
	uint8 KillerTeam = SpiritsTeams::NoTeam;
	if (Killer)
	{
		if (const AUnitBase* KillerUnit = Cast<AUnitBase>(Killer->GetPawn()))
		{
			KillerTeam = KillerUnit->TeamId;
		}
		else if (const ASpiritsPlayerState* KillerPS = Killer->GetPlayerState<ASpiritsPlayerState>())
		{
			KillerTeam = KillerPS->TeamId;
		}
	}

	if (KillerTeam != SpiritsTeams::NoTeam && GameState)
	{
		for (APlayerState* PS : GameState->PlayerArray)
		{
			ASpiritsPlayerState* SPS = Cast<ASpiritsPlayerState>(PS);
			if (SPS && SPS->TeamId == KillerTeam)
			{
				SPS->AddSouls(KillReward);
			}
		}
	}

	// Hero moment pays: a possessing player's own kill grants a personal bonus.
	if (Killer && Killer->IsPlayerController())
	{
		if (ASpiritsPlayerState* KillerPS = Killer->GetPlayerState<ASpiritsPlayerState>())
		{
			KillerPS->AddSouls(15);
		}

		// Achievement: only count kills scored while driving a possessed unit.
		if (Cast<AUnitBase>(Killer->GetPawn()))
		{
			if (ASpiritsPlayerController* KPC = Cast<ASpiritsPlayerController>(Killer))
			{
				KPC->Client_ReportPossessKill();
			}
		}
	}

	// Kill feed
	if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
	{
		const TCHAR* VictimTeam = (Unit->TeamId == SpiritsTeams::TeamA) ? TEXT("Blue") : TEXT("Red");
		GS->Multicast_KillFeed(
			FString::Printf(TEXT("%s %s destroyed  (+%d souls)"), VictimTeam, *Unit->Stats.DisplayName, KillReward),
			SpiritsTeams::GetTeamColor(Unit->TeamId) * 1.3f);
	}
}

AUnitBase* ASpiritsGameMode::SpawnUnitForPlayer(ASpiritsPlayerController* PC, int32 ArchetypeIndex, const FVector& Location)
{
	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;
	const TArray<FMinionArchetype>& Loadout = LoadoutForTeam(PS ? PS->TeamId : SpiritsTeams::TeamA);

	if (!PC || !PS || !GS)
	{
		if (PC)
		{
			PC->Client_SummonFailed(SpiritsRules::FailureCodes::InvalidPhase);
		}
		return nullptr;
	}

	const SpiritsRules::FMatchSettings Settings{
		GS->Phase,
		GS->Difficulty,
		GS->MapIndex,
		static_cast<ECivilization>(GS->TeamACivilization),
		static_cast<ECivilization>(GS->TeamBCivilization),
		GetNetMode() != NM_Standalone};
	const bool bLocationValid = IsValidSummonLocation(Location, PS->TeamId, 96.f);
	const SpiritsRules::FSummonValidation Validation = SpiritsRules::ValidateSummon(
		Settings, Loadout, ArchetypeIndex, PS->Souls, bLocationValid);
	if (!Validation.bAccepted)
	{
		PC->Client_SummonFailed(Validation.FailureCode);
		return nullptr;
	}

	const FString TransactionToken = FString::Printf(
		TEXT("summon-%d-%s-%llu"), MatchGeneration, *PC->GetName(), ++SummonTransactionCounter);
	if (SettledSummonTransactions.Contains(TransactionToken))
	{
		PC->Client_SummonFailed(TEXT("Summon.TransactionAlreadySettled"));
		return nullptr;
	}

	const FMinionArchetype& Arch = Loadout[ArchetypeIndex];
	const SpiritsRules::FSummonTransactionState InitialState = SpiritsRules::BeginSummonTransaction(
		Validation, PS->Souls, TransactionToken);
	if (!PS->TrySpendSouls(Validation.Cost))
	{
		PC->Client_SummonFailed(SpiritsRules::FailureCodes::InsufficientSouls);
		return nullptr;
	}

	AUnitBase* Unit = SpawnUnitForTeam(ArchetypeIndex, PS->TeamId, Location);
	const SpiritsRules::FSummonTransactionResult Result = SpiritsRules::EvaluateSummonTransaction(
		Validation, InitialState, Unit != nullptr);
	SettledSummonTransactions.Add(TransactionToken);

	if (!Unit)
	{
		if (Result.bRefundEventEmitted)
		{
			PS->AddSouls(Arch.SummonCost);
		}
		PC->Client_SummonFailed(Result.FailureCode.IsEmpty()
			? SpiritsRules::FailureCodes::SpawnFailedRefunded
			: Result.FailureCode);
		return nullptr;
	}

	PC->Client_ReportSummon(); // achievement progress (owning client only)
	return Unit;
}

AUnitBase* ASpiritsGameMode::SpawnUnitForTeam(int32 ArchetypeIndex, uint8 TeamId, const FVector& Location)
{
	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	const TArray<FMinionArchetype>& Loadout = LoadoutForTeam(TeamId);
	if (!Loadout.IsValidIndex(ArchetypeIndex) || !UnitClass)
	{
		return nullptr;
	}

	const FVector SpawnLoc = ProjectToGround(Location, 96.f);
	const FTransform SpawnTM(FRotator::ZeroRotator, SpawnLoc);

	AUnitBase* Unit = GetWorld()->SpawnActorDeferred<AUnitBase>(
		UnitClass, SpawnTM, nullptr, nullptr,
		ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButDontSpawnIfColliding);
	const ECivilization Civilization = (TeamId == SpiritsTeams::TeamB)
		? static_cast<ECivilization>(SpiritsCiv::Clamp(GS ? GS->TeamBCivilization : GSpiritsCivTeamB))
		: static_cast<ECivilization>(SpiritsCiv::Clamp(GS ? GS->TeamACivilization : GSpiritsCivTeamA));
	if (Unit)
	{
		Unit->InitUnit(Loadout[ArchetypeIndex], TeamId, Civilization);
		Unit->FinishSpawning(SpawnTM);
		if (!IsValid(Unit) || Unit->IsActorBeingDestroyed())
		{
			return nullptr;
		}
	}
	return Unit;
}

void ASpiritsGameMode::SetPlayerVRMode(ASpiritsPlayerController* PC, bool bVR)
{
	if (!PC || PC->IsVRPlayer() == bVR)
	{
		return;
	}
	PC->SetVRPlayer(bVR);

	// Only swap the pawn if the player is still in spirit form (not possessing a unit).
	APawn* Current = PC->GetPawn();
	if (Current && !Current->IsA<AUnitBase>())
	{
		PC->UnPossess();
		Current->Destroy();
		RestartPlayer(PC);
	}
}

void ASpiritsGameMode::EndMatch(uint8 InWinningTeam)
{
	if (!HasAuthority() || bEndMatchProcessed)
	{
		return;
	}

	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	if (!GS || GS->Phase != ESpiritsMatchPhase::InProgress)
	{
		return;
	}

	bEndMatchProcessed = true;
	// Publish the winner before Ended so clients never need to render an Ended
	// snapshot with the transient NoTeam value.
	GS->WinningTeam = (InWinningTeam == SpiritsTeams::TeamB) ? SpiritsTeams::TeamB : SpiritsTeams::TeamA;
	GS->Phase = ESpiritsMatchPhase::Ended;

	// Ended is an authority barrier: no queued heavy strike or hit-stop may
	// resolve after the winner has been published.
	for (const TWeakObjectPtr<AUnitBase>& Unit : AllUnits)
	{
		if (Unit.IsValid())
		{
			Unit->CancelPendingCombat();
		}
	}

	GetWorldTimerManager().ClearTimer(SoulTimerHandle);
	GetWorldTimerManager().ClearTimer(WaveTimerHandle);
	GetWorldTimerManager().ClearTimer(WaveStartTimerHandle);
	GetWorldTimerManager().ClearTimer(StartBattleTimerHandle);
	bAIWavesActive = false;
	GS->NextWaveTime = 0.f;
	GS->ForceNetUpdate();

	// Achievements: notify each human on the winning team (owning client unlocks locally).
	const int32 WinnerCiv = (GS->WinningTeam == SpiritsTeams::TeamB) ? GS->TeamBCivilization : GS->TeamACivilization;
	const bool bLan = (GetNetMode() != NM_Standalone);
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(It->Get());
		const ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;
		if (PC && PS && PS->TeamId == GS->WinningTeam)
		{
			PC->Client_ReportWin(GS->Difficulty, WinnerCiv, bLan);
		}
	}

	GS->Multicast_Announce(
		GS->WinningTeam == SpiritsTeams::TeamA ? TEXT("Blue team wins!") : TEXT("Red team wins!"),
		FLinearColor(1.f, 0.82f, 0.25f));
	UE_LOG(LogTemp, Log, TEXT("[Spirits] Match ended exactly once. Winning team: %d"), GS->WinningTeam);
}

void ASpiritsGameMode::RequestRestartMatch(ASpiritsPlayerController* RequestingPC)
{
	if (!HasAuthority() || !RequestingPC || !bEndMatchProcessed)
	{
		return;
	}
	ResetMatchState();
	// Keep WaitingToStart observable to connected clients and let the same
	// collision-readiness gate used for the first match start the next round.
	GetWorldTimerManager().SetTimer(StartBattleTimerHandle, this, &ASpiritsGameMode::StartBattle, 0.1f, false);
}

void ASpiritsGameMode::ResetMatchState()
{
	if (!HasAuthority())
	{
		return;
	}

	GetWorldTimerManager().ClearTimer(SoulTimerHandle);
	GetWorldTimerManager().ClearTimer(WaveTimerHandle);
	GetWorldTimerManager().ClearTimer(WaveStartTimerHandle);
	GetWorldTimerManager().ClearTimer(StartBattleTimerHandle);

	// A match can end while a player is possessing a unit. Return every player
	// to a valid spirit pawn before destroying the old match actors; otherwise
	// the controller may retain a stale possessed-pawn reference in the next
	// generation.
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(It->Get()))
		{
			PC->ServerReturnToSpirit();
		}
	}

	TSet<AActor*> ActorsToDestroy;
	for (const TWeakObjectPtr<AUnitBase>& Unit : AllUnits)
	{
		if (Unit.IsValid())
		{
			ActorsToDestroy.Add(Unit.Get());
		}
	}
	for (const TObjectPtr<ASoulShrine>& Shrine : Shrines)
	{
		if (Shrine)
		{
			ActorsToDestroy.Add(Shrine.Get());
		}
	}
	for (AActor* Actor : ActorsToDestroy)
	{
		Actor->Destroy();
	}
	AllUnits.Reset();
	Shrines.Reset();

	bAIWavesActive = false;
	// A disconnected Team B player permits AI in the next generation; a player
	// who remains connected continues to suppress it.
	bHumanTeamBSeen = HasHumanTeamB();
	bEndMatchProcessed = false;
	SettledSummonTransactions.Reset();
	WaveNumber = 0;
	++MatchGeneration;
	LastShrineWarnTime[0] = -100.f;
	LastShrineWarnTime[1] = -100.f;

	if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
	{
		GS->Phase = ESpiritsMatchPhase::WaitingToStart;
		GS->WinningTeam = SpiritsTeams::NoTeam;
		GS->CurrentWave = 0;
		GS->NextWaveTime = 0.f;
		PublishMatchSnapshot(GS);
		GS->ForceNetUpdate();
	}

	if (GameState)
	{
		for (APlayerState* PS : GameState->PlayerArray)
		{
			if (ASpiritsPlayerState* SPS = Cast<ASpiritsPlayerState>(PS))
			{
				SPS->Souls = 100;
			}
		}
	}
}

void ASpiritsGameMode::SpawnShrines()
{
	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	if (!ShrineClass)
	{
		return;
	}

	for (uint8 Team = 0; Team < 2; ++Team)
	{
		const FVector Base = FindGroundedBaseLocation(Team, 220.f);
		const FTransform TM(FRotator::ZeroRotator, Base);

		ASoulShrine* Shrine = GetWorld()->SpawnActorDeferred<ASoulShrine>(
			ShrineClass, TM, nullptr, nullptr,
			ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
		if (Shrine)
		{
			FMinionArchetype ShrineStats = Shrine->Stats;
			const ECivilization Civilization = (Team == SpiritsTeams::TeamB)
				? static_cast<ECivilization>(SpiritsCiv::Clamp(GS ? GS->TeamBCivilization : GSpiritsCivTeamB))
				: static_cast<ECivilization>(SpiritsCiv::Clamp(GS ? GS->TeamACivilization : GSpiritsCivTeamA));
			Shrine->InitUnit(ShrineStats, Team, Civilization);
			Shrine->FinishSpawning(TM);
			Shrines.Add(Shrine);
		}
	}
}

FVector ASpiritsGameMode::GetTeamBaseLocation(uint8 TeamId) const
{
	TArray<APlayerStart*> Starts;
	for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
	{
		Starts.Add(*It);
	}
	Starts.Sort([](const APlayerStart& A, const APlayerStart& B)
	{
		return A.GetName() < B.GetName();
	});

	if (Starts.Num() >= 2)
	{
		// Shrine sits behind each start, on opposite sides.
		return Starts[TeamId % Starts.Num()]->GetActorLocation();
	}

	FVector Center = FVector::ZeroVector;
	if (Starts.Num() == 1)
	{
		Center = Starts[0]->GetActorLocation();
	}
	const float Sign = (TeamId == SpiritsTeams::TeamA) ? -1.f : 1.f;
	return Center + FVector(Sign * FallbackBaseDistance, 0.f, 0.f);
}

bool ASpiritsGameMode::TraceGround(const FVector& Location, FVector& OutGroundPoint) const
{
	FHitResult Hit;
	const FVector TraceStart = Location + FVector(0.f, 0.f, 3000.f);
	const FVector TraceEnd = Location - FVector(0.f, 0.f, 10000.f);
	FCollisionQueryParams Params(FName(TEXT("SpiritsGroundProject")), false);

	if (GetWorld()->LineTraceSingleByChannel(Hit, TraceStart, TraceEnd, ECC_WorldStatic, Params))
	{
		OutGroundPoint = Hit.ImpactPoint;
		return true;
	}
	return false;
}

FVector ASpiritsGameMode::ProjectToGround(const FVector& Location, float HalfHeight) const
{
	FVector Ground;
	if (TraceGround(Location, Ground))
	{
		return Ground + FVector(0.f, 0.f, HalfHeight + 5.f);
	}
	return Location + FVector(0.f, 0.f, HalfHeight + 5.f);
}

bool ASpiritsGameMode::IsValidSummonLocation(const FVector& Location, uint8 TeamId, float HalfHeight) const
{
	(void)TeamId;
	if (!GetWorld() || Location.ContainsNaN() ||
		!FMath::IsFinite(Location.X) || !FMath::IsFinite(Location.Y) || !FMath::IsFinite(Location.Z) ||
		Location.SizeSquared2D() > FMath::Square(100000.f))
	{
		return false;
	}

	FVector Ground;
	if (!TraceGround(Location, Ground))
	{
		return false;
	}

	const FVector SpawnLocation = Ground + FVector(0.f, 0.f, HalfHeight + 5.f);
	const FCollisionShape Capsule = FCollisionShape::MakeCapsule(42.f, HalfHeight);
	FCollisionQueryParams Params(FName(TEXT("SpiritsSummonPlacement")), false);
	return !GetWorld()->OverlapBlockingTestByChannel(
		SpawnLocation, FQuat::Identity, ECC_Pawn, Capsule, Params);
}

FVector ASpiritsGameMode::FindGroundedBaseLocation(uint8 TeamId, float HalfHeight) const
{
	const FVector Desired = GetTeamBaseLocation(TeamId);

	// Direction from desired base back toward the opposite base (i.e. inward).
	const FVector Opposite = GetTeamBaseLocation(TeamId == SpiritsTeams::TeamA ? SpiritsTeams::TeamB : SpiritsTeams::TeamA);
	FVector Inward = (Opposite - Desired).GetSafeNormal2D();
	if (Inward.IsNearlyZero())
	{
		Inward = (TeamId == SpiritsTeams::TeamA) ? FVector(1.f, 0.f, 0.f) : FVector(-1.f, 0.f, 0.f);
	}

	// Walk inward until we find real ground (small maps: shrines end up near the floor edges).
	const float TotalDist = FVector::Dist2D(Desired, Opposite);
	const float Step = 250.f;
	for (float Offset = 0.f; Offset <= TotalDist * 0.5f - 200.f; Offset += Step)
	{
		const FVector Candidate = Desired + Inward * Offset;
		FVector Ground;
		if (TraceGround(Candidate, Ground))
		{
			return Ground + FVector(0.f, 0.f, HalfHeight + 5.f);
		}
	}

	// No ground anywhere along the line: give up and hover at the desired spot.
	return Desired + FVector(0.f, 0.f, HalfHeight + 5.f);
}

void ASpiritsGameMode::SoulIncomeTick()
{
	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	if (!GS || GS->Phase != ESpiritsMatchPhase::InProgress)
	{
		return;
	}

	// Comeback protection: a team whose shrine dropped below 50% earns +1/s.
	float ShrinePct[2] = { 1.f, 1.f };
	for (const TObjectPtr<ASoulShrine>& Shrine : Shrines)
	{
		if (Shrine && Shrine->TeamId < 2)
		{
			ShrinePct[Shrine->TeamId] = Shrine->GetHealthPercent();
		}
	}

	for (APlayerState* PS : GS->PlayerArray)
	{
		if (ASpiritsPlayerState* SPS = Cast<ASpiritsPlayerState>(PS))
		{
			const int32 Bonus = (SPS->TeamId < 2 && ShrinePct[SPS->TeamId] < 0.5f) ? 1 : 0;
			SPS->AddSouls(SoulsPerSecond + Bonus);
		}
	}
}

void ASpiritsGameMode::NotifyShrineDamaged(const AUnitBase* Shrine)
{
	if (!Shrine || Shrine->TeamId > 1)
	{
		return;
	}
	const float Now = GetWorld()->GetTimeSeconds();
	if (Now - LastShrineWarnTime[Shrine->TeamId] < 10.f)
	{
		return;
	}
	LastShrineWarnTime[Shrine->TeamId] = Now;

	if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
	{
		const TCHAR* Team = (Shrine->TeamId == SpiritsTeams::TeamA) ? TEXT("Blue") : TEXT("Red");
		GS->Multicast_Announce(FString::Printf(TEXT("%s shrine is under attack!"), Team),
		                       SpiritsTeams::GetTeamColor(Shrine->TeamId) * 1.5f, /*SoundId=*/1);
	}
}

bool ASpiritsGameMode::HasHumanTeamB() const
{
	if (!GameState)
	{
		return false;
	}
	for (APlayerState* PS : GameState->PlayerArray)
	{
		const ASpiritsPlayerState* SPS = Cast<ASpiritsPlayerState>(PS);
		if (SPS && SPS->TeamId == SpiritsTeams::TeamB)
		{
			return true;
		}
	}
	return false;
}

void ASpiritsGameMode::StopAIWavesForHumanTeamB()
{
	bHumanTeamBSeen = true;
	bAIWavesActive = false;
	GetWorldTimerManager().ClearTimer(WaveStartTimerHandle);
	GetWorldTimerManager().ClearTimer(WaveTimerHandle);
	if (ASpiritsGameState* GS = GetGameState<ASpiritsGameState>())
	{
		GS->NextWaveTime = 0.f;
	}
}

void ASpiritsGameMode::MaybeStartAIWaves()
{
	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	const bool bTeamBHasHuman = HasHumanTeamB();
	if (!GS || !SpiritsRules::ShouldRunAIWaves(GS->Phase, bHumanTeamBSeen, bTeamBHasHuman))
	{
		if (bTeamBHasHuman)
		{
			StopAIWavesForHumanTeamB();
		}
		return;
	}

	bAIWavesActive = true;
	SpawnAIWave();
	if (bAIWavesActive)
	{
		GetWorldTimerManager().SetTimer(WaveTimerHandle, this, &ASpiritsGameMode::SpawnAIWave, AIWaveInterval, true);
		UE_LOG(LogTemp, Log, TEXT("[Spirits] Single-player detected: enemy AI waves activated."));
	}
}

void ASpiritsGameMode::SpawnAIWave()
{
	// The timer can already be queued when a Team B human joins. Re-check the
	// authoritative guard inside the callback so ClearTimer is not our only
	// protection against a stale same-frame wave.
	if (!HasAuthority() || !bAIWavesActive)
	{
		return;
	}

	ASpiritsGameState* GS = GetGameState<ASpiritsGameState>();
	const bool bTeamBHasHuman = HasHumanTeamB();
	if (!GS || !bAIWavesActive ||
		!SpiritsRules::ShouldRunAIWaves(GS->Phase, bHumanTeamBSeen, bTeamBHasHuman) ||
		SummonOptionsB.Num() == 0)
	{
		if (bTeamBHasHuman)
		{
			StopAIWavesForHumanTeamB();
		}
		return;
	}

	// Pressure curve: waves grow over time (2, 2, 3, 3, 4 ... capped at 6).
	WaveNumber++;
	const int32 WaveSize = FMath::Min(AIWaveSize + (WaveNumber - 1) / 2, MaxWaveSize);

	// Feed the HUD countdown and the mood/color script.
	GS->CurrentWave = static_cast<uint8>(FMath::Min(WaveNumber, 255));
	GS->NextWaveTime = GS->GetServerWorldTimeSeconds() + AIWaveInterval;

	GS->Multicast_Announce(FString::Printf(TEXT("Wave %d incoming! (%d enemies)"), WaveNumber, WaveSize),
	                       FLinearColor(1.f, 0.3f, 0.25f));

	// Spawn next to the red team's shrine (guaranteed to be on real ground).
	FVector Base = GetTeamBaseLocation(SpiritsTeams::TeamB);
	for (const TObjectPtr<ASoulShrine>& Shrine : Shrines)
	{
		if (Shrine && Shrine->TeamId == SpiritsTeams::TeamB)
		{
			Base = Shrine->GetActorLocation();
			break;
		}
	}

	for (int32 i = 0; i < WaveSize; ++i)
	{
		const FVector Offset(FMath::FRandRange(-350.f, 350.f), FMath::FRandRange(-350.f, 350.f), 0.f);
		// Later waves mix in tougher archetypes more often.
		const float EliteChance = FMath::Min(0.15f + WaveNumber * 0.06f, 0.55f);
		const int32 Archetype = (FMath::FRand() < EliteChance) ? FMath::RandRange(1, SummonOptionsB.Num() - 1) : 0;
		SpawnUnitForTeam(Archetype, SpiritsTeams::TeamB, Base + Offset);
	}
}
