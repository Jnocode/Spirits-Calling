#include "SoulShrine.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/WidgetComponent.h"
#include "FXFlash.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SpiritsAssets.h"

ASoulShrine::ASoulShrine()
{
	bIsStructure = true;
	AutoPossessAI = EAutoPossessAI::Disabled;
	AIControllerClass = nullptr;

	GetCapsuleComponent()->InitCapsuleSize(150.f, 240.f);
	// Constructor-safe immobilization (avoid SetMovementMode on the CDO).
	GetCharacterMovement()->DefaultLandMovementMode = MOVE_None;
	GetCharacterMovement()->GravityScale = 0.f;

	// Hide the ghost rig from the base class.
	if (BodyMesh)  { BodyMesh->SetVisibility(false); }
	if (HeadMesh)  { HeadMesh->SetVisibility(false); }
	if (EyeLeft)   { EyeLeft->SetVisibility(false); }
	if (EyeRight)  { EyeRight->SetVisibility(false); }
	if (BaseRing)  { BaseRing->SetVisibility(false); }

	auto MakePart = [&](const TCHAR* Name) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		C->SetupAttachment(GetCapsuleComponent());
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		return C;
	};

	Obelisk = MakePart(TEXT("Obelisk"));
	Obelisk->SetRelativeLocation(FVector(0.f, 0.f, -60.f));
	Obelisk->SetRelativeScale3D(FVector(1.7f, 1.7f, 3.6f));
	Obelisk->SetCastShadow(true);

	Crystal = MakePart(TEXT("Crystal"));
	Crystal->SetRelativeLocation(FVector(0.f, 0.f, 250.f));
	Crystal->SetRelativeScale3D(FVector(0.9f));
	Crystal->SetRelativeRotation(FRotator(45.f, 0.f, 45.f));

	RingA = MakePart(TEXT("RingA"));
	RingA->SetRelativeLocation(FVector(0.f, 0.f, 60.f));
	RingA->SetRelativeScale3D(FVector(3.4f));

	RingB = MakePart(TEXT("RingB"));
	RingB->SetRelativeLocation(FVector(0.f, 0.f, 140.f));
	RingB->SetRelativeScale3D(FVector(2.6f));

	BaseGlow = MakePart(TEXT("BaseGlow"));
	BaseGlow->SetRelativeLocation(FVector(0.f, 0.f, -232.f));
	BaseGlow->SetRelativeScale3D(FVector(5.5f));

	if (GlowLight)
	{
		GlowLight->SetRelativeLocation(FVector(0.f, 0.f, 180.f));
		GlowLight->SetIntensity(9000.f);
		GlowLight->SetAttenuationRadius(1400.f);
	}
	if (HealthBarComp)
	{
		HealthBarComp->SetRelativeLocation(FVector(0.f, 0.f, 330.f));
		HealthBarComp->SetDrawSize(FVector2D(220.f, 16.f));
	}

	Stats.DisplayName = TEXT("Soul Shrine");
	Stats.MaxHP = 1500.f;
	Stats.AttackDamage = 0.f;
	Stats.MoveSpeed = 0.f;
	Stats.MeshScale = 1.f;
	Stats.Tint = FLinearColor::White;
	Health = Stats.MaxHP;
}

void ASoulShrine::BeginPlay()
{
	Super::BeginPlay();

	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}

	if (Obelisk)
	{
		Obelisk->SetStaticMesh(SpiritsAssets::ChamferCube());
		UMaterialInterface* ShrineMaterial = SpiritsAssets::UnitBodyMaterial();
		if (!ShrineMaterial)
		{
			UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=SoulShrine.PatternTex material=/Game/Materials/M_UnitBody"));
		}
		Obelisk->SetMaterial(0, ShrineMaterial ? ShrineMaterial : SpiritsAssets::GridMaterialGray());
		ObeliskMID = Obelisk->CreateAndSetMaterialInstanceDynamic(0);
	}
	if (Crystal)
	{
		Crystal->SetStaticMesh(SpiritsAssets::ChamferCube());
		Crystal->SetMaterial(0, SpiritsAssets::GlowMaterial());
		CrystalMID = Crystal->CreateAndSetMaterialInstanceDynamic(0);
	}
	if (RingA)
	{
		RingA->SetStaticMesh(SpiritsAssets::CircularBand());
		RingA->SetMaterial(0, SpiritsAssets::GlowMaterial());
		RingAMID = RingA->CreateAndSetMaterialInstanceDynamic(0);
	}
	if (RingB)
	{
		RingB->SetStaticMesh(SpiritsAssets::CircularBand());
		RingB->SetMaterial(0, SpiritsAssets::GlowMaterial());
		RingBMID = RingB->CreateAndSetMaterialInstanceDynamic(0);
	}
	if (BaseGlow)
	{
		BaseGlow->SetStaticMesh(SpiritsAssets::CircularGlow());
		BaseGlow->SetMaterial(0, SpiritsAssets::GlowMaterial());
		BaseGlowMID = BaseGlow->CreateAndSetMaterialInstanceDynamic(0);
	}

	ApplyVisuals();
}

void ASoulShrine::ApplyVisuals()
{
	Super::ApplyVisuals();

	const FLinearColor TeamColor = SpiritsTeams::GetTeamColor(TeamId);
	UTexture2D* Pattern = SpiritsAssets::CivilizationPattern(static_cast<int32>(Civilization));
	if (ObeliskMID)
	{
		SpiritsAssets::SetColor(ObeliskMID, TeamColor * 0.5f + FLinearColor(0.03f, 0.03f, 0.06f));
		if (Pattern && !SpiritsAssets::SetTexture(ObeliskMID, Pattern, TEXT("PatternTex")))
		{
			UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=SoulShrine.PatternTex civilization=%d"), static_cast<int32>(Civilization));
		}
	}
	SpiritsAssets::SetColor(CrystalMID, TeamColor * 4.f + FLinearColor(0.3f, 0.3f, 0.3f));
	SpiritsAssets::SetColor(RingAMID, TeamColor * 2.2f);
	SpiritsAssets::SetColor(RingBMID, TeamColor * 1.6f);
	SpiritsAssets::SetColor(BaseGlowMID, TeamColor * 1.2f);
}

void ASoulShrine::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (GetNetMode() == NM_DedicatedServer)
	{
		return;
	}

	SpinTime += DeltaSeconds;
	const float HealthPct = GetHealthPercent();

	// Rings spin faster as the shrine gets closer to destruction (urgency).
	const float SpinSpeed = 40.f + (1.f - HealthPct) * 140.f;
	if (RingA) { RingA->AddLocalRotation(FRotator(0.f, SpinSpeed * DeltaSeconds, 0.f)); }
	if (RingB) { RingB->AddLocalRotation(FRotator(0.f, -SpinSpeed * 1.4f * DeltaSeconds, 0.f)); }

	// Floating crystal: bob + slow tumble
	if (Crystal)
	{
		Crystal->SetRelativeLocation(FVector(0.f, 0.f, 250.f + FMath::Sin(SpinTime * 1.4f) * 18.f));
		Crystal->AddLocalRotation(FRotator(0.f, 35.f * DeltaSeconds, 0.f));
	}

	// Light weakens with damage
	if (GlowLight)
	{
		GlowLight->SetIntensity(2500.f + 6500.f * HealthPct);
	}

	// Flash on damage
	if (LastFlashHealth < 0.f)
	{
		LastFlashHealth = Health;
	}
	else if (Health < LastFlashHealth - 0.1f)
	{
		LastFlashHealth = Health;
		AFXFlash::Spawn(GetWorld(), SpiritsAssets::Sphere(), GetActorLocation() + FVector(0, 0, 120.f),
		                FRotator::ZeroRotator, SpiritsTeams::GetTeamColor(TeamId) * 4.f,
		                FVector(1.6f), FVector(3.2f), 0.25f);
	}

	// Death: collapse with a ceremonial light column (the match's climax beat).
	if (IsDead())
	{
		if (!bFallFXDone)
		{
			bFallFXDone = true;
			const FLinearColor C = SpiritsTeams::GetTeamColor(TeamId) * 5.f;
			const FVector Base = GetActorLocation() - FVector(0, 0, 200.f);
			AFXFlash::Spawn(GetWorld(), SpiritsAssets::Cylinder(), Base, FRotator::ZeroRotator,
			                C, FVector(1.2f, 1.2f, 2.f), FVector(0.2f, 0.2f, 60.f), 1.6f, 250.f);
			AFXFlash::Spawn(GetWorld(), SpiritsAssets::CircularGlow(), Base, FRotator::ZeroRotator,
			                C, FVector(1.f), FVector(14.f), 1.2f);
			AFXFlash::Spawn(GetWorld(), SpiritsAssets::Sphere(), GetActorLocation() + FVector(0, 0, 100.f),
			                FRotator::ZeroRotator, FLinearColor(4.f, 3.6f, 2.4f), FVector(1.f), FVector(8.f), 0.8f);
		}
		if (Obelisk) { Obelisk->AddLocalRotation(FRotator(0.f, 0.f, 25.f * DeltaSeconds)); }
		if (Crystal) { Crystal->SetVisibility(false); }
	}
}
