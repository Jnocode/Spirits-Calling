#include "SpiritsPlayerController.h"

#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "IXRTrackingSystem.h"
#include "MainMenuWidget.h"
#include "Net/UnrealNetwork.h"
#include "SpiritVRPawn.h"
#include "SpiritsAchievements.h"
#include "SpiritsGameMode.h"
#include "SpiritsGameState.h"
#include "SpiritsHUD.h"
#include "SpiritsPlayerState.h"
#include "UnitBase.h"

ASpiritsPlayerController::ASpiritsPlayerController()
{
	bShowMouseCursor = true;
}

void ASpiritsPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (!IsLocalController())
	{
		return;
	}

	// Bind engine connection failure delegates so a failed Join IP or a dropped
	// connection always resolves to a stable code and owner-facing presentation
	// instead of a silent or falsely connected state.
	if (GEngine)
	{
		NetworkFailureHandle = GEngine->OnNetworkFailure().AddUObject(this, &ASpiritsPlayerController::HandleNetworkFailure);
		TravelFailureHandle = GEngine->OnTravelFailure().AddUObject(this, &ASpiritsPlayerController::HandleTravelFailure);
	}

	// A local controller that begins play on a networked client world means the
	// Join IP attempt actually reached the listen server.
	if (GetWorld() && GetWorld()->GetNetMode() == NM_Client)
	{
		ConnectionModel.MarkConnected();
	}

	// Report the pure mode decision so the server spawns the right spirit pawn.
	// An XR module alone is insufficient: unavailable tracking must remain PC.
	const bool bXRSystemAvailable = GEngine && GEngine->XRSystem.IsValid();
	const bool bHeadTrackingAllowed = bXRSystemAvailable && GEngine->XRSystem->IsHeadTrackingAllowed();
	const SpiritsPlatform::EPlatformMode PlatformMode =
		SpiritsPlatform::SelectPlatformMode(bXRSystemAvailable, bHeadTrackingAllowed);
	if (PlatformMode == SpiritsPlatform::EPlatformMode::PCVR)
	{
		Server_ReportVRMode(true);
	}
	else if (GetWorld() && GetWorld()->GetNetMode() == NM_Standalone)
	{
		// Flat-screen offline start: show the main menu (offline / host / join).
		ToggleMainMenu();
	}
}

void ASpiritsPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (GEngine)
	{
		if (NetworkFailureHandle.IsValid())
		{
			GEngine->OnNetworkFailure().Remove(NetworkFailureHandle);
			NetworkFailureHandle.Reset();
		}
		if (TravelFailureHandle.IsValid())
		{
			GEngine->OnTravelFailure().Remove(TravelFailureHandle);
			TravelFailureHandle.Reset();
		}
	}

	Super::EndPlay(EndPlayReason);
}

// ------------------------------------------------------------- LAN connection

void ASpiritsPlayerController::BeginJoinAttempt()
{
	ConnectionModel.BeginJoinAttempt();
}

void ASpiritsPlayerController::HandleNetworkFailure(UWorld* /*World*/, UNetDriver* /*NetDriver*/, ENetworkFailure::Type FailureType, const FString& ErrorString)
{
	// A lost connection to an established Match: the remaining peer stays
	// operable and records the disconnect; a pre-connection failure is a join
	// failure. Both clear the connected flag.
	if (ConnectionModel.IsMatchConnected())
	{
		ConnectionModel.HandleDisconnect();
	}
	else
	{
		ConnectionModel.HandleJoinFailure();
	}
	PresentConnectionError(ConnectionModel.GetLastErrorCode(),
		FString::Printf(TEXT("%s: %s"), ENetworkFailure::ToString(FailureType), *ErrorString));
}

void ASpiritsPlayerController::HandleTravelFailure(UWorld* /*World*/, ETravelFailure::Type FailureType, const FString& ErrorString)
{
	// Travel failure always means the Join IP attempt did not establish a Match.
	ConnectionModel.HandleJoinFailure();
	PresentConnectionError(ConnectionModel.GetLastErrorCode(),
		FString::Printf(TEXT("%s: %s"), ETravelFailure::ToString(FailureType), *ErrorString));
}

void ASpiritsPlayerController::PresentConnectionError(const FString& Code, const FString& Detail)
{
	UE_LOG(LogTemp, Warning, TEXT("[Match] connection error [%s] connected=%s detail=%s"),
		*Code, IsMatchConnected() ? TEXT("true") : TEXT("false"), *Detail);

	// No local player means there is no viewport to present into (e.g. headless
	// automation or a dedicated context); the stable code is still logged above.
	if (!IsLocalController() || !GetLocalPlayer())
	{
		return;
	}

	// Surface the failure so the owner can retry from the menu rather than being
	// left in an ambiguous state.
	if (!MainMenu || !MainMenu->IsInViewport())
	{
		ToggleMainMenu();
	}
	if (MainMenu)
	{
		MainMenu->ShowConnectionError(Code);
	}
	if (ASpiritsHUD* HUD = Cast<ASpiritsHUD>(GetHUD()))
	{
		HUD->AddAnnouncement(
			FString::Printf(TEXT("Connection failed [%s]"), *Code),
			FLinearColor(0.95f, 0.25f, 0.20f));
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void ASpiritsPlayerController::SimulateTravelFailureForAutomation(ETravelFailure::Type FailureType)
{
	HandleTravelFailure(GetWorld(), FailureType, TEXT("automation"));
}

void ASpiritsPlayerController::SimulateNetworkFailureForAutomation(ENetworkFailure::Type FailureType)
{
	HandleNetworkFailure(GetWorld(), nullptr, FailureType, TEXT("automation"));
}
#endif

// ------------------------------------------------------------------ Possession

void ASpiritsPlayerController::RequestPossessMinion(APawn* TargetMinion)
{
	if (TargetMinion && CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Possession))
	{
		Server_PossessMinion(TargetMinion);
	}
}

bool ASpiritsPlayerController::Server_PossessMinion_Validate(APawn* TargetMinion)
{
	return true; // full validation in implementation (soft-fail instead of kick)
}

void ASpiritsPlayerController::Server_PossessMinion_Implementation(APawn* TargetMinion)
{
	AUnitBase* Unit = Cast<AUnitBase>(TargetMinion);
	const ASpiritsPlayerState* PS = GetPlayerState<ASpiritsPlayerState>();
	const ASpiritsGameState* GS = GetWorld() ? GetWorld()->GetGameState<ASpiritsGameState>() : nullptr;

	if (!Unit || !PS || Unit->IsDead() || Unit->bIsStructure || Unit->TeamId != PS->TeamId)
	{
		return;
	}
	if (GS && GS->Phase != ESpiritsMatchPhase::InProgress)
	{
		return;
	}
	if (Unit->GetController() && Unit->GetController()->IsPlayerController())
	{
		return; // already possessed by another player
	}

	// Remember the spirit pawn so we can return to it.
	if (APawn* Current = GetPawn())
	{
		if (!Current->IsA<AUnitBase>())
		{
			SavedSpiritPawn = Current;
		}
	}

	// Remove the unit's AI controller before the player takes over.
	if (AController* OldAI = Unit->GetController())
	{
		OldAI->UnPossess();
		OldAI->Destroy();
	}

	Possess(Unit);

	UE_LOG(LogTemp, Log, TEXT("[Spirits] %s possessed %s"), *GetName(), *Unit->GetName());
}

void ASpiritsPlayerController::RequestUnpossess()
{
	if (CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::ReturnFromPossession))
	{
		Server_Unpossess();
	}
}

void ASpiritsPlayerController::Server_Unpossess_Implementation()
{
	ServerReturnToSpirit();
}

void ASpiritsPlayerController::ServerReturnToSpirit()
{
	if (!HasAuthority())
	{
		return;
	}

	AUnitBase* Unit = Cast<AUnitBase>(GetPawn());
	if (!Unit)
	{
		return; // already in spirit form
	}

	if (SavedSpiritPawn && IsValid(SavedSpiritPawn))
	{
		Possess(SavedSpiritPawn);
	}
	else
	{
		UnPossess();
		if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
		{
			GM->RestartPlayer(this);
		}
	}

	// Hand the unit back to its AI (if it survived).
	if (IsValid(Unit) && !Unit->IsDead())
	{
		Unit->SpawnDefaultController();
	}
}

// ------------------------------------------------------------------ Summoning

void ASpiritsPlayerController::RequestSummon(int32 ArchetypeIndex, const FVector& Location)
{
	if (CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Summon))
	{
		Server_SummonUnit(ArchetypeIndex, Location);
	}
}

bool ASpiritsPlayerController::Server_SummonUnit_Validate(int32 /*ArchetypeIndex*/, FVector_NetQuantize /*Location*/)
{
	// Keep malformed gameplay requests inside the server validation path so the
	// owner receives a stable failure code instead of being disconnected by RPC
	// validation. GameMode performs the authoritative rules and placement checks.
	return true;
}

void ASpiritsPlayerController::Server_SummonUnit_Implementation(int32 ArchetypeIndex, FVector_NetQuantize Location)
{
	if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
	{
		GM->SpawnUnitForPlayer(this, ArchetypeIndex, Location);
	}
}

void ASpiritsPlayerController::CycleSelectedArchetype(int32 Direction)
{
	if (!CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SummonSelection))
	{
		return;
	}

	int32 NumOptions = 3;
	if (const ASpiritsGameState* GS = GetWorld() ? GetWorld()->GetGameState<ASpiritsGameState>() : nullptr)
	{
		if (GS->SummonOptions.Num() > 0)
		{
			NumOptions = GS->SummonOptions.Num();
		}
	}
	SelectedArchetype = (SelectedArchetype + Direction + NumOptions) % NumOptions;
}

// ------------------------------------------------------------------ VR

void ASpiritsPlayerController::Server_ReportVRMode_Implementation(bool bVR)
{
	if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
	{
		GM->SetPlayerVRMode(this, bVR);
	}
}

// ------------------------------------------------------------------ Menu

bool ASpiritsPlayerController::CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction Action) const
{
	return PlatformActionRouter.CanDispatch(Action);
}

void ASpiritsPlayerController::ToggleMainMenu()
{
	if (!IsLocalController() ||
		!CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::MenuToggle))
	{
		return;
	}

	if (MainMenu && MainMenu->IsInViewport())
	{
		CloseMainMenu();
		return;
	}

	if (!MainMenu)
	{
		MainMenu = CreateWidget<UMainMenuWidget>(this, UMainMenuWidget::StaticClass());
	}
	if (MainMenu)
	{
		MainMenu->AddToViewport(100);
		// Stable, greppable smoke marker for the title/menu launch stage.
		UE_LOG(LogTemp, Display, TEXT("[SpiritsSmoke] Stage=MenuReady"));
		SetPlatformMenuOpen(true);
		bShowMouseCursor = true;
		FInputModeGameAndUI Mode;
		Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		Mode.SetHideCursorDuringCapture(false);
		SetInputMode(Mode);
	}
}

void ASpiritsPlayerController::CloseMainMenu()
{
	if (MainMenu && MainMenu->IsInViewport())
	{
		MainMenu->RemoveFromParent();
	}
	if (ASpiritVRPawn* VRPawn = Cast<ASpiritVRPawn>(GetPawn()))
	{
		VRPawn->SetVRMenuOpen(false);
	}
	SetPlatformMenuOpen(false);

	// Restore input mode appropriate for the current pawn.
	if (GetPawn() && (GetPawn()->IsA<AUnitBase>() || GetPawn()->IsA<ASpiritVRPawn>()))
	{
		bShowMouseCursor = false;
		SetInputMode(FInputModeGameOnly());
	}
	else
	{
		bShowMouseCursor = true;
		FInputModeGameAndUI Mode;
		Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		Mode.SetHideCursorDuringCapture(false);
		SetInputMode(Mode);
	}
}

void ASpiritsPlayerController::RequestRestartMatch()
{
	if (CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Restart))
	{
		Server_RequestRestartMatch();
	}
}

bool ASpiritsPlayerController::Server_RequestRestartMatch_Validate()
{
	return true;
}

void ASpiritsPlayerController::Server_RequestRestartMatch_Implementation()
{
	if (ASpiritsGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASpiritsGameMode>() : nullptr)
	{
		GM->RequestRestartMatch(this);
	}
}

// ------------------------------------------------------------------ Achievements

namespace
{
	USpiritsAchievements* GetAchievements(const APlayerController* PC)
	{
		UWorld* World = PC ? PC->GetWorld() : nullptr;
		UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
		return GI ? GI->GetSubsystem<USpiritsAchievements>() : nullptr;
	}
}

void ASpiritsPlayerController::Client_UnlockAchievement_Implementation(const FString& Id)
{
	if (USpiritsAchievements* Ach = GetAchievements(this))
	{
		Ach->UnlockAchievement(Id);
	}
}

void ASpiritsPlayerController::Client_ReportPossessKill_Implementation()
{
	if (USpiritsAchievements* Ach = GetAchievements(this))
	{
		Ach->ReportPossessKill();
	}
}

void ASpiritsPlayerController::Client_ReportSummon_Implementation()
{
	if (USpiritsAchievements* Ach = GetAchievements(this))
	{
		Ach->ReportSummon();
	}
}

void ASpiritsPlayerController::Client_SummonFailed_Implementation(const FString& FailureCode)
{
	UE_LOG(LogTemp, Warning, TEXT("[Summon] request rejected for owner %s: %s"), *GetName(), *FailureCode);
	if (ASpiritsHUD* HUD = Cast<ASpiritsHUD>(GetHUD()))
	{
		HUD->AddAnnouncement(
			FString::Printf(TEXT("Summon rejected [%s]"), *FailureCode),
			FLinearColor(0.95f, 0.25f, 0.20f));
	}
}

void ASpiritsPlayerController::Client_ReportWin_Implementation(int32 Difficulty, int32 Civ, bool bLan)
{
	if (USpiritsAchievements* Ach = GetAchievements(this))
	{
		Ach->ReportWin(Difficulty, Civ, bLan);
	}
}

void ASpiritsPlayerController::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASpiritsPlayerController, bVRPlayer);
}
