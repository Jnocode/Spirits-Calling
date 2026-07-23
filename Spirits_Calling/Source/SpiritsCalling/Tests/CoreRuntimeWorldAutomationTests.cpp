#include "SpiritsCalling/SpiritsGameMode.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Blueprint/UserWidget.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerState.h"
#include "Misc/AutomationTest.h"
#include "SpiritsCalling/SpiritsGameState.h"
#include "SpiritsCalling/SpiritsHUDWidget.h"
#include "SpiritsCalling/SpiritsPlayerController.h"
#include "SpiritsCalling/SpiritsPlayerState.h"
#include "SpiritsCalling/UnitBase.h"

namespace
{
	struct FScopedSpiritsTestWorld
	{
		FScopedSpiritsTestWorld()
		{
			if (!GEngine)
			{
				return;
			}

			const FName WorldName = MakeUniqueObjectName(
				GetTransientPackage(), UWorld::StaticClass(), TEXT("SpiritsCoreRuntimeTestWorld"));
			FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::Game);
			World = UWorld::CreateWorld(EWorldType::Game, false, WorldName, GetTransientPackage());
			if (!World)
			{
				return;
			}
			World->AddToRoot();
			WorldContext.SetCurrentWorld(World);
		}

		~FScopedSpiritsTestWorld()
		{
			if (!World || !GEngine)
			{
				return;
			}
			if (World->HasBegunPlay())
			{
				World->EndPlay(EEndPlayReason::Quit);
			}
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
			World->RemoveFromRoot();
		}

		UWorld* World = nullptr;
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsCoreRuntimeWorldAutomationTest,
	"SpiritsCalling.Requirements.CoreRuntime.World lifecycle, restart, OnRep, and HUD presentation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsCoreRuntimeWorldAutomationTest::RunTest(const FString& Parameters)
{
	FScopedSpiritsTestWorld Fixture;
	UWorld* World = Fixture.World;
	if (!TestNotNull(TEXT("Transient game world is created"), World))
	{
		return false;
	}

	// The canonical civilization/arena textures and M_UnitBody/M_ArenaSurface
	// materials are now imported into /Game (committed source Content, required
	// by build_shipping.ps1's cook of DemoMap). ApplyVisuals therefore resolves
	// the BodyMID.PatternTex / SoulShrine.PatternTex hooks cleanly, so the prior
	// [Asset.MissingHook] / [Asset.MissingCookReference] failures must NOT fire.
	// If either error reappears, a required runtime asset regressed out of source.

	ASpiritsGameMode* GameMode = World->SpawnActor<ASpiritsGameMode>();
	ASpiritsGameState* GameState = World->SpawnActor<ASpiritsGameState>();
	if (!TestNotNull(TEXT("Spirits GameMode is spawned with authority"), GameMode) ||
		!TestNotNull(TEXT("Spirits GameState is spawned"), GameState))
	{
		return false;
	}
	GameMode->SetGameStateForAutomation(GameState);

	ASpiritsPlayerController* PlayerController = World->SpawnActor<ASpiritsPlayerController>();
	ASpiritsPlayerState* PlayerState = World->SpawnActor<ASpiritsPlayerState>();
	AUnitBase* RegisteredUnit = World->SpawnActor<AUnitBase>();
	if (!TestNotNull(TEXT("Restart requester is spawned"), PlayerController) ||
		!TestNotNull(TEXT("PlayerState is spawned"), PlayerState) ||
		!TestNotNull(TEXT("Registered unit is spawned"), RegisteredUnit))
	{
		return false;
	}

	GameState->AddPlayerState(PlayerState);
	PlayerState->Souls = 999;
	GameMode->RegisterUnit(RegisteredUnit);
	const int32 PreviousGeneration = GameState->MatchGeneration;
	GameState->Phase = ESpiritsMatchPhase::InProgress;
	GameState->WinningTeam = SpiritsTeams::NoTeam;
	GameState->CurrentWave = 4;
	GameState->NextWaveTime = 30.f;

	GameMode->EndMatch(SpiritsTeams::TeamA);
	TestEqual(TEXT("EndMatch publishes Ended"), GameState->Phase, ESpiritsMatchPhase::Ended);
	TestEqual(TEXT("EndMatch publishes winner before restart"), GameState->WinningTeam, SpiritsTeams::TeamA);

	GameMode->RequestRestartMatch(PlayerController);
	TestEqual(TEXT("Restart returns to WaitingToStart"), GameState->Phase, ESpiritsMatchPhase::WaitingToStart);
	TestEqual(TEXT("Restart clears winner"), GameState->WinningTeam, SpiritsTeams::NoTeam);
	TestEqual(TEXT("Restart clears wave number"), GameState->CurrentWave, static_cast<uint8>(0));
	TestEqual(TEXT("Restart clears next-wave time"), GameState->NextWaveTime, 0.f);
	TestTrue(TEXT("Restart advances match generation"), GameState->MatchGeneration > PreviousGeneration);
	TestEqual(TEXT("Restart restores player Souls"), PlayerState->Souls, 100);
	TestEqual(TEXT("Restart clears registered units"), GameMode->GetAllUnits().Num(), 0);
	TestTrue(TEXT("Restart destroys prior-generation unit"), RegisteredUnit->IsActorBeingDestroyed());
	TestEqual(TEXT("Restart republishes Team A loadout"), GameState->SummonOptions.Num(), 3);
	TestEqual(TEXT("Restart republishes Team B loadout"), GameState->SummonOptionsB.Num(), 3);

	GameState->ClearRouteCaptureForAutomation();
	GameState->Phase = ESpiritsMatchPhase::InProgress;
	GameState->OnRep_Phase();
	TestTrue(TEXT("InProgress OnRep routes announcement"),
		GameState->GetLastRoutedMessageForAutomation().Contains(TEXT("in progress")));
	TestFalse(TEXT("Phase announcement is not kill feed"), GameState->WasLastRouteKillFeedForAutomation());

	GameState->Phase = ESpiritsMatchPhase::Ended;
	GameState->WinningTeam = SpiritsTeams::TeamB;
	GameState->OnRep_WinningTeam();
	TestTrue(TEXT("Ended OnRep routes deterministic result"),
		GameState->GetLastRoutedMessageForAutomation().Contains(TEXT("Defeat")));
	GameState->Multicast_KillFeed_Implementation(TEXT("unit defeated"), FLinearColor::White);
	TestEqual(TEXT("Kill feed implementation preserves message"),
		GameState->GetLastRoutedMessageForAutomation(), FString(TEXT("unit defeated")));
	TestTrue(TEXT("Kill feed route is classified"), GameState->WasLastRouteKillFeedForAutomation());

	USpiritsHUDWidget* HUDWidget = CreateWidget<USpiritsHUDWidget>(World, USpiritsHUDWidget::StaticClass());
	if (TestNotNull(TEXT("HUD widget is created"), HUDWidget))
	{
		HUDWidget->TakeWidget();
		HUDWidget->AddKillFeedLine(TEXT("old generation"), FLinearColor::White);
		TestEqual(TEXT("HUD receives kill feed"), HUDWidget->GetKillFeedCountForAutomation(), 1);
		HUDWidget->ApplyMatchPresentationForAutomation(
			ESpiritsMatchPhase::Ended, SpiritsTeams::TeamA, SpiritsTeams::TeamA);
		TestTrue(TEXT("Ended shows result overlay"), HUDWidget->IsEndOverlayVisibleForAutomation());
		TestEqual(TEXT("Winner sees victory title"),
			HUDWidget->GetEndTitleForAutomation(), FString(TEXT("V I C T O R Y")));
		HUDWidget->ApplyMatchPresentationForAutomation(
			ESpiritsMatchPhase::WaitingToStart, SpiritsTeams::NoTeam, SpiritsTeams::TeamA);
		TestFalse(TEXT("Next generation hides result overlay"), HUDWidget->IsEndOverlayVisibleForAutomation());
		TestEqual(TEXT("Next generation clears stale kill feed"), HUDWidget->GetKillFeedCountForAutomation(), 0);
	}

	AUnitBase* TeardownUnit = World->SpawnActor<AUnitBase>();
	if (TestNotNull(TEXT("Teardown unit is spawned"), TeardownUnit))
	{
		TeardownUnit->DispatchBeginPlay();
		TeardownUnit->PrimePendingCombatForAutomation();
		TestTrue(TEXT("Automation arms real pending combat state"), TeardownUnit->HasPendingCombatForAutomation());
		const int32 BroadcastsBeforeDestroy = TeardownUnit->GetCombatCancellationBroadcastCountForAutomation();
		// The fixture does not begin the whole world/game loop, so its actor router
		// cannot deliver EndPlay. Use the dev-only seam to invoke the production
		// override, then destroy the actor through the real world path.
		TeardownUnit->InvokeEndPlayForAutomation(EEndPlayReason::Destroyed);
		TeardownUnit->Destroy();
		TestFalse(TEXT("EndPlay override clears timers and local combat state"), TeardownUnit->HasPendingCombatForAutomation());
		TestEqual(TEXT("EndPlay does not multicast cancellation"),
			TeardownUnit->GetCombatCancellationBroadcastCountForAutomation(), BroadcastsBeforeDestroy);
	}

	AUnitBase* BarrierUnit = World->SpawnActor<AUnitBase>();
	if (TestNotNull(TEXT("Authority barrier unit is spawned"), BarrierUnit))
	{
		BarrierUnit->DispatchBeginPlay();
		BarrierUnit->PrimePendingCombatForAutomation();
		BarrierUnit->CancelPendingCombat(true);
		TestFalse(TEXT("Authority barrier clears pending combat"), BarrierUnit->HasPendingCombatForAutomation());
		TestEqual(TEXT("Normal authority cancellation multicasts once"),
			BarrierUnit->GetCombatCancellationBroadcastCountForAutomation(), 1);
	}

	return true;
}
#endif
