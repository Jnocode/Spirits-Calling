#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "SpiritPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UFloatingPawnMovement;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

/**
 * PC spirit (RTS god view):
 * WASD pan, Q/E rotate, mouse wheel zoom,
 * LMB possess friendly minion, RMB summon at cursor, 1-3 pick archetype, M menu.
 */
UCLASS()
class SPIRITSCALLING_API ASpiritPawn : public APawn
{
	GENERATED_BODY()

public:
	ASpiritPawn();

	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

#if WITH_DEV_AUTOMATION_TESTS
	/** Dev-only seams so actor/world automation exercises the real PC handlers. */
	void MoveInputForAutomation(const FVector2D& Axis);
	void SelectArchetypeForAutomation(int32 Which);
#endif

protected:
	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<USpringArmComponent> SpringArm;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UFloatingPawnMovement> Movement;

	// Runtime-built input
	UPROPERTY() TObjectPtr<UInputMappingContext> SpiritIMC;
	UPROPERTY() TObjectPtr<UInputAction> IA_Move;
	UPROPERTY() TObjectPtr<UInputAction> IA_Zoom;
	UPROPERTY() TObjectPtr<UInputAction> IA_Rotate;
	UPROPERTY() TObjectPtr<UInputAction> IA_Select;
	UPROPERTY() TObjectPtr<UInputAction> IA_Summon;
	UPROPERTY() TObjectPtr<UInputAction> IA_Type1;
	UPROPERTY() TObjectPtr<UInputAction> IA_Type2;
	UPROPERTY() TObjectPtr<UInputAction> IA_Type3;
	UPROPERTY() TObjectPtr<UInputAction> IA_Menu;

	void BuildInputAssets();
	void OnMoveInput(const FInputActionValue& Value);
	void OnZoomInput(const FInputActionValue& Value);
	void OnRotateInput(const FInputActionValue& Value);
	void OnSelectInput(const FInputActionValue& Value);
	void OnSummonInput(const FInputActionValue& Value);
	void OnType1(const FInputActionValue& Value);
	void OnType2(const FInputActionValue& Value);
	void OnType3(const FInputActionValue& Value);
	void OnMenuInput(const FInputActionValue& Value);
};
