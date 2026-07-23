#include "UnitBase.h"

#include "Blueprint/UserWidget.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/WidgetComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "FXFlash.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/PlatformTime.h"
#include "IXRTrackingSystem.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "SpiritsAssets.h"
#include "SpiritsAudio.h"
#include "SpiritsVFX.h"
#include "SpiritsGameMode.h"
#include "SpiritsGameState.h"
#include "SpiritsRules.h"
#include "SpiritsHUD.h"
#include "SpiritsInputBuilder.h"
#include "SpiritsPlayerController.h"
#include "TimerManager.h"
#include "UnitAIController.h"
#include "UnitHealthBarWidget.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	bool IsHMDActive()
	{
		return GEngine && GEngine->XRSystem.IsValid() && GEngine->XRSystem->IsHeadTrackingAllowed();
	}
}

AUnitBase::AUnitBase()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	SetReplicateMovement(true);

	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.f);

	// ---------- Ghost visual rig ----------
	VisualRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot"));
	VisualRoot->SetupAttachment(GetCapsuleComponent());
	VisualRoot->SetRelativeLocation(FVector(0.f, 0.f, -18.f));

	UStaticMesh* SphereMesh = nullptr;
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
		if (SphereFinder.Succeeded()) { SphereMesh = SphereFinder.Object; }
	}
	UMaterialInterface* BasicMat = nullptr;
	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> MatFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		if (MatFinder.Succeeded()) { BasicMat = MatFinder.Object; }
	}

	auto MakePart = [&](const TCHAR* Name, USceneComponent* Parent) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		C->SetupAttachment(Parent);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		if (SphereMesh) { C->SetStaticMesh(SphereMesh); }
		if (BasicMat) { C->SetMaterial(0, BasicMat); }
		return C;
	};

	// Tapered ghost body (sphere squashed into a teardrop-ish shape)
	BodyMesh = MakePart(TEXT("GhostBody"), VisualRoot);
	BodyMesh->SetRelativeLocation(FVector(0.f, 0.f, 30.f));
	BodyMesh->SetRelativeScale3D(FVector(0.85f, 0.7f, 1.5f));
	BodyMesh->SetCastShadow(true);

	// Head
	HeadMesh = MakePart(TEXT("GhostHead"), VisualRoot);
	HeadMesh->SetRelativeLocation(FVector(6.f, 0.f, 118.f));
	HeadMesh->SetRelativeScale3D(FVector(0.52f));

	// Glowing eyes
	EyeLeft = MakePart(TEXT("EyeLeft"), HeadMesh);
	EyeLeft->SetRelativeLocation(FVector(40.f, -17.f, 8.f));
	EyeLeft->SetRelativeScale3D(FVector(0.2f, 0.17f, 0.26f));
	EyeRight = MakePart(TEXT("EyeRight"), HeadMesh);
	EyeRight->SetRelativeLocation(FVector(40.f, 17.f, 8.f));
	EyeRight->SetRelativeScale3D(FVector(0.2f, 0.17f, 0.26f));

	// Rotating soul ring at the base
	BaseRing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BaseRing"));
	BaseRing->SetupAttachment(VisualRoot);
	BaseRing->SetRelativeLocation(FVector(0.f, 0.f, -72.f));
	BaseRing->SetRelativeScale3D(FVector(1.05f));
	BaseRing->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	BaseRing->SetCastShadow(false);

	// Team-colored glow light
	GlowLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("GlowLight"));
	GlowLight->SetupAttachment(VisualRoot);
	GlowLight->SetRelativeLocation(FVector(0.f, 0.f, 60.f));
	GlowLight->SetIntensity(2600.f);
	GlowLight->SetAttenuationRadius(420.f);
	GlowLight->SetCastShadows(false);

	// ---------- UI / camera ----------
	HealthBarComp = CreateDefaultSubobject<UWidgetComponent>(TEXT("HealthBar"));
	HealthBarComp->SetupAttachment(GetCapsuleComponent());
	HealthBarComp->SetRelativeLocation(FVector(0.f, 0.f, 150.f));
	HealthBarComp->SetWidgetSpace(EWidgetSpace::World);
	HealthBarComp->SetDrawSize(FVector2D(100.f, 10.f));
	HealthBarComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(GetCapsuleComponent());
	SpringArm->TargetArmLength = 350.f;
	SpringArm->SocketOffset = FVector(0.f, 0.f, 60.f);
	SpringArm->bUsePawnControlRotation = true;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SpringArm);
	Camera->bLockToHmd = false;
	Camera->bAutoActivate = true;

	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->RotationRate = FRotator(0.f, 540.f, 0.f);
	bUseControllerRotationYaw = false;
	bUseControllerRotationPitch = false;
	bUseControllerRotationRoll = false;

	AIControllerClass = AUnitAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
}

void AUnitBase::InitUnit(const FMinionArchetype& InStats, uint8 InTeamId, ECivilization InCivilization)
{
	if (!HasAuthority())
	{
		return;
	}
	Stats = InStats;
	TeamId = InTeamId;
	Civilization = InCivilization;
	Health = Stats.MaxHP;
	GetCharacterMovement()->MaxWalkSpeed = Stats.MoveSpeed;
	ApplyVisuals();
}

void AUnitBase::BeginPlay()
{
	Super::BeginPlay();

	if (HasAuthority())
	{
		if (Health <= 0.f || Health > Stats.MaxHP)
		{
			Health = Stats.MaxHP;
		}
		GetCharacterMovement()->MaxWalkSpeed = Stats.MoveSpeed;

		if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
		{
			GM->RegisterUnit(this);
		}
	}

	if (GetNetMode() != NM_DedicatedServer)
	{
		if (BaseRing)
		{
			BaseRing->SetStaticMesh(SpiritsAssets::CircularBand());
			BaseRing->SetMaterial(0, SpiritsAssets::GlowMaterial());
		}
		if (EyeLeft) { EyeLeft->SetMaterial(0, SpiritsAssets::GlowMaterial()); }
		if (EyeRight) { EyeRight->SetMaterial(0, SpiritsAssets::GlowMaterial()); }

		HealthWidget = CreateWidget<UUnitHealthBarWidget>(GetWorld(), UUnitHealthBarWidget::StaticClass());
		if (HealthWidget && HealthBarComp)
		{
			HealthBarComp->SetWidget(HealthWidget);
		}

		// Summon flash + chime
		if (!bIsStructure)
		{
			AFXFlash::Spawn(GetWorld(), SpiritsAssets::CircularGlow(), GetActorLocation() - FVector(0, 0, 80.f),
			                FRotator::ZeroRotator, SpiritsTeams::GetTeamColor(TeamId) * 2.5f,
			                FVector(0.5f), FVector(3.f), 0.5f, 120.f);
			SpiritsAudio::PlayAt(this, TEXT("S_Summon"), GetActorLocation(), 0.7f);
		}

		// Desync hover phases so crowds don't bob in unison
		HoverTime = FMath::FRand() * 10.f;

		// Materialize: scale in from nothing over ~0.35s
		if (!bIsStructure)
		{
			SpawnAnim = 0.f;
		}
	}

	ApplyVisuals();
	OnRep_Health();
}

void AUnitBase::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// Actor channels may already be closing during teardown; clean locally only.
	CancelPendingCombat(false);
	if (HasAuthority())
	{
		if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
		{
			GM->UnregisterUnit(this);
		}
	}
	Super::EndPlay(EndPlayReason);
}

void AUnitBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (GetNetMode() != NM_DedicatedServer)
	{
		UpdateCosmetics(DeltaSeconds);
	}
}

void AUnitBase::UpdateCosmetics(float DeltaSeconds)
{
	// Health bar billboard
	if (HealthBarComp && HealthBarComp->IsVisible())
	{
		if (APlayerController* LocalPC = GetWorld()->GetFirstPlayerController())
		{
			if (LocalPC->PlayerCameraManager)
			{
				const FVector CamLoc = LocalPC->PlayerCameraManager->GetCameraLocation();
				const FRotator LookAt = (CamLoc - HealthBarComp->GetComponentLocation()).Rotation();
				HealthBarComp->SetWorldRotation(FRotator(0.f, LookAt.Yaw, 0.f));
			}
		}
	}

	if (bIsStructure || !VisualRoot)
	{
		return;
	}

	// Death: sink, shrink, fade the light, one expanding soul ring.
	if (IsDead())
	{
		DeathAnim = FMath::Min(DeathAnim + DeltaSeconds / 1.1f, 1.f);
		VisualRoot->SetRelativeLocation(FVector(0.f, 0.f, -18.f - 90.f * DeathAnim));
		VisualRoot->SetRelativeScale3D(FVector(FMath::Max(0.01f, (1.f - DeathAnim))) * FMath::Max(0.1f, Stats.MeshScale));
		if (GlowLight)
		{
			GlowLight->SetIntensity(1800.f * (1.f - DeathAnim));
		}
		if (!bDeathFXDone)
		{
			bDeathFXDone = true;
			AFXFlash::Spawn(GetWorld(), SpiritsAssets::CircularGlow(), GetActorLocation() - FVector(0, 0, 70.f),
			                FRotator::ZeroRotator, SpiritsTeams::GetTeamColor(TeamId) * 3.f,
			                FVector(0.3f), FVector(3.5f), 0.6f, 40.f);
		}
		return;
	}

	// Hover bob + sway
	HoverTime += DeltaSeconds;
	const float BobSpeed = 2.2f / FMath::Max(0.6f, Stats.MeshScale);
	const float Bob = FMath::Sin(HoverTime * BobSpeed) * 7.f;
	const float Sway = FMath::Sin(HoverTime * BobSpeed * 0.63f) * 2.5f;

	// Lean into movement
	const float Speed2D = GetVelocity().Size2D();
	const float TargetLean = FMath::Clamp(Speed2D / FMath::Max(200.f, Stats.MoveSpeed), 0.f, 1.f) * 14.f;
	CurrentLean = FMath::FInterpTo(CurrentLean, TargetLean, DeltaSeconds, 6.f);

	// Heavy windup: wind the body back and tilt up, building tension.
	float HeavyPull = 0.f;
	if (bHeavyCharging)
	{
		HeavyChargeTime = FMath::Min(HeavyChargeTime + DeltaSeconds, HeavyWindup);
		const float Charge = HeavyChargeTime / HeavyWindup; // 0..1
		HeavyPull = -34.f * Charge; // lean/pull backwards
	}

	// Attack lunge (heavy release lunges ~1.9x further than a light swing).
	float Lunge = 0.f;
	if (AttackAnim > 0.f)
	{
		const float LungeAmp = 34.f * (bHeavyLunge ? 1.9f : 1.f);
		Lunge = FMath::Sin(AttackAnim * PI) * LungeAmp;
		AttackAnim = FMath::Max(0.f, AttackAnim - DeltaSeconds / (bHeavyLunge ? 0.34f : 0.28f));
		if (AttackAnim <= 0.f)
		{
			bHeavyLunge = false;
		}
	}

	const float FwdOffset = Lunge + HeavyPull;
	VisualRoot->SetRelativeLocation(FVector(FwdOffset, Sway, -18.f + Bob));
	VisualRoot->SetRelativeRotation(FRotator(-CurrentLean - FwdOffset * 0.35f, 0.f, Sway * 0.6f));

	// Materialize scale-in
	if (SpawnAnim < 1.f)
	{
		SpawnAnim = FMath::Min(1.f, SpawnAnim + DeltaSeconds / 0.35f);
		const float Ease = SpawnAnim * SpawnAnim * (3.f - 2.f * SpawnAnim);
		VisualRoot->SetRelativeScale3D(FVector(FMath::Max(0.02f, Ease) * FMath::Max(0.1f, Stats.MeshScale)));
	}

	// Spin the soul ring
	if (BaseRing)
	{
		BaseRing->AddLocalRotation(FRotator(0.f, 140.f * DeltaSeconds, 0.f));
	}

	// Eye glow pulse
	const float Pulse = 2.6f + FMath::Sin(HoverTime * 3.1f) * 0.9f;
	const FLinearColor EyeColor = SpiritsTeams::GetTeamColor(TeamId) * Pulse + FLinearColor(0.4f, 0.4f, 0.4f);
	SpiritsAssets::SetColor(EyeMIDL, EyeColor);
	SpiritsAssets::SetColor(EyeMIDR, EyeColor);

	// White hit-flash decay (Sakurai: the victim must visibly "take" the hit).
	if (DamageFlash > 0.f && BodyMID)
	{
		DamageFlash = FMath::Max(0.f, DamageFlash - DeltaSeconds / 0.18f);
		const FLinearColor Base = SpiritsTeams::GetTeamColor(TeamId) * Stats.Tint * 0.5f + FLinearColor(0.03f, 0.03f, 0.06f);
		SpiritsAssets::SetColor(BodyMID, FMath::Lerp(Base, FLinearColor(2.5f, 2.5f, 2.5f), DamageFlash));
	}
}

void AUnitBase::ApplyVisuals()
{
	const FLinearColor TeamColor = SpiritsTeams::GetTeamColor(TeamId);
	const FLinearColor Tinted = TeamColor * Stats.Tint;

	if (BodyMesh)
	{
		// M_UnitBody is the required PatternTex hook generated by the asset
		// pipeline. Keep the primitive material only as a development fallback;
		// missing generated content is reported by LoadRequiredTexture below.
		if (UMaterialInterface* UnitBody = SpiritsAssets::UnitBodyMaterial())
		{
			if (BodyMesh->GetMaterial(0) != UnitBody)
			{
				BodyMesh->SetMaterial(0, UnitBody);
				BodyMID = nullptr;
			}
		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=BodyMID.PatternTex material=/Game/Materials/M_UnitBody"));
		}
		if (!BodyMID) { BodyMID = BodyMesh->CreateAndSetMaterialInstanceDynamic(0); }
		SpiritsAssets::SetColor(BodyMID, Tinted * 0.5f + FLinearColor(0.03f, 0.03f, 0.06f));
		UTexture2D* Pattern = SpiritsAssets::CivilizationPattern(static_cast<int32>(Civilization));
		if (Pattern && !SpiritsAssets::SetTexture(BodyMID, Pattern, TEXT("PatternTex")))
		{
			UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=BodyMID.PatternTex civilization=%d"), static_cast<int32>(Civilization));
		}
	}
	if (HeadMesh)
	{
		if (!HeadMID) { HeadMID = HeadMesh->CreateAndSetMaterialInstanceDynamic(0); }
		SpiritsAssets::SetColor(HeadMID, Tinted * 0.7f + FLinearColor(0.04f, 0.04f, 0.07f));
	}
	if (EyeLeft && !EyeMIDL) { EyeMIDL = EyeLeft->CreateAndSetMaterialInstanceDynamic(0); }
	if (EyeRight && !EyeMIDR) { EyeMIDR = EyeRight->CreateAndSetMaterialInstanceDynamic(0); }
	if (BaseRing)
	{
		if (!RingMID) { RingMID = BaseRing->CreateAndSetMaterialInstanceDynamic(0); }
		SpiritsAssets::SetColor(RingMID, Tinted * 3.2f);
	}
	if (GlowLight)
	{
		GlowLight->SetLightColor(TeamColor);
	}
	if (VisualRoot && !IsDead())
	{
		VisualRoot->SetRelativeScale3D(FVector(FMath::Max(0.1f, Stats.MeshScale)));
	}
	if (HealthWidget)
	{
		HealthWidget->SetBarColor(TeamColor);
	}

	GetCharacterMovement()->MaxWalkSpeed = Stats.MoveSpeed;
}

void AUnitBase::OnRep_Visuals()
{
	ApplyVisuals();
}

void AUnitBase::OnRep_Health()
{
	if (HealthWidget)
	{
		HealthWidget->SetHealthPercent(GetHealthPercent());
	}

	if (IsDead() && HealthBarComp)
	{
		HealthBarComp->SetVisibility(false);
	}
	if (IsDead() && !bDeathSoundPlayed && GetNetMode() != NM_DedicatedServer)
	{
		bDeathSoundPlayed = true;
		SpiritsAudio::PlayAt(this, TEXT("S_Death"), GetActorLocation(), bIsStructure ? 1.f : 0.6f);
	}
}

float AUnitBase::TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent,
                            AController* EventInstigator, AActor* DamageCauser)
{
	if (!HasAuthority() || IsDead() || DamageAmount <= 0.f)
	{
		return 0.f;
	}

	const float Applied = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	Health = FMath::Max(0.f, Health - DamageAmount);
	OnRep_Health(); // listen server visuals

	Multicast_DamageFX(DamageAmount, GetActorLocation() + FVector(0.f, 0.f, 110.f));

	// Attribution: shrines raise a rate-limited global alarm when hit.
	if (bIsStructure)
	{
		if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
		{
			GM->NotifyShrineDamaged(this);
		}
	}

	if (Health <= 0.f)
	{
		HandleDeath(EventInstigator);
	}
	return Applied > 0.f ? Applied : DamageAmount;
}

void AUnitBase::Multicast_DamageFX_Implementation(float Amount, FVector_NetQuantize Location)
{
	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	DamageFlash = 1.f; // white hit-flash, decays in UpdateCosmetics

	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (ASpiritsHUD* HUD = PC ? Cast<ASpiritsHUD>(PC->GetHUD()) : nullptr)
	{
		HUD->AddDamageNumber(Location, Amount);
	}
}

void AUnitBase::HandleDeath(AController* Killer)
{
	if (bDeathHandled || !HasAuthority())
	{
		return;
	}
	bDeathHandled = true;
	Health = 0.f;
	CancelPendingCombat();

	if (ASpiritsGameMode* GM = GetWorld()->GetAuthGameMode<ASpiritsGameMode>())
	{
		GM->NotifyUnitDied(this, Killer);
	}

	// Kick out a possessing player, or clean up the AI controller.
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController()))
	{
		PC->ServerReturnToSpirit();
	}
	else if (AController* AI = GetController())
	{
		AI->UnPossess();
		AI->Destroy();
	}

	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GetCharacterMovement()->StopMovementImmediately();
	GetCharacterMovement()->DisableMovement();
	SetLifeSpan(3.f);
}

bool AUnitBase::CanResolveCombat_Server() const
{
	const UWorld* World = GetWorld();
	const ASpiritsGameState* GS = World ? World->GetGameState<ASpiritsGameState>() : nullptr;
	return HasAuthority() && GS && SpiritsRules::CanResolveCombat(GS->Phase, !IsDead(), bIsStructure);
}

void AUnitBase::CancelPendingCombat(bool bBroadcastCancellation)
{
	UWorld* World = GetWorld();
	if (World)
	{
		World->GetTimerManager().ClearTimer(HeavyWindupHandle);
		World->GetTimerManager().ClearTimer(HitStopHandle);
	}

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		if (HeavySavedWalkSpeed > 0.f)
		{
			Move->MaxWalkSpeed = HeavySavedWalkSpeed;
		}
	}
	HeavySavedWalkSpeed = 0.f;
	HeavyWindupEndTime = 0.f;
	CustomTimeDilation = 1.f;
	bHeavyCharging = false;
	bHeavyLunge = false;
	HeavyChargeTime = 0.f;

	if (HasAuthority() && bBroadcastCancellation)
	{
#if WITH_DEV_AUTOMATION_TESTS
		// Count the authoritative RPC dispatch, not local implementation delivery;
		// transient automation worlds intentionally have no net driver.
		++CombatCancellationBroadcastCount;
#endif
		Multicast_CancelHeavyFX();
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void AUnitBase::PrimePendingCombatForAutomation()
{
	bHeavyCharging = true;
	bHeavyLunge = true;
	HeavyChargeTime = 0.2f;
	HeavyWindupEndTime = 30.f;
	HeavySavedWalkSpeed = GetCharacterMovement() ? GetCharacterMovement()->MaxWalkSpeed : 600.f;
	CustomTimeDilation = 0.12f;

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(HeavyWindupHandle, FTimerDelegate::CreateLambda([] {}), 30.f, false);
		World->GetTimerManager().SetTimer(HitStopHandle, FTimerDelegate::CreateLambda([] {}), 30.f, false);
	}
}

bool AUnitBase::HasPendingCombatForAutomation() const
{
	const UWorld* World = GetWorld();
	const bool bTimerPending = World &&
		(World->GetTimerManager().IsTimerActive(HeavyWindupHandle) ||
		 World->GetTimerManager().IsTimerActive(HitStopHandle));
	return bTimerPending || HeavyWindupEndTime > 0.f || HeavySavedWalkSpeed > 0.f ||
		bHeavyCharging || bHeavyLunge || HeavyChargeTime > 0.f || !FMath::IsNearlyEqual(CustomTimeDilation, 1.f);
}
#endif

void AUnitBase::Multicast_CancelHeavyFX_Implementation()
{
	bHeavyCharging = false;
	bHeavyLunge = false;
	HeavyChargeTime = 0.f;
	CustomTimeDilation = 1.f;
}

void AUnitBase::TryAttack()
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((PC && !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::LightAttack)) ||
		bIsStructure || IsDead())
	{
		return;
	}
	if (HasAuthority())
	{
		PerformAttack_Server();
	}
	else
	{
		Server_TryAttack();
	}
}

void AUnitBase::Server_TryAttack_Implementation()
{
	if (CanResolveCombat_Server())
	{
		PerformAttack_Server();
	}
}

void AUnitBase::PerformAttack_Server()
{
	if (!CanResolveCombat_Server())
	{
		return;
	}
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();
	// Locked out while a heavy attack is winding up (can't cancel the commitment).
	if (HeavyWindupEndTime > 0.f && Now < HeavyWindupEndTime)
	{
		return;
	}
	if (Now - LastAttackTime < Stats.AttackInterval)
	{
		return;
	}
	LastAttackTime = Now;

	// Design: possession is the hero mechanic — player-driven units hit 35% harder.
	const bool bPlayerDriven = GetController() && GetController()->IsPlayerController();
	const float Damage = Stats.AttackDamage * (bPlayerDriven ? 1.35f : 1.f);

	const FVector Forward = GetActorForwardVector();
	const FVector Start = GetActorLocation() + Forward * GetCapsuleComponent()->GetScaledCapsuleRadius();
	const FVector End = GetActorLocation() + Forward * FMath::Max(Stats.AttackRange, 100.f);

	TArray<FHitResult> Hits;
	FCollisionQueryParams Params(FName(TEXT("SpiritsMelee")), false, this);
	World->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Pawn,
	                           FCollisionShape::MakeSphere(60.f), Params);

	bool bHitEnemy = false;
	FVector FXEnd = End;
	for (const FHitResult& Hit : Hits)
	{
		AUnitBase* Target = Cast<AUnitBase>(Hit.GetActor());
		if (Target && Target != this && !Target->IsDead() && Target->TeamId != TeamId)
		{
			UGameplayStatics::ApplyDamage(Target, Damage, GetController(), this, UDamageType::StaticClass());

			// Sakurai pass: impact = knockback the victim (replicates via movement).
			if (!Target->bIsStructure)
			{
				const FVector KnockDir = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
				Target->LaunchCharacter(KnockDir * 240.f + FVector(0.f, 0.f, 90.f), true, false);
			}

			bHitEnemy = true;
			FXEnd = Hit.ImpactPoint;
			break;
		}
	}

	Multicast_AttackFX(FXEnd, bHitEnemy);
}

void AUnitBase::Multicast_AttackFX_Implementation(FVector_NetQuantize TraceEnd, bool bHit)
{
	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}

	AttackAnim = 1.f;

	const FLinearColor SlashColor = SpiritsTeams::GetTeamColor(TeamId) * 3.f + FLinearColor(0.5f, 0.5f, 0.5f);
	const FVector Forward = GetActorForwardVector();
	const FVector SlashLoc = GetActorLocation() + Forward * 85.f + FVector(0.f, 0.f, 35.f);
	const FRotator SlashRot = (Forward.Rotation() + FRotator(0.f, -45.f, 0.f));

	AFXFlash::Spawn(GetWorld(), SpiritsAssets::QuarterCylinder(), SlashLoc, SlashRot,
	                SlashColor, FVector(0.9f, 0.9f, 0.10f), FVector(1.7f, 1.7f, 0.02f), 0.18f);
	// Real VFX if the asset exists (/Game/VFX/NS_SlashLight); null-safe otherwise.
	SpiritsVFX::SpawnAt(this, TEXT("NS_SlashLight"), SlashLoc, SlashRot, SpiritsTeams::GetTeamColor(TeamId), 1.f);
	SpiritsAudio::PlayAt(this, TEXT("S_Attack"), GetActorLocation(), 0.5f);

	if (bHit)
	{
		AFXFlash::Spawn(GetWorld(), SpiritsAssets::Sphere(), TraceEnd, FRotator::ZeroRotator,
		                FLinearColor(3.f, 2.6f, 1.2f), FVector(0.25f), FVector(1.1f), 0.22f);
		SpiritsAudio::PlayAt(this, TEXT("S_Hit"), TraceEnd, 0.8f);

		// Sakurai pass: hit stop — the attacker freezes for a few frames on contact.
		CustomTimeDilation = 0.12f;
		TWeakObjectPtr<AUnitBase> WeakThis(this);
		GetWorld()->GetTimerManager().SetTimer(HitStopHandle, [WeakThis]()
		{
			if (WeakThis.IsValid())
			{
				WeakThis->CustomTimeDilation = 1.f;
			}
		}, 0.07f, false);
	}
}

// ------------------------------------------------------------------ Heavy attack

void AUnitBase::TryHeavyAttack()
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((PC && !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::HeavyAttack)) ||
		bIsStructure || IsDead())
	{
		return;
	}
	if (HasAuthority())
	{
		BeginHeavy_Server();
	}
	else
	{
		Server_TryHeavyAttack();
	}
}

void AUnitBase::Server_TryHeavyAttack_Implementation()
{
	if (CanResolveCombat_Server())
	{
		BeginHeavy_Server();
	}
}

void AUnitBase::BeginHeavy_Server()
{
	if (!CanResolveCombat_Server())
	{
		return;
	}
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const float Now = World->GetTimeSeconds();

	// Already committed to a windup, or still on cooldown → ignore.
	if (HeavyWindupEndTime > 0.f && Now < HeavyWindupEndTime)
	{
		return;
	}
	if (Now - LastHeavyTime < Stats.AttackInterval * HeavyCooldownMult)
	{
		return;
	}
	LastHeavyTime = Now;
	HeavyWindupEndTime = Now + HeavyWindup;

	// Commitment: movement crawls during the windup (Sakurai: the tell is the cost).
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		HeavySavedWalkSpeed = Move->MaxWalkSpeed;
		Move->MaxWalkSpeed = HeavySavedWalkSpeed * 0.35f;
	}

	Multicast_HeavyWindupFX();

	TWeakObjectPtr<AUnitBase> WeakThis(this);
	World->GetTimerManager().SetTimer(HeavyWindupHandle, [WeakThis]()
	{
		if (WeakThis.IsValid())
		{
			WeakThis->PerformHeavy_Server();
		}
	}, HeavyWindup, false);
}

void AUnitBase::PerformHeavy_Server()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!CanResolveCombat_Server())
	{
		CancelPendingCombat();
		return;
	}

	// Restore mobility and clear the windup lock.
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		if (HeavySavedWalkSpeed > 0.f)
		{
			Move->MaxWalkSpeed = HeavySavedWalkSpeed;
		}
	}
	HeavySavedWalkSpeed = 0.f;
	HeavyWindupEndTime = 0.f;

	// Interrupted by death or match end mid-windup: bail without swinging.
	if (IsDead())
	{
		return;
	}

	// Gate the light attack briefly so heavy → light can't double-dip.
	LastAttackTime = World->GetTimeSeconds();

	const bool bPlayerDriven = GetController() && GetController()->IsPlayerController();
	const float Damage = Stats.AttackDamage * HeavyDamageMult * (bPlayerDriven ? 1.35f : 1.f);

	const FVector Forward = GetActorForwardVector();
	const FVector Start = GetActorLocation() + Forward * GetCapsuleComponent()->GetScaledCapsuleRadius();
	const FVector End = GetActorLocation() + Forward * FMath::Max(Stats.AttackRange * HeavyRangeMult, 120.f);

	TArray<FHitResult> Hits;
	FCollisionQueryParams Params(FName(TEXT("SpiritsHeavy")), false, this);
	World->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Pawn,
	                           FCollisionShape::MakeSphere(HeavyRadius), Params);

	bool bHitEnemy = false;
	FVector FXEnd = End;
	for (const FHitResult& Hit : Hits)
	{
		AUnitBase* Target = Cast<AUnitBase>(Hit.GetActor());
		if (Target && Target != this && !Target->IsDead() && Target->TeamId != TeamId)
		{
			UGameplayStatics::ApplyDamage(Target, Damage, GetController(), this, UDamageType::StaticClass());

			// Heavier launch: knock the victim back and up harder than a light hit.
			if (!Target->bIsStructure)
			{
				const FVector KnockDir = (Target->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
				Target->LaunchCharacter(KnockDir * HeavyKnockback + FVector(0.f, 0.f, 180.f), true, true);
			}

			bHitEnemy = true;
			FXEnd = Hit.ImpactPoint;
			// Note: no break — a heavy swing cleaves everything in the arc.
		}
	}

	Multicast_HeavyFX(FXEnd, bHitEnemy);
}

void AUnitBase::Multicast_HeavyWindupFX_Implementation()
{
	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	bHeavyCharging = true;
	HeavyChargeTime = 0.f;

	// Low, building charge tone (reuses the attack cue at a lower pitch; null-safe).
	SpiritsAudio::PlayAt(this, TEXT("S_Attack"), GetActorLocation(), 0.4f);
}

void AUnitBase::Multicast_HeavyFX_Implementation(FVector_NetQuantize TraceEnd, bool bHit)
{
	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}

	bHeavyCharging = false;
	bHeavyLunge = true;
	AttackAnim = 1.f;

	const FLinearColor SlashColor = SpiritsTeams::GetTeamColor(TeamId) * 4.2f + FLinearColor(0.7f, 0.7f, 0.7f);
	const FVector Forward = GetActorForwardVector();
	const FVector SlashLoc = GetActorLocation() + Forward * 100.f + FVector(0.f, 0.f, 35.f);
	const FRotator SlashRot = (Forward.Rotation() + FRotator(0.f, -55.f, 0.f));

	// Bigger, slower arc than a light swing.
	AFXFlash::Spawn(GetWorld(), SpiritsAssets::QuarterCylinder(), SlashLoc, SlashRot,
	                SlashColor, FVector(1.4f, 1.4f, 0.14f), FVector(2.7f, 2.7f, 0.03f), 0.28f);
	// Real VFX if the asset exists (/Game/VFX/NS_SlashHeavy); null-safe otherwise.
	SpiritsVFX::SpawnAt(this, TEXT("NS_SlashHeavy"), SlashLoc, SlashRot, SpiritsTeams::GetTeamColor(TeamId), 1.6f);
	SpiritsAudio::PlayAt(this, TEXT("S_Attack"), GetActorLocation(), 0.75f, 0.7f);

	if (bHit)
	{
		AFXFlash::Spawn(GetWorld(), SpiritsAssets::Sphere(), TraceEnd, FRotator::ZeroRotator,
		                FLinearColor(4.f, 3.2f, 1.4f), FVector(0.4f), FVector(1.8f), 0.3f);
		SpiritsAudio::PlayAt(this, TEXT("S_Hit"), TraceEnd, 1.f, 0.75f);

		// Stronger, longer hit stop than a light attack.
		CustomTimeDilation = 0.1f;
		TWeakObjectPtr<AUnitBase> WeakThis(this);
		GetWorld()->GetTimerManager().SetTimer(HitStopHandle, [WeakThis]()
		{
			if (WeakThis.IsValid())
			{
				WeakThis->CustomTimeDilation = 1.f;
			}
		}, HeavyHitStop, false);
	}
}

void AUnitBase::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);

	const bool bPlayer = NewController && NewController->IsPlayerController();
	bUseControllerRotationYaw = bPlayer;
	GetCharacterMovement()->bOrientRotationToMovement = !bPlayer;
	// Possession hero buff: +20% move speed while player-driven.
	GetCharacterMovement()->MaxWalkSpeed = Stats.MoveSpeed * (bPlayer ? 1.2f : 1.f);
}

void AUnitBase::UnPossessed()
{
	Super::UnPossessed();
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->MaxWalkSpeed = Stats.MoveSpeed;
}

void AUnitBase::PawnClientRestart()
{
	Super::PawnClientRestart();

	APlayerController* PC = Cast<APlayerController>(GetController());
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
			Subsystem->AddMappingContext(PossessedIMC, 1);
		}
	}

	// Possessed mode uses mouse-look: hide the cursor.
	PC->bShowMouseCursor = false;
	PC->SetInputMode(FInputModeGameOnly());

	// VR: first person view locked to HMD; PC: third person spring arm.
	if (IsHMDActive())
	{
		Camera->AttachToComponent(GetCapsuleComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
		Camera->SetRelativeLocation(FVector(0.f, 0.f, 70.f));
		Camera->SetRelativeRotation(FRotator::ZeroRotator);
		Camera->bLockToHmd = true;
		bUseControllerRotationPitch = false;
	}
	else
	{
		Camera->AttachToComponent(SpringArm, FAttachmentTransformRules::SnapToTargetNotIncludingScale, USpringArmComponent::SocketName);
		Camera->SetRelativeLocation(FVector::ZeroVector);
		Camera->SetRelativeRotation(FRotator::ZeroRotator);
		Camera->bLockToHmd = false;
	}
}

void AUnitBase::BuildInputAssets()
{
	if (PossessedIMC)
	{
		return;
	}

	PossessedIMC = NewObject<UInputMappingContext>(this);
	IA_Move        = SpiritsInput::MakeAction(this, EInputActionValueType::Axis2D);
	IA_Look        = SpiritsInput::MakeAction(this, EInputActionValueType::Axis2D);
	IA_Attack      = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_HeavyAttack = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Unpossess   = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_Jump        = SpiritsInput::MakeAction(this, EInputActionValueType::Boolean);
	IA_SnapTurn    = SpiritsInput::MakeAction(this, EInputActionValueType::Axis1D);

	using namespace SpiritsInput;

	// Move: WASD + VR left thumbsticks
	MapWASD(PossessedIMC, IA_Move);
	MapStick2D(PossessedIMC, IA_Move, EKeys::OculusTouch_Left_Thumbstick_X, EKeys::OculusTouch_Left_Thumbstick_Y);
	MapStick2D(PossessedIMC, IA_Move, EKeys::ValveIndex_Left_Thumbstick_X, EKeys::ValveIndex_Left_Thumbstick_Y);
	MapStick2D(PossessedIMC, IA_Move, EKeys::MixedReality_Left_Thumbstick_X, EKeys::MixedReality_Left_Thumbstick_Y);

	// Look: mouse (Y inverted for natural pitch)
	MapNegate(PossessedIMC, IA_Look, EKeys::Mouse2D, false, true, false);

	// Snap turn: VR right thumbstick X
	Map(PossessedIMC, IA_SnapTurn, EKeys::OculusTouch_Right_Thumbstick_X);
	Map(PossessedIMC, IA_SnapTurn, EKeys::ValveIndex_Right_Thumbstick_X);
	Map(PossessedIMC, IA_SnapTurn, EKeys::MixedReality_Right_Thumbstick_X);

	// Attack: LMB + VR right trigger
	Map(PossessedIMC, IA_Attack, EKeys::LeftMouseButton);
	Map(PossessedIMC, IA_Attack, EKeys::OculusTouch_Right_Trigger_Click);
	Map(PossessedIMC, IA_Attack, EKeys::ValveIndex_Right_Trigger_Click);
	Map(PossessedIMC, IA_Attack, EKeys::Vive_Right_Trigger_Click);
	Map(PossessedIMC, IA_Attack, EKeys::MixedReality_Right_Trigger_Click);

	// Heavy attack: RMB + VR LEFT trigger (committed, high-reward swing).
	// Left trigger exists on every headset (Index has no *_Grip_Click), so this
	// gives all VR players a dedicated heavy button while the right trigger stays light.
	Map(PossessedIMC, IA_HeavyAttack, EKeys::RightMouseButton);
	Map(PossessedIMC, IA_HeavyAttack, EKeys::OculusTouch_Left_Trigger_Click);
	Map(PossessedIMC, IA_HeavyAttack, EKeys::ValveIndex_Left_Trigger_Click);
	Map(PossessedIMC, IA_HeavyAttack, EKeys::Vive_Left_Trigger_Click);
	Map(PossessedIMC, IA_HeavyAttack, EKeys::MixedReality_Left_Trigger_Click);

	// Jump: Space + VR A button
	Map(PossessedIMC, IA_Jump, EKeys::SpaceBar);
	Map(PossessedIMC, IA_Jump, EKeys::OculusTouch_Right_A_Click);
	Map(PossessedIMC, IA_Jump, EKeys::ValveIndex_Right_A_Click);

	// Unpossess (return to spirit): Q + VR B button
	Map(PossessedIMC, IA_Unpossess, EKeys::Q);
	Map(PossessedIMC, IA_Unpossess, EKeys::Escape);
	Map(PossessedIMC, IA_Unpossess, EKeys::OculusTouch_Right_B_Click);
	Map(PossessedIMC, IA_Unpossess, EKeys::ValveIndex_Right_B_Click);
}

void AUnitBase::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	BuildInputAssets();

	if (UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EIC->BindAction(IA_Move, ETriggerEvent::Triggered, this, &AUnitBase::OnMoveInput);
		EIC->BindAction(IA_Look, ETriggerEvent::Triggered, this, &AUnitBase::OnLookInput);
		EIC->BindAction(IA_SnapTurn, ETriggerEvent::Triggered, this, &AUnitBase::OnSnapTurnInput);
		EIC->BindAction(IA_Attack, ETriggerEvent::Started, this, &AUnitBase::OnAttackInput);
		EIC->BindAction(IA_HeavyAttack, ETriggerEvent::Started, this, &AUnitBase::OnHeavyAttackInput);
		EIC->BindAction(IA_Jump, ETriggerEvent::Started, this, &AUnitBase::OnJumpInput);
		EIC->BindAction(IA_Unpossess, ETriggerEvent::Started, this, &AUnitBase::OnUnpossessInput);
	}
}

void AUnitBase::OnMoveInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((PC && !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Movement)) || IsDead())
	{
		return;
	}
	const FVector2D Input = Value.Get<FVector2D>();

	FRotator YawRot;
	if (IsHMDActive() && Camera)
	{
		YawRot = FRotator(0.f, Camera->GetComponentRotation().Yaw, 0.f);
	}
	else
	{
		YawRot = FRotator(0.f, GetControlRotation().Yaw, 0.f);
	}

	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::X), Input.Y);
	AddMovementInput(FRotationMatrix(YawRot).GetUnitAxis(EAxis::Y), Input.X);
}

void AUnitBase::OnLookInput(const FInputActionValue& Value)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((PC && !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::View)) || IsHMDActive())
	{
		return; // menu blocks view; HMD drives the view in VR
	}
	const FVector2D Input = Value.Get<FVector2D>();
	AddControllerYawInput(Input.X);
	AddControllerPitchInput(Input.Y);
}

void AUnitBase::OnSnapTurnInput(const FInputActionValue& Value)
{
	const float Axis = Value.Get<float>();
	if (FMath::Abs(Axis) < 0.6f)
	{
		return;
	}

	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((PC && !PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::SnapTurn)) ||
		!ComfortTurnGate.TryAccept(FPlatformTime::Seconds()))
	{
		return;
	}

	if (AController* C = GetController())
	{
		FRotator Rot = C->GetControlRotation();
		Rot.Yaw += (Axis > 0.f ? 45.f : -45.f);
		C->SetControlRotation(Rot);
	}
}

void AUnitBase::OnAttackInput(const FInputActionValue& /*Value*/)
{
	TryAttack();
}

void AUnitBase::OnHeavyAttackInput(const FInputActionValue& /*Value*/)
{
	TryHeavyAttack();
}

void AUnitBase::OnJumpInput(const FInputActionValue& /*Value*/)
{
	const ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController());
	if ((!PC || PC->CanDispatchPlatformAction(SpiritsPlatform::EPlatformAction::Movement)) && !IsDead())
	{
		Jump();
	}
}

void AUnitBase::OnUnpossessInput(const FInputActionValue& /*Value*/)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetController()))
	{
		PC->RequestUnpossess();
	}
}

void AUnitBase::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AUnitBase, Stats);
	DOREPLIFETIME(AUnitBase, TeamId);
	DOREPLIFETIME(AUnitBase, Civilization);
	DOREPLIFETIME(AUnitBase, Health);
	DOREPLIFETIME(AUnitBase, bIsStructure);
}
