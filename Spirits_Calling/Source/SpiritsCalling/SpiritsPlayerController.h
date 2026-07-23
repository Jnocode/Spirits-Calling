#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/NetSerialization.h"
#include "GameFramework/PlayerController.h"
#include "MatchConnection.h"
#include "PlatformActionRouter.h"
#include "SpiritsPlayerController.generated.h"

class UNetDriver;

class APawn;
class UMainMenuWidget;

/**
 * Shared player controller for PC and VR.
 * Handles possession (spirit <-> minion), summoning RPCs, VR mode reporting
 * and the in-game main menu (offline / host / join).
 */
UCLASS()
class SPIRITSCALLING_API ASpiritsPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ASpiritsPlayerController();

	// --- Possession ---
	UFUNCTION(BlueprintCallable, Category = "Spirits|Possession")
	void RequestPossessMinion(APawn* TargetMinion);

	UFUNCTION(Server, Reliable, WithValidation)
	void Server_PossessMinion(APawn* TargetMinion);

	UFUNCTION(BlueprintCallable, Category = "Spirits|Possession")
	void RequestUnpossess();

	UFUNCTION(Server, Reliable)
	void Server_Unpossess();

	/** Server-side direct call (e.g. possessed unit died). */
	void ServerReturnToSpirit();

	// --- Summoning ---
	UFUNCTION(BlueprintCallable, Category = "Spirits|Summon")
	void RequestSummon(int32 ArchetypeIndex, const FVector& Location);

	UFUNCTION(Server, Reliable, WithValidation)
	void Server_SummonUnit(int32 ArchetypeIndex, FVector_NetQuantize Location);

	/** Local-only summon selection (sent along with the summon RPC). */
	UPROPERTY(BlueprintReadWrite, Category = "Spirits|Summon")
	int32 SelectedArchetype = 0;

	void CycleSelectedArchetype(int32 Direction);

	// --- VR ---
	bool IsVRPlayer() const { return bVRPlayer; }
	void SetVRPlayer(bool bVR) { bVRPlayer = bVR; } // server only

	UFUNCTION(Server, Reliable)
	void Server_ReportVRMode(bool bVR);

	// --- Platform action/menu routing ---
	bool CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction Action) const;
	bool IsPlatformMenuOpen() const { return PlatformActionRouter.IsMenuOpen(); }
	void SetPlatformMenuOpen(bool bOpen) { PlatformActionRouter.SetMenuOpen(bOpen); }

	// --- Menu ---
	void ToggleMainMenu();
	void CloseMainMenu();

	/** Starts the next authoritative match without relaunching the application. */
	UFUNCTION(BlueprintCallable, Category = "Spirits|Match")
	void RequestRestartMatch();

	UFUNCTION(Server, Reliable, WithValidation)
	void Server_RequestRestartMatch();

	// --- LAN connection lifecycle ---
	/** Called by the menu before issuing a Join IP ClientTravel. */
	void BeginJoinAttempt();

	/** True only when a join attempt actually reached a networked client world. */
	bool IsMatchConnected() const { return ConnectionModel.IsMatchConnected(); }

	/** Stable code of the most recent connection failure ("" when none). */
	const FString& GetLastConnectionError() const { return ConnectionModel.GetLastErrorCode(); }

	// --- Achievements (server detects the event; owning client unlocks locally) ---
	UFUNCTION(Client, Reliable) void Client_UnlockAchievement(const FString& Id);
	UFUNCTION(Client, Reliable) void Client_ReportPossessKill();
	UFUNCTION(Client, Reliable) void Client_ReportSummon();
	UFUNCTION(Client, Reliable) void Client_SummonFailed(const FString& FailureCode);
	UFUNCTION(Client, Reliable) void Client_ReportWin(int32 Difficulty, int32 Civ, bool bLan);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

#if WITH_DEV_AUTOMATION_TESTS
	/** Dev-only seams so actor/world automation can drive the connection model. */
	void BeginJoinAttemptForAutomation() { BeginJoinAttempt(); }
	void SimulateTravelFailureForAutomation(ETravelFailure::Type FailureType);
	void SimulateNetworkFailureForAutomation(ENetworkFailure::Type FailureType);
	void SimulateMatchConnectedForAutomation() { ConnectionModel.MarkConnected(); }
	void SimulateDisconnectForAutomation() { ConnectionModel.HandleDisconnect(); }
	SpiritsNet::EConnectionPhase GetConnectionPhaseForAutomation() const { return ConnectionModel.GetPhase(); }
#endif

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Routes engine failure delegates onto the pure connection model + presentation. */
	void HandleNetworkFailure(UWorld* World, UNetDriver* NetDriver, ENetworkFailure::Type FailureType, const FString& ErrorString);
	void HandleTravelFailure(UWorld* World, ETravelFailure::Type FailureType, const FString& ErrorString);

	/** Surfaces a stable connection code to the owner via menu + HUD, never silently. */
	void PresentConnectionError(const FString& Code, const FString& Detail);

	UPROPERTY(Replicated)
	bool bVRPlayer = false;

	/** Server: spirit pawn kept while possessing a minion. */
	UPROPERTY()
	TObjectPtr<APawn> SavedSpiritPawn;

	UPROPERTY()
	TObjectPtr<UMainMenuWidget> MainMenu;

	/** Local-only pure gate shared by PC, PCVR and possessed-pawn adapters. */
	SpiritsPlatform::FPlatformActionRouter PlatformActionRouter;

	/** Local-only LAN connection lifecycle tracker. */
	SpiritsNet::FMatchConnectionModel ConnectionModel;

	FDelegateHandle NetworkFailureHandle;
	FDelegateHandle TravelFailureHandle;
};
