#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "PlatformActionRouter.h"
#include "SpiritVRPawn.generated.h"

class UCameraComponent;
class UFloatingPawnMovement;
class UMotionControllerComponent;
class UStaticMeshComponent;
class UTextRenderComponent;
class UWidgetComponent;
class UWidgetInteractionComponent;
class UMainMenuWidget;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

/**
 * VR spirit (floating god view):
 * left stick move (camera-relative), right stick X snap turn, right stick Y fly up/down,
 * right trigger point-and-possess, A summon at pointed ground, X cycle archetype.
 */
UCLASS()
class SPIRITSCALLING_API ASpiritVRPawn : public APawn
{
	GENERATED_BODY()

public:
	ASpiritVRPawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

	/** Applies world-space menu presentation and updates the controller-owned gate. */
	void SetVRMenuOpen(bool bOpen);

#if WITH_DEV_AUTOMATION_TESTS
	/** Dev-only seams so actor/world automation exercises the real VR handlers. */
	void MoveInputForAutomation(const FVector2D& Axis);
	void SnapTurnInputForAutomation(float Axis);
#endif

protected:
	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<USceneComponent> VROrigin;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UMotionControllerComponent> LeftController;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UMotionControllerComponent> RightController;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> LeftHandMesh;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> RightHandMesh;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> AimBeam;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UTextRenderComponent> HUDText;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UFloatingPawnMovement> Movement;

	// World-space VR main menu (floats in front of the head; laser-selected).
	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UWidgetComponent> VRMenuComp;

	// Drives hover/click on the menu widget from the right controller's ray.
	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UWidgetInteractionComponent> WidgetInteraction;

	UPROPERTY() TObjectPtr<UMainMenuWidget> VRMenuWidget;

	// Runtime-built input
	UPROPERTY() TObjectPtr<UInputMappingContext> VRSpiritIMC;
	UPROPERTY() TObjectPtr<UInputAction> IA_Move;
	UPROPERTY() TObjectPtr<UInputAction> IA_SnapTurn;
	UPROPERTY() TObjectPtr<UInputAction> IA_Vertical;
	UPROPERTY() TObjectPtr<UInputAction> IA_Possess;
	UPROPERTY() TObjectPtr<UInputAction> IA_Summon;
	UPROPERTY() TObjectPtr<UInputAction> IA_CycleType;
	UPROPERTY() TObjectPtr<UInputAction> IA_Menu;

	void BuildInputAssets();
	void OnMoveInput(const FInputActionValue& Value);
	void OnSnapTurnInput(const FInputActionValue& Value);
	void OnVerticalInput(const FInputActionValue& Value);
	void OnPossessInput(const FInputActionValue& Value);
	void OnTriggerReleased(const FInputActionValue& Value);
	void OnSummonInput(const FInputActionValue& Value);
	void OnCycleTypeInput(const FInputActionValue& Value);
	void OnMenuInput(const FInputActionValue& Value);

	void EnsureVRMenu();
	void ToggleVRMenu();
	void UpdateComfortVignette(float DeltaSeconds);

	bool TraceFromRightController(FHitResult& OutHit) const;
	void UpdateHUDText();

	SpiritsPlatform::FComfortTurnGate ComfortTurnGate;
};
