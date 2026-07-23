#include "SpiritsCalling/SpiritsPlayerController.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Misc/AutomationTest.h"
#include "SpiritsCalling/MatchConnection.h"
#include "SpiritsCalling/PlatformActionRouter.h"
#include "SpiritsCalling/SpiritPawn.h"
#include "SpiritsCalling/SpiritVRPawn.h"

// Actor/world regression for PC/PCVR platform actions and the LAN connection
// lifecycle. Property 8 covers the pure router/gate; this suite proves the same
// contract on real spawned pawns and controllers: menu-open input never moves
// the player transform, the snap-turn cooldown gates the actual actor rotation,
// and travel/network failures resolve to stable connection codes without a
// falsely connected Match. Real hardware (Quest Link/SteamVR), two-instance LAN
// and packaged clean-machine launches remain separate, human/hardware gates.
namespace
{
	struct FScopedSpiritsPlatformWorld
	{
		FScopedSpiritsPlatformWorld()
		{
			if (!GEngine)
			{
				return;
			}
			const FName WorldName = MakeUniqueObjectName(
				GetTransientPackage(), UWorld::StaticClass(), TEXT("SpiritsPlatformTestWorld"));
			FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::Game);
			World = UWorld::CreateWorld(EWorldType::Game, false, WorldName, GetTransientPackage());
			if (!World)
			{
				return;
			}
			World->AddToRoot();
			WorldContext.SetCurrentWorld(World);
		}

		~FScopedSpiritsPlatformWorld()
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
	FSpiritsPlatformActionWorldAutomationTest,
	"SpiritsCalling.Requirements.Platform.World action gate, snap-turn cooldown, and LAN connection lifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsPlatformActionWorldAutomationTest::RunTest(const FString& Parameters)
{
	FScopedSpiritsPlatformWorld Fixture;
	UWorld* World = Fixture.World;
	if (!TestNotNull(TEXT("Transient game world is created"), World))
	{
		return false;
	}

	ASpiritsPlayerController* Controller = World->SpawnActor<ASpiritsPlayerController>();
	ASpiritPawn* PCPawn = World->SpawnActor<ASpiritPawn>();
	ASpiritVRPawn* VRPawn = World->SpawnActor<ASpiritVRPawn>();
	if (!TestNotNull(TEXT("PC-shared controller is spawned"), Controller) ||
		!TestNotNull(TEXT("PC spirit pawn is spawned"), PCPawn) ||
		!TestNotNull(TEXT("VR spirit pawn is spawned"), VRPawn))
	{
		return false;
	}

	// ---------------------------------------------------------- PC action gate
	Controller->Possess(PCPawn);
	Controller->SetPlatformMenuOpen(true);

	PCPawn->ConsumeMovementInputVector();
	PCPawn->MoveInputForAutomation(FVector2D(1.f, 1.f));
	TestTrue(TEXT("PC movement handler is blocked while the menu is open"),
		PCPawn->GetPendingMovementInputVector().IsNearlyZero());

	Controller->SelectedArchetype = 2;
	PCPawn->SelectArchetypeForAutomation(0);
	TestEqual(TEXT("PC summon selection is blocked while the menu is open"),
		Controller->SelectedArchetype, 2);

	Controller->SetPlatformMenuOpen(false);
	PCPawn->ConsumeMovementInputVector();
	PCPawn->MoveInputForAutomation(FVector2D(1.f, 1.f));
	TestFalse(TEXT("PC movement handler dispatches while the menu is closed"),
		PCPawn->GetPendingMovementInputVector().IsNearlyZero());

	PCPawn->SelectArchetypeForAutomation(1);
	TestEqual(TEXT("PC summon selection dispatches while the menu is closed"),
		Controller->SelectedArchetype, 1);

	// ------------------------------------------------------- VR movement gate
	Controller->Possess(VRPawn);
	Controller->SetPlatformMenuOpen(true);

	VRPawn->ConsumeMovementInputVector();
	VRPawn->MoveInputForAutomation(FVector2D(1.f, 1.f));
	TestTrue(TEXT("VR movement handler is blocked while the menu is open"),
		VRPawn->GetPendingMovementInputVector().IsNearlyZero());

	// Snap turn is a gameplay action; it must not rotate the player while the
	// menu is open (the handler returns before the comfort gate is consulted).
	const double YawBeforeMenu = VRPawn->GetActorRotation().Yaw;
	VRPawn->SnapTurnInputForAutomation(1.f);
	TestEqual(TEXT("VR snap turn is blocked while the menu is open"),
		VRPawn->GetActorRotation().Yaw, YawBeforeMenu);

	// --------------------------------------------------- VR snap-turn cooldown
	Controller->SetPlatformMenuOpen(false);
	const double YawStart = VRPawn->GetActorRotation().Yaw;
	VRPawn->SnapTurnInputForAutomation(1.f); // first turn is accepted
	const double YawAfterFirst = VRPawn->GetActorRotation().Yaw;
	TestFalse(TEXT("First VR snap turn rotates the actor"),
		FMath::IsNearlyEqual(YawAfterFirst, YawStart));

	VRPawn->SnapTurnInputForAutomation(1.f); // within 0.35s: rejected by the gate
	TestEqual(TEXT("Second VR snap turn within the cooldown is rejected"),
		VRPawn->GetActorRotation().Yaw, YawAfterFirst);

	// A below-threshold axis never turns even when the cooldown has elapsed.
	const double YawBeforeWeak = VRPawn->GetActorRotation().Yaw;
	VRPawn->SnapTurnInputForAutomation(0.3f);
	TestEqual(TEXT("Below-threshold VR snap axis does not turn"),
		VRPawn->GetActorRotation().Yaw, YawBeforeWeak);

	// ---------------------------------------------- LAN connection lifecycle
	TestFalse(TEXT("Controller starts with no connected Match"), Controller->IsMatchConnected());
	TestTrue(TEXT("Controller starts with no connection error"), Controller->GetLastConnectionError().IsEmpty());

	Controller->BeginJoinAttemptForAutomation();
	TestEqual(TEXT("Join attempt enters Joining"),
		Controller->GetConnectionPhaseForAutomation(), SpiritsNet::EConnectionPhase::Joining);
	TestFalse(TEXT("Join attempt is not yet a connected Match"), Controller->IsMatchConnected());

	Controller->SimulateTravelFailureForAutomation(ETravelFailure::TravelFailure);
	TestEqual(TEXT("Travel failure resolves to Match.JoinFailed"),
		Controller->GetLastConnectionError(), FString(SpiritsNet::JoinFailedCode));
	TestFalse(TEXT("Failed join is not a connected Match"), Controller->IsMatchConnected());
	TestEqual(TEXT("Failed join leaves the local peer operable (Failed, not frozen)"),
		Controller->GetConnectionPhaseForAutomation(), SpiritsNet::EConnectionPhase::Failed);

	// A pre-connection network failure is also a join failure, not a disconnect.
	Controller->BeginJoinAttemptForAutomation();
	Controller->SimulateNetworkFailureForAutomation(ENetworkFailure::ConnectionTimeout);
	TestEqual(TEXT("Pre-connection network failure resolves to Match.JoinFailed"),
		Controller->GetLastConnectionError(), FString(SpiritsNet::JoinFailedCode));

	// A drop after a successful connection is a disconnect; the remaining peer
	// stays operable and never keeps a stale connected flag.
	Controller->SimulateMatchConnectedForAutomation();
	TestTrue(TEXT("Successful join reports a connected Match"), Controller->IsMatchConnected());
	Controller->SimulateNetworkFailureForAutomation(ENetworkFailure::ConnectionLost);
	TestEqual(TEXT("Post-connection drop resolves to Match.Disconnected"),
		Controller->GetLastConnectionError(), FString(SpiritsNet::DisconnectedCode));
	TestFalse(TEXT("Disconnect clears the connected Match flag"), Controller->IsMatchConnected());
	TestEqual(TEXT("Disconnect returns the remaining peer to an operable idle state"),
		Controller->GetConnectionPhaseForAutomation(), SpiritsNet::EConnectionPhase::Idle);

	return true;
}
#endif
