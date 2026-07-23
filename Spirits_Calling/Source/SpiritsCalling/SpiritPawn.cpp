#include "SpiritPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/SpringArmComponent.h"
#include "SpiritsInputBuilder.h"
#include "SpiritsPlayerController.h"
#include "SpiritsPlayerState.h"
#include "UnitBase.h"

ASpiritPawn::ASpiritPawn()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true;
	SetReplicateMovement(true);

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(Root);
	SpringArm->SetRelativeRotation(FRotator(-55.f, 0.f, 0.f));
	SpringArm->TargetArmLength = 1600.f;
	SpringArm->bDoCollisionTest = false;
	SpringArm->bUsePawnControlRotation = false;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SpringArm);
	Camera->bLockToHmd = false;

	Movement = CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("Movement"));
	Movement->MaxSpeed = 3000.f;
	Movement->Acceleration = 8000.f;
	Movement->Deceleration = 6500.f;
}

void ASpiritPawn::PawnClientRestart()
{
	Super::PawnClientRestart();

	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->IsLocalController())
	{
		return;
	}

	BuildInputAssets();

	if (ULocalPlayer* LP = PC->GetLocalPlayer())
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = LP->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
		{
			Subsystem->ClearAllMappings();
			Subsystem->AddMappingContext(SpiritIMC, 1);
		}
	}

	PC->bShowMouseCursor = true;
	FInputModeGameAndUI Mode;
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	Mode.SetHideCursorDuringCapture(false);
	PC->SetInputMode(Mode);
}

void ASpiritPawn::BuildInputAssets()
{
	if (SpiritIMC)
	{
		return;
	}

	SpiritIMC = NewObject<UInputMappingContext>(this);
	IA_Move   = SpiritsInput::MakeAction(this, EInputActionValueType::Axis2D);
	IA_Zoom   = SpiritsInput::MakeAction(this, EInputActionValueType::Axis1D);
	IA_Rotate = SpiritsInput::MakeAction(this, EInputActionValueType::Axis1D);
	IA_Select = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Summon = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Type1  = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Type2  = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Type3  = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Menu   = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);

	using namespace SpiritsInput;

	MapWASD(SpiritIMC, IA_Move);
	MapSwizzle(SpiritIMC, IA_Move, EKeys::Up);
	MapSwizzle(SpiritIMC, IA_Move, EKeys::Down, true);
	Map(SpiritIMC, IA_Move, EKeys::Right);
	MapNegate(SpiritIMC, IA_Move, EKeys::Left);

	Map(SpiritIMC, IA_Zoom, EKeys::MouseWheelAxis);

	Map(SpiritIMC, IA_Rotate, EKeys::E);
	MapNegate(SpiritIMC, IA_Rotate, EKeys::Q);

	Map(SpiritIMC, IA_Select, EKeys::LeftMouseButton);
	Map(SpiritIMC, IA_Summon, EKeys::RightMouseButton);

	Map(SpiritIMC, IA_Type1, EKeys::One);
	Map(SpiritIMC, IA_Type2, EKeys::Two);
	Map(SpiritIMC, IA_Type3, EKeys::Three);

	Map(SpiritIMC, IA_Menu, EKeys::M);
	Map(SpiritIMC, IA_Menu, EKeys::Escape);
}

void ASpiritPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	BuildInputAssets();

	if (UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EIC->BindAction(IA_Move, ETriggerEvent::Triggered, this, &ASpiritPawn::OnMoveInput);
		EIC->BindAction(IA_Zoom, ETriggerEvent::Triggered, this, &ASpiritPawn::OnZoomInput);
		EIC->BindAction(IA_Rotate, ETriggerEvent::Triggered, this, &ASpiritPawn::OnRotateInput);
		EIC->BindAction(IA_Select, ETriggerEvent::Started, this, &ASpiritPawn::OnSelectInput);
		EIC->BindAction(IA_Summon, ETriggerEvent::Started, this, &ASpiritPawn::OnSummonInput);
		EIC->BindAction(IA_Type1, ETriggerEvent::Started, this, &ASpiritPawn::OnType1);
		EIC->BindAction(IA_Type2, ETriggerEvent::Started, this, &ASpiritPawn::OnType2);
		EIC->BindAction(IA_Type3, ETriggerEvent::Started, this, &ASpiritPawn::OnType3);
		EIC->BindAction(IA_Menu, ETriggerEvent::Started, this, &ASpiritPawn::OnMenuInput);
	}
}

void ASpiritPawn::OnMoveInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Movement))
	{
		return;
	}
	const FVector2D Input = Value.Get<FVector2D>();
	const FRotator YawRot(0.f, GetActorRotation().Yaw, 0.f);
	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::X), Input.Y);
	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::Y), Input.X);
}

void ASpiritPawn::OnZoomInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::View))
	{
		return;
	}
	const float Axis = Value.Get<float>();
	SpringArm->TargetArmLength = FMath::Clamp(SpringArm->TargetArmLength - Axis * 150.f, 500.f, 4500.f);
}

void ASpiritPawn::OnRotateInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::View))
	{
		return;
	}
	const float Axis = Value.Get<float>();
	AddActorWorldRotation(FRotator(0.f, Axis * 90.f * GetWorld()->GetDeltaSeconds(), 0.f));
}

void ASpiritPawn::OnSelectInput(const FInputActionValue& /*Value*/)
{
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Possession))
	{
		return;
	}

	FHitResult Hit;
	if (PC->GetHitResultUnderCursor(ECC_Pawn, false, Hit))
	{
		AUnitBase* Unit = Cast<AUnitBase>(Hit.GetActor());
		const ASpiritsPlayerState* PS = PC->GetPlayerState<ASpiritsPlayerState>();
		if (Unit && PS && !Unit->IsDead() && !Unit->bIsStructure && Unit->TeamId == PS->TeamId)
		{
			PC->RequestPossessMinion(Unit);
		}
	}
}

void ASpiritPawn::OnSummonInput(const FInputActionValue& /*Value*/)
{
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Summon))
	{
		return;
	}

	FHitResult Hit;
	if (PC->GetHitResultUnderCursor(ECC_Pawn, false, Hit))
	{
		PC->RequestSummon(PC->SelectedArchetype, Hit.Location);
	}
}

void ASpiritPawn::OnType1(const FInputActionValue&)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
		PC && PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SummonSelection))
	{
		PC->SelectedArchetype = 0;
	}
}

void ASpiritPawn::OnType2(const FInputActionValue&)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
		PC && PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SummonSelection))
	{
		PC->SelectedArchetype = 1;
	}
}

void ASpiritPawn::OnType3(const FInputActionValue&)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
		PC && PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SummonSelection))
	{
		PC->SelectedArchetype = 2;
	}
}

void ASpiritPawn::OnMenuInput(const FInputActionValue&)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController()))
	{
		PC->ToggleMainMenu();
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void ASpiritPawn::MoveInputForAutomation(const FVector2D& Axis)
{
	OnMoveInput(FInputActionValue(Axis));
}

void ASpiritPawn::SelectArchetypeForAutomation(int32 Which)
{
	switch (Which)
	{
	case 0:  OnType1(FInputActionValue(true)); break;
	case 1:  OnType2(FInputActionValue(true)); break;
	default: OnType3(FInputActionValue(true)); break;
	}
}
#endif
