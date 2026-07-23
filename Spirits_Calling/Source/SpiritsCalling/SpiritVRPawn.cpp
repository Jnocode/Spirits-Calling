#include "SpiritVRPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/WidgetComponent.h"
#include "Components/WidgetInteractionComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "HAL/PlatformTime.h"
#include "MainMenuWidget.h"
#include "MotionControllerComponent.h"
#include "SpiritsGameState.h"
#include "SpiritsInputBuilder.h"
#include "SpiritsPlayerController.h"
#include "SpiritsPlayerState.h"
#include "UnitBase.h"
#include "UObject/ConstructorHelpers.h"

ASpiritVRPawn::ASpiritVRPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	SetReplicateMovement(true);

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	VROrigin = CreateDefaultSubobject<USceneComponent>(TEXT("VROrigin"));
	VROrigin->SetupAttachment(Root);

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(VROrigin);
	Camera->bLockToHmd = true;

	LeftController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("LeftController"));
	LeftController->SetupAttachment(VROrigin);
	LeftController->SetTrackingMotionSource(FName(TEXT("Left")));

	RightController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("RightController"));
	RightController->SetupAttachment(VROrigin);
	RightController->SetTrackingMotionSource(FName(TEXT("Right")));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	LeftHandMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftHandMesh"));
	LeftHandMesh->SetupAttachment(LeftController);
	LeftHandMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	LeftHandMesh->SetRelativeScale3D(FVector(0.06f));

	RightHandMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightHandMesh"));
	RightHandMesh->SetupAttachment(RightController);
	RightHandMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RightHandMesh->SetRelativeScale3D(FVector(0.06f));

	if (CubeFinder.Succeeded())
	{
		LeftHandMesh->SetStaticMesh(CubeFinder.Object);
		RightHandMesh->SetStaticMesh(CubeFinder.Object);
	}

	// Thin aim beam along the right controller's forward axis.
	AimBeam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("AimBeam"));
	AimBeam->SetupAttachment(RightController);
	AimBeam->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (CylinderFinder.Succeeded())
	{
		AimBeam->SetStaticMesh(CylinderFinder.Object);
	}
	AimBeam->SetRelativeRotation(FRotator(-90.f, 0.f, 0.f)); // local +Z -> +X
	AimBeam->SetRelativeLocation(FVector(750.f, 0.f, 0.f));
	AimBeam->SetRelativeScale3D(FVector(0.01f, 0.01f, 15.f));

	// Camera-anchored minimal HUD text.
	HUDText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("HUDText"));
	HUDText->SetupAttachment(Camera);
	HUDText->SetRelativeLocation(FVector(120.f, 0.f, -35.f));
	HUDText->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));
	HUDText->SetWorldSize(4.f);
	HUDText->SetHorizontalAlignment(EHTA_Center);
	HUDText->SetTextRenderColor(FColor::Cyan);

	Movement = CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("Movement"));
	Movement->MaxSpeed = 900.f;
	Movement->Acceleration = 4000.f;
	Movement->Deceleration = 4000.f;

	// World-space main menu panel, floating in front of the head (hidden until toggled).
	VRMenuComp = CreateDefaultSubobject<UWidgetComponent>(TEXT("VRMenu"));
	VRMenuComp->SetupAttachment(Camera);
	VRMenuComp->SetRelativeLocationAndRotation(FVector(140.f, 0.f, 0.f), FRotator(0.f, 180.f, 0.f));
	VRMenuComp->SetWidgetSpace(EWidgetSpace::World);
	VRMenuComp->SetDrawSize(FVector2D(900.f, 760.f));
	VRMenuComp->SetPivot(FVector2D(0.5f, 0.5f));
	VRMenuComp->SetRelativeScale3D(FVector(0.12f)); // world-cm per UMG-px, keeps it readable ~1.4m away
	// The laser interaction traces on Visibility; make the panel block only that channel
	// so the ray hits it without disturbing pawn/summon traces (which use ECC_Pawn).
	VRMenuComp->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	VRMenuComp->SetCollisionResponseToAllChannels(ECR_Ignore);
	VRMenuComp->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	VRMenuComp->SetVisibility(false);

	// Laser pointer that clicks the menu (right controller ray).
	WidgetInteraction = CreateDefaultSubobject<UWidgetInteractionComponent>(TEXT("WidgetInteraction"));
	WidgetInteraction->SetupAttachment(RightController);
	WidgetInteraction->InteractionDistance = 3000.f;
	WidgetInteraction->TraceChannel = ECC_Visibility;
	WidgetInteraction->bEnableHitTesting = true;
	WidgetInteraction->bAutoActivate = false; // only traces while the menu is open

	// Comfort tunnelling: the camera drives its own post-process vignette on movement.
	Camera->PostProcessBlendWeight = 1.f;
	Camera->PostProcessSettings.bOverride_VignetteIntensity = true;
	Camera->PostProcessSettings.VignetteIntensity = 0.4f;
}

void ASpiritVRPawn::PawnClientRestart()
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
			Subsystem->AddMappingContext(VRSpiritIMC, 1);
		}
	}

	PC->bShowMouseCursor = false;
	PC->SetInputMode(FInputModeGameOnly());

	EnsureVRMenu();
}

void ASpiritVRPawn::EnsureVRMenu()
{
	if (VRMenuWidget || !VRMenuComp)
	{
		return;
	}
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->IsLocalController())
	{
		return;
	}

	VRMenuWidget = CreateWidget<UMainMenuWidget>(PC, UMainMenuWidget::StaticClass());
	if (VRMenuWidget)
	{
		VRMenuComp->SetWidget(VRMenuWidget);
	}
	VRMenuComp->SetVisibility(false);
	PC->SetPlatformMenuOpen(false);
}

void ASpiritVRPawn::SetVRMenuOpen(bool bOpen)
{
	EnsureVRMenu();
	if (!VRMenuComp)
	{
		return;
	}

	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController()))
	{
		PC->SetPlatformMenuOpen(bOpen);
	}
	VRMenuComp->SetVisibility(bOpen);
	if (WidgetInteraction)
	{
		WidgetInteraction->SetActive(bOpen);
	}
}

void ASpiritVRPawn::ToggleVRMenu()
{
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::MenuToggle))
	{
		return;
	}
	SetVRMenuOpen(!PC->IsPlatformMenuOpen());
}

void ASpiritVRPawn::BuildInputAssets()
{
	if (VRSpiritIMC)
	{
		return;
	}

	VRSpiritIMC  = NewObject<UInputMappingContext>(this);
	IA_Move      = SpiritsInput::MakeAction(this, EInputActionValueType::Axis2D);
	IA_SnapTurn  = SpiritsInput::MakeAction(this, EInputActionValueType::Axis1D);
	IA_Vertical  = SpiritsInput::MakeAction(this, EInputActionValueType::Axis1D);
	IA_Possess   = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Summon    = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_CycleType = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Menu      = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);

	using namespace SpiritsInput;

	// Left stick: horizontal movement (also WASD for desktop debugging of the VR pawn).
	MapWASD(VRSpiritIMC, IA_Move);
	MapStick2D(VRSpiritIMC, IA_Move, EKeys::OculusTouch_Left_Thumbstick_X, EKeys::OculusTouch_Left_Thumbstick_Y);
	MapStick2D(VRSpiritIMC, IA_Move, EKeys::ValveIndex_Left_Thumbstick_X, EKeys::ValveIndex_Left_Thumbstick_Y);
	MapStick2D(VRSpiritIMC, IA_Move, EKeys::MixedReality_Left_Thumbstick_X, EKeys::MixedReality_Left_Thumbstick_Y);

	// Right stick X: snap turn.
	Map(VRSpiritIMC, IA_SnapTurn, EKeys::OculusTouch_Right_Thumbstick_X);
	Map(VRSpiritIMC, IA_SnapTurn, EKeys::ValveIndex_Right_Thumbstick_X);
	Map(VRSpiritIMC, IA_SnapTurn, EKeys::MixedReality_Right_Thumbstick_X);

	// Right stick Y: fly up/down.
	Map(VRSpiritIMC, IA_Vertical, EKeys::OculusTouch_Right_Thumbstick_Y);
	Map(VRSpiritIMC, IA_Vertical, EKeys::ValveIndex_Right_Thumbstick_Y);
	Map(VRSpiritIMC, IA_Vertical, EKeys::MixedReality_Right_Thumbstick_Y);

	// Right trigger: possess pointed minion. (LMB for desktop debugging.)
	Map(VRSpiritIMC, IA_Possess, EKeys::OculusTouch_Right_Trigger_Click);
	Map(VRSpiritIMC, IA_Possess, EKeys::ValveIndex_Right_Trigger_Click);
	Map(VRSpiritIMC, IA_Possess, EKeys::Vive_Right_Trigger_Click);
	Map(VRSpiritIMC, IA_Possess, EKeys::MixedReality_Right_Trigger_Click);
	Map(VRSpiritIMC, IA_Possess, EKeys::LeftMouseButton);

	// A: summon at pointed ground. (RMB for desktop debugging.)
	Map(VRSpiritIMC, IA_Summon, EKeys::OculusTouch_Right_A_Click);
	Map(VRSpiritIMC, IA_Summon, EKeys::ValveIndex_Right_A_Click);
	Map(VRSpiritIMC, IA_Summon, EKeys::RightMouseButton);

	// X: cycle summon archetype.
	Map(VRSpiritIMC, IA_CycleType, EKeys::OculusTouch_Left_X_Click);
	Map(VRSpiritIMC, IA_CycleType, EKeys::ValveIndex_Left_A_Click);
	Map(VRSpiritIMC, IA_CycleType, EKeys::Tab);

	// Menu toggle: left Y / Index left B / (M for desktop debugging).
	Map(VRSpiritIMC, IA_Menu, EKeys::OculusTouch_Left_Y_Click);
	Map(VRSpiritIMC, IA_Menu, EKeys::ValveIndex_Left_B_Click);
	Map(VRSpiritIMC, IA_Menu, EKeys::M);
}

void ASpiritVRPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	BuildInputAssets();

	if (UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EIC->BindAction(IA_Move, ETriggerEvent::Triggered, this, &ASpiritVRPawn::OnMoveInput);
		EIC->BindAction(IA_SnapTurn, ETriggerEvent::Triggered, this, &ASpiritVRPawn::OnSnapTurnInput);
		EIC->BindAction(IA_Vertical, ETriggerEvent::Triggered, this, &ASpiritVRPawn::OnVerticalInput);
		EIC->BindAction(IA_Possess, ETriggerEvent::Started, this, &ASpiritVRPawn::OnPossessInput);
		EIC->BindAction(IA_Possess, ETriggerEvent::Completed, this, &ASpiritVRPawn::OnTriggerReleased);
		EIC->BindAction(IA_Summon, ETriggerEvent::Started, this, &ASpiritVRPawn::OnSummonInput);
		EIC->BindAction(IA_CycleType, ETriggerEvent::Started, this, &ASpiritVRPawn::OnCycleTypeInput);
		EIC->BindAction(IA_Menu, ETriggerEvent::Started, this, &ASpiritVRPawn::OnMenuInput);
	}
}

void ASpiritVRPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (IsLocallyControlled())
	{
		UpdateHUDText();
		UpdateComfortVignette(DeltaSeconds);
	}
}

void ASpiritVRPawn::UpdateComfortVignette(float DeltaSeconds)
{
	if (!Camera)
	{
		return;
	}
	// Tunnel the periphery while moving fast to reduce vection sickness; ease back when still.
	const float Speed = GetVelocity().Size();
	const float MaxSpeed = Movement ? FMath::Max(Movement->MaxSpeed, 1.f) : 900.f;
	const float Target = 0.4f + FMath::Clamp(Speed / MaxSpeed, 0.f, 1.f) * 1.0f; // 0.4 idle -> ~1.4 moving
	const float Current = Camera->PostProcessSettings.VignetteIntensity;
	Camera->PostProcessSettings.VignetteIntensity = FMath::FInterpTo(Current, Target, DeltaSeconds, 6.f);
}

void ASpiritVRPawn::UpdateHUDText()
{
	if (!HUDText)
	{
		return;
	}

	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	const ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;
	const ASpiritsGameState* GS = GetWorld() ? GetWorld()->GetGameState<ASpiritsGameState>() : nullptr;

	FString Text;
	if (GS && GS->Phase == ESpiritsMatchPhase::Ended && PS)
	{
		Text = (GS->WinningTeam == PS->TeamId) ? TEXT("VICTORY!") : TEXT("DEFEAT");
	}
	else
	{
		const int32 Souls = PS ? PS->Souls : 0;
		FString TypeName = TEXT("?");
		int32 Cost = 0;
		if (GS && PC && PS)
		{
			const TArray<FMinionArchetype>& Options = GS->OptionsForTeam(PS->TeamId);
			if (Options.IsValidIndex(PC->SelectedArchetype))
			{
				TypeName = Options[PC->SelectedArchetype].DisplayName;
				Cost = Options[PC->SelectedArchetype].SummonCost;
			}
		}
		Text = FString::Printf(TEXT("Souls %d | %s (%d)"), Souls, *TypeName, Cost);
	}
	HUDText->SetText(FText::FromString(Text));
}

void ASpiritVRPawn::OnMoveInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Movement))
	{
		return; // hold still while any platform menu is up
	}
	const FVector2D Input = Value.Get<FVector2D>();
	const FRotator YawRot(0.f, Camera->GetComponentRotation().Yaw, 0.f);
	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::X), Input.Y);
	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::Y), Input.X);
}

void ASpiritVRPawn::OnMenuInput(const FInputActionValue& /*Value*/)
{
	ToggleVRMenu();
}

void ASpiritVRPawn::OnTriggerReleased(const FInputActionValue& /*Value*/)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (PC && PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::MenuRelease) && WidgetInteraction)
	{
		WidgetInteraction->ReleasePointerKey(EKeys::LeftMouseButton);
	}
}

void ASpiritVRPawn::OnSnapTurnInput(const FInputActionValue& Value)
{
	const float Axis = Value.Get<float>();
	if (FMath::Abs(Axis) < 0.6f)
	{
		return;
	}

	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SnapTurn))
	{
		return;
	}
	if (!ComfortTurnGate.TryAccept(FPlatformTime::Seconds()))
	{
		return;
	}
	AddActorWorldRotation(FRotator(0.f, Axis > 0.f ? 45.f : -45.f, 0.f));
}

void ASpiritVRPawn::OnVerticalInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Movement))
	{
		return;
	}
	const float Axis = Value.Get<float>();
	if (FMath::Abs(Axis) > 0.25f)
	{
		AddMovementInput(FVector::UpVector, Axis);
	}
}

bool ASpiritVRPawn::TraceFromRightController(FHitResult& OutHit) const
{
	if (!RightController || !GetWorld())
	{
		return false;
	}
	const FVector Start = RightController->GetComponentLocation();
	const FVector End = Start + RightController->GetForwardVector() * 8000.f;
	FCollisionQueryParams Params(FName(TEXT("SpiritsVRAim")), false, this);
	return GetWorld()->LineTraceSingleByChannel(OutHit, Start, End, ECC_Pawn, Params);
}

void ASpiritVRPawn::OnPossessInput(const FInputActionValue& /*Value*/)
{
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC)
	{
		return;
	}

	// While the menu is up the trigger is a UI click, never possession.
	if (PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::MenuClick))
	{
		if (WidgetInteraction)
		{
			WidgetInteraction->PressPointerKey(EKeys::LeftMouseButton);
		}
		return;
	}
	if (!PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Possession))
	{
		return;
	}

	FHitResult Hit;
	if (TraceFromRightController(Hit))
	{
		AUnitBase* Unit = Cast<AUnitBase>(Hit.GetActor());
		const ASpiritsPlayerState* PS = PC->GetPlayerState<ASpiritsPlayerState>();
		if (Unit && PS && !Unit->IsDead() && !Unit->bIsStructure && Unit->TeamId == PS->TeamId)
		{
			PC->RequestPossessMinion(Unit);
		}
	}
}

void ASpiritVRPawn::OnSummonInput(const FInputActionValue& /*Value*/)
{
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if (!PC || !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Summon))
	{
		return;
	}

	FHitResult Hit;
	if (TraceFromRightController(Hit) && !Cast<AUnitBase>(Hit.GetActor()))
	{
		PC->RequestSummon(PC->SelectedArchetype, Hit.Location);
	}
}

void ASpiritVRPawn::OnCycleTypeInput(const FInputActionValue& /*Value*/)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController()))
	{
		PC->CycleSelectedArchetype(1);
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void ASpiritVRPawn::MoveInputForAutomation(const FVector2D& Axis)
{
	OnMoveInput(FInputActionValue(Axis));
}

void ASpiritVRPawn::SnapTurnInputForAutomation(float Axis)
{
	OnSnapTurnInput(FInputActionValue(Axis));
}
#endif
