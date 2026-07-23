#include "SpiritsGameState.h"

#include "ArenaBuilder.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Net/UnrealNetwork.h"
#include "SpiritsAudio.h"
#include "SpiritsHUD.h"
#include "SpiritsPlayerState.h"

ASpiritsGameState::ASpiritsGameState()
{
}

void ASpiritsGameState::BeginPlay()
{
	Super::BeginPlay();

	// Build the arena locally on every instance (deterministic layout, no replication needed).
	bool bHasArena = false;
	for (TActorIterator<AArenaBuilder> It(GetWorld()); It; ++It) { bHasArena = true; break; }
	if (!bHasArena)
	{
		GetWorld()->SpawnActor<AArenaBuilder>(AArenaBuilder::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
	}
	RefreshArenaPresentation();
}

void ASpiritsGameState::RefreshArenaPresentation()
{
	if (!GetWorld())
	{
		return;
	}

	for (TActorIterator<AArenaBuilder> It(GetWorld()); It; ++It)
	{
		It->ApplyMapIndex(MapIndex);
	}
}

void ASpiritsGameState::OnRep_Phase()
{
	if (Phase == ESpiritsMatchPhase::InProgress)
	{
		RouteToHUD(TEXT("The battle is in progress."), FLinearColor(1.f, 0.82f, 0.35f), false);
		// Stable, greppable smoke marker mirrored on replicated clients.
		UE_LOG(LogTemp, Display, TEXT("[SpiritsSmoke] Stage=MatchInProgress"));
	}
	else if (Phase == ESpiritsMatchPhase::Ended)
	{
		OnRep_WinningTeam();
	}
}

void ASpiritsGameState::OnRep_WinningTeam()
{
	if (Phase != ESpiritsMatchPhase::Ended)
	{
		return;
	}

	const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	const ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;
	const bool bWon = PS && PS->TeamId == WinningTeam;
	RouteToHUD(bWon ? TEXT("Victory! The enemy shrine has fallen.") : TEXT("Defeat. Your shrine has fallen."),
	           bWon ? FLinearColor(1.f, 0.82f, 0.25f) : FLinearColor(0.8f, 0.2f, 0.2f), false);
}

void ASpiritsGameState::OnRep_MapIndex()
{
	RefreshArenaPresentation();
}

void ASpiritsGameState::OnRep_MatchSnapshot()
{
	// The menu/HUD reads Difficulty, civilization IDs and the team-specific
	// loadout through this replicated GameState. Re-resolve the arena as well so
	// a client that receives the snapshot in a different order than MapIndex
	// still converges on the authoritative presentation without changing state.
	RefreshArenaPresentation();
}

void ASpiritsGameState::RouteToHUD(const FString& Message, const FLinearColor& Color, bool bKillFeed)
{
#if WITH_DEV_AUTOMATION_TESTS
	LastRoutedMessage = Message;
	bLastRouteWasKillFeed = bKillFeed;
#endif

	APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	ASpiritsHUD* HUD = PC ? Cast<ASpiritsHUD>(PC->GetHUD()) : nullptr;
	if (HUD)
	{
		if (bKillFeed)
		{
			HUD->AddKillFeed(Message, Color);
		}
		else
		{
			HUD->AddAnnouncement(Message, Color);
		}
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void ASpiritsGameState::ClearRouteCaptureForAutomation()
{
	LastRoutedMessage.Reset();
	bLastRouteWasKillFeed = false;
}
#endif

void ASpiritsGameState::Multicast_Announce_Implementation(const FString& Message, FLinearColor Color, uint8 SoundId)
{
	RouteToHUD(Message, Color, false);
	if (SoundId == 1)
	{
		SpiritsAudio::Play2D(this, TEXT("S_Alarm"), 0.7f);
	}
}

void ASpiritsGameState::Multicast_KillFeed_Implementation(const FString& Message, FLinearColor Color)
{
	RouteToHUD(Message, Color, true);
}

void ASpiritsGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASpiritsGameState, Phase);
	DOREPLIFETIME(ASpiritsGameState, WinningTeam);
	DOREPLIFETIME(ASpiritsGameState, Difficulty);
	DOREPLIFETIME(ASpiritsGameState, TeamACivilization);
	DOREPLIFETIME(ASpiritsGameState, TeamBCivilization);
	DOREPLIFETIME(ASpiritsGameState, MatchGeneration);
	DOREPLIFETIME(ASpiritsGameState, SummonOptions);
	DOREPLIFETIME(ASpiritsGameState, SummonOptionsB);
	DOREPLIFETIME(ASpiritsGameState, MapIndex);
	DOREPLIFETIME(ASpiritsGameState, CurrentWave);
	DOREPLIFETIME(ASpiritsGameState, NextWaveTime);
}
