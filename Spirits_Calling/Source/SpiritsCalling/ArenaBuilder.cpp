#include "ArenaBuilder.h"

#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SoulShrine.h"
#include "SpiritsAssets.h"
#include "SpiritsAudio.h"
#include "SpiritsGameState.h"
#include "SpiritsPlayerState.h"
#include "SpiritsRules.h"
#include "SpiritsTypes.h"

FArenaStyle AArenaBuilder::MakeStyle(int32 MapIndex)
{
	FArenaStyle S;
	const int32 NormalizedMapIndex = SpiritsRules::NormalizeMapIndex(MapIndex);

	if (NormalizedMapIndex == 1)
	{
		// --- Sands: open desert arena, wider floor, denser pillar grid, warm day ---
		S.FloorHalfX = 5200.f;   // still contains the +/-3400 team bases
		S.FloorHalfY = 3100.f;
		S.FloorTopZ = 12.f;
		S.PillarScale = FVector(2.8f, 2.8f, 5.5f);
		S.Pillars = {
			{ 1200,  850 }, { 1200, -850 }, { -1200,  850 }, { -1200, -850 },
			{ 2400, 1500 }, { 2400, -1500 }, { -2400, 1500 }, { -2400, -1500 },
			{ 1800,    0 }, { -1800,    0 }, { 0, 1600 }, { 0, -1600 },
			{ 3200, 2300 }, { 3200, -2300 }, { -3200, 2300 }, { -3200, -2300 },
		};
		S.GlowColor = FLinearColor(1.f, 0.75f, 0.25f);        // gold accents
		S.bNightDome = false;                                  // open bright sky
		S.SunRotation = FRotator(-55.f, 20.f, 0.f);
		S.SunColor = FLinearColor(1.f, 0.93f, 0.78f);          // warm daylight
		S.SunIntensity = 9.f;
		S.SkyColor = FLinearColor(0.85f, 0.82f, 0.7f);
		S.SkyIntensity = 2.2f;
		S.FogColor = FLinearColor(0.22f, 0.16f, 0.09f);        // warm haze
		S.FogDensity = 0.005f;
		S.ExposureBias = 0.7f;
		return S;
	}

	// --- Void (default, index 0): night arena with a dark dome + moon ---
	S.FloorHalfX = 4500.f;
	S.FloorHalfY = 2750.f;
	S.FloorTopZ = 12.f;
	S.PillarScale = FVector(3.2f, 3.2f, 6.5f);
	S.Pillars = {
		{ 1300,  950 }, { 1300, -950 }, { -1300,  950 }, { -1300, -950 },
		{ 2500, 1700 }, { 2500, -1700 }, { -2500, 1700 }, { -2500, -1700 },
		{ 0, 1900 }, { 0, -1900 },
	};
	S.GlowColor = FLinearColor(0.15f, 0.9f, 1.f);              // cyan accents
	S.bNightDome = true;
	S.DomeColor = FLinearColor(0.015f, 0.02f, 0.06f);
	S.SunRotation = FRotator(-42.f, 35.f, 0.f);
	S.SunColor = FLinearColor(0.85f, 0.9f, 1.f);
	S.SunIntensity = 6.f;
	S.SkyColor = FLinearColor(0.55f, 0.65f, 0.9f);
	S.SkyIntensity = 1.1f;
	S.FogColor = FLinearColor(0.06f, 0.1f, 0.22f);
	S.FogDensity = 0.007f;
	S.ExposureBias = 0.9f;
	return S;
}

void AArenaBuilder::ApplyMapIndex(int32 MapIndex)
{
	const SpiritsRules::FMapStyleHooks MapHooks = SpiritsRules::ResolveMapStyle(MapIndex);
	const int32 NormalizedIndex = MapHooks.MapIndex;
	if (bCollisionReady && ResolvedMapIndex == NormalizedIndex)
	{
		return;
	}

	ResolvedMapIndex = NormalizedIndex;
	GroundHook = MapHooks.GroundHook;
	SkyHook = MapHooks.SkyHook;
	bCollisionReady = false;
	ClearGeneratedScene();
	Style = MakeStyle(ResolvedMapIndex);
	BuildGeometry();
	if (GetNetMode() != NM_DedicatedServer)
	{
		BuildLighting();
	}
}

void AArenaBuilder::ClearGeneratedScene()
{
	SpinningRings.Reset();

	TArray<UActorComponent*> Components;
	GetComponents(Components);
	for (UActorComponent* Component : Components)
	{
		if (Component && Component != GetRootComponent())
		{
			Component->DestroyComponent();
		}
	}

	if (SunActor)
	{
		SunActor->Destroy();
		SunActor = nullptr;
	}
	if (FogActor)
	{
		FogActor->Destroy();
		FogActor = nullptr;
	}
	if (PPActor)
	{
		PPActor->Destroy();
		PPActor = nullptr;
	}
}

AArenaBuilder::AArenaBuilder()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

void AArenaBuilder::BeginPlay()
{
	Super::BeginPlay();

	// Resolve the battlefield style from the replicated GameState snapshot.
	int32 MapIndex = GSpiritsMapIndex;
	if (const ASpiritsGameState* GS = GetWorld() ? GetWorld()->GetGameState<ASpiritsGameState>() : nullptr)
	{
		MapIndex = GS->MapIndex;
	}

	// Take full ownership of the scene: remove the old prototype floor, orcs
	// and stale (static, unbuilt) lighting on every instance, then rebuild.
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* Actor = *It;
		const FString Name = Actor->GetName();
		const bool bLegacyProp = Name.Contains(TEXT("BP_Orc")) || Name.Equals(TEXT("Ground"));
		const bool bLegacyLight = Actor->IsA<ADirectionalLight>() || Actor->IsA<ASkyLight>() ||
		                          Actor->IsA<AExponentialHeightFog>() || Actor->IsA<APostProcessVolume>();
		if (bLegacyProp || bLegacyLight)
		{
			Actor->Destroy();
		}
	}

	ApplyMapIndex(MapIndex);
}

UStaticMeshComponent* AArenaBuilder::AddMesh(UStaticMesh* Mesh, UMaterialInterface* Mat,
                                             const FVector& Location, const FRotator& Rotation, const FVector& Scale,
                                             const FLinearColor* GlowColor, bool bCollision)
{
	if (!Mesh)
	{
		return nullptr;
	}

	UStaticMeshComponent* Comp = NewObject<UStaticMeshComponent>(this);
	Comp->SetStaticMesh(Mesh);
	if (Mat)
	{
		Comp->SetMaterial(0, Mat);
	}
	Comp->SetupAttachment(GetRootComponent());
	Comp->SetRelativeLocation(Location);
	Comp->SetRelativeRotation(Rotation);
	Comp->SetRelativeScale3D(Scale);
	Comp->SetCollisionEnabled(bCollision ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	Comp->SetCastShadow(false);
	Comp->RegisterComponent();

	if (GlowColor)
	{
		UMaterialInstanceDynamic* MID = Comp->CreateAndSetMaterialInstanceDynamic(0);
		SpiritsAssets::SetColor(MID, *GlowColor);
	}
	return Comp;
}

bool AArenaBuilder::ApplyTextureHook(UStaticMeshComponent* Component, UTexture2D* Texture, const FString& Hook)
{
	if (!Component || !Texture)
	{
		UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=%s component=%s"), *Hook, Component ? *Component->GetName() : TEXT("<null>"));
		return false;
	}

	UMaterialInstanceDynamic* MID = Component->CreateAndSetMaterialInstanceDynamic(0);
	const bool bApplied = SpiritsAssets::SetTexture(MID, Texture, TEXT("Texture"));
	if (!bApplied)
	{
		UE_LOG(LogTemp, Error, TEXT("[Asset.MissingHook] hook=%s component=%s parameter=Texture"), *Hook, *Component->GetName());
	}
	return bApplied;
}

void AArenaBuilder::BuildGeometry()
{
	UStaticMesh* Cube = SpiritsAssets::Cube();
	UStaticMesh* Chamfer = SpiritsAssets::ChamferCube();
	UStaticMesh* Sphere = SpiritsAssets::Sphere();
	UMaterialInterface* GridDark = SpiritsAssets::GridMaterialDark();
	UMaterialInterface* ArenaSurface = SpiritsAssets::ArenaSurfaceMaterial();
	UMaterialInterface* GridGray = SpiritsAssets::GridMaterialGray();
	UMaterialInterface* Glow = SpiritsAssets::GlowMaterial();

	const float FloorHX = Style.FloorHalfX;
	const float FloorHY = Style.FloorHalfY;
	const float FloorZ = Style.FloorTopZ;
	const FLinearColor Accent = Style.GlowColor;

	// --- Floor (top at FloorTopZ) ---
	UStaticMeshComponent* Floor = AddMesh(Cube, ArenaSurface ? ArenaSurface : GridDark, FVector(0, 0, FloorZ - 12.f), FRotator::ZeroRotator,
	                                      FVector(FloorHX * 2.f / 100.f, FloorHY * 2.f / 100.f, 0.24f));
	ApplyTextureHook(Floor, SpiritsAssets::ArenaGroundTexture(ResolvedMapIndex), GroundHook);

	// --- Perimeter walls with glow trim ---
	const float WallH = 260.f;
	const float WallT = 60.f;
	struct FWall { FVector Loc; FVector Scale; };
	const FWall Walls[] = {
		{ FVector(0,  FloorHY, WallH * 0.5f), FVector(FloorHX * 2.f / 100.f, WallT / 100.f, WallH / 100.f) },
		{ FVector(0, -FloorHY, WallH * 0.5f), FVector(FloorHX * 2.f / 100.f, WallT / 100.f, WallH / 100.f) },
		{ FVector( FloorHX, 0, WallH * 0.5f), FVector(WallT / 100.f, FloorHY * 2.f / 100.f, WallH / 100.f) },
		{ FVector(-FloorHX, 0, WallH * 0.5f), FVector(WallT / 100.f, FloorHY * 2.f / 100.f, WallH / 100.f) },
	};
	for (const FWall& W : Walls)
	{
		AddMesh(Cube, GridGray, W.Loc, FRotator::ZeroRotator, W.Scale);
		// Glow trim on top of each wall
		FVector TrimScale = W.Scale;
		TrimScale.Z = 0.06f;
		AddMesh(Cube, Glow, W.Loc + FVector(0, 0, WallH * 0.5f + 4.f), FRotator::ZeroRotator, TrimScale, &Accent, false);
	}

	// --- Center line + team base circles ---
	const FLinearColor MidGlow = Accent * 0.6f;
	AddMesh(Cube, Glow, FVector(0, 0, FloorZ + 2.f), FRotator::ZeroRotator,
	        FVector(0.5f, FloorHY * 2.f / 100.f, 0.03f), &MidGlow, false);

	UStaticMesh* CircleGlow = SpiritsAssets::CircularGlow();
	const FLinearColor BlueGlow = SpiritsTeams::GetTeamColor(SpiritsTeams::TeamA) * 1.5f;
	const FLinearColor RedGlow = SpiritsTeams::GetTeamColor(SpiritsTeams::TeamB) * 1.5f;
	AddMesh(CircleGlow, Glow, FVector(-3400, 0, FloorZ + 3.f), FRotator::ZeroRotator, FVector(9.f), &BlueGlow, false);
	AddMesh(CircleGlow, Glow, FVector( 3400, 0, FloorZ + 3.f), FRotator::ZeroRotator, FVector(9.f), &RedGlow, false);

	// --- Symmetric pillars (cover, breaks sightlines) ---
	const FVector PillarScale = Style.PillarScale;
	const float PillarCapZ = FloorZ + PillarScale.Z * 100.f + 8.f;
	for (const FVector2D& P : Style.Pillars)
	{
		AddMesh(Chamfer, GridGray, FVector(P.X, P.Y, FloorZ), FRotator::ZeroRotator, PillarScale);
		// Small glow cap
		AddMesh(Cube, Glow, FVector(P.X, P.Y, PillarCapZ), FRotator::ZeroRotator,
		        FVector(1.1f, 1.1f, 0.06f), &MidGlow, false);
	}

	// --- Canonical ground/sky material hooks ---
	// Both map variants expose a sky hook. Void keeps its moon/wisp accents;
	// Sands uses the same textured dome without the night-only accents.
	if (GetNetMode() != NM_DedicatedServer && Sphere)
	{
		UStaticMeshComponent* Dome = AddMesh(Sphere, ArenaSurface ? ArenaSurface : Glow, FVector(0, 0, 0), FRotator::ZeroRotator,
		                                     FVector(-900.f), &Style.DomeColor, false);
		ApplyTextureHook(Dome, SpiritsAssets::ArenaSkyTexture(ResolvedMapIndex), SkyHook);
		if (Dome)
		{
			Dome->SetCastShadow(false);
			Dome->bVisibleInRayTracing = false;
		}

		if (Style.bNightDome)
		{
			const FLinearColor MoonGlow(2.2f, 2.4f, 2.8f);
			AddMesh(Sphere, Glow, FVector(-20000, 14000, 16000), FRotator::ZeroRotator, FVector(18.f), &MoonGlow, false);

			// Floating spirit wisps around the arena edge (slowly spinning rings)
			UStaticMesh* Band = SpiritsAssets::CircularBand();
			const FVector2D WispSpots[] = { { 3400, 0 }, { -3400, 0 } };
			for (int32 i = 0; i < 2; ++i)
			{
				const FLinearColor& C = (i == 0) ? RedGlow : BlueGlow;
				UStaticMeshComponent* Ring = AddMesh(Band, Glow, FVector(WispSpots[i].X, WispSpots[i].Y, 420.f),
				                                     FRotator::ZeroRotator, FVector(4.5f), &C, false);
				if (Ring)
				{
					SpinningRings.Add(Ring);
				}
			}
		}
	}

	// Collision is authoritative for shrine grounding and must be ready before
	// the GameMode transitions the match into InProgress.
	bCollisionReady = Floor != nullptr;
}

void AArenaBuilder::BuildLighting()
{
	UWorld* World = GetWorld();

	// Key light (moonlight for Void, warm sun for Sands): reads silhouettes clearly.
	ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>(FVector::ZeroVector, Style.SunRotation);
	SunActor = Sun;
	if (Sun && Sun->GetLightComponent())
	{
		Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);
		Sun->GetLightComponent()->SetIntensity(Style.SunIntensity);
		Sun->GetLightComponent()->SetLightColor(Style.SunColor);
	}

	// Ambient fill so shadow sides never go pitch black.
	ASkyLight* Sky = World->SpawnActor<ASkyLight>(FVector::ZeroVector, FRotator::ZeroRotator);
	if (Sky && Sky->GetLightComponent())
	{
		Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);
		Sky->GetLightComponent()->SetIntensity(Style.SkyIntensity);
		Sky->GetLightComponent()->SetLightColor(Style.SkyColor);
		Sky->GetLightComponent()->RecaptureSky();
	}

	// Distance fog: depth cue, not murk (color/density per style).
	AExponentialHeightFog* Fog = World->SpawnActor<AExponentialHeightFog>(FVector(0, 0, -100.f), FRotator::ZeroRotator);
	FogActor = Fog;
	if (Fog && Fog->GetComponent())
	{
		Fog->GetComponent()->SetMobility(EComponentMobility::Movable);
		Fog->GetComponent()->SetFogDensity(Style.FogDensity);
		Fog->GetComponent()->SetFogInscatteringColor(Style.FogColor);
		Fog->GetComponent()->SetFogHeightFalloff(0.4f);
	}

	// Post processing: bloom for all the glow, gentle vignette, style exposure.
	APostProcessVolume* PP = World->SpawnActor<APostProcessVolume>(FVector::ZeroVector, FRotator::ZeroRotator);
	PPActor = PP;
	if (PP)
	{
		PP->bUnbound = true;
		PP->Settings.bOverride_BloomIntensity = true;
		PP->Settings.BloomIntensity = 1.5f;
		PP->Settings.bOverride_VignetteIntensity = true;
		PP->Settings.VignetteIntensity = 0.4f;
		PP->Settings.bOverride_AutoExposureBias = true;
		PP->Settings.AutoExposureBias = Style.ExposureBias;
	}
}

void AArenaBuilder::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	for (UStaticMeshComponent* Ring : SpinningRings)
	{
		if (Ring)
		{
			Ring->AddLocalRotation(FRotator(0.f, 25.f * DeltaSeconds, 0.f));
		}
	}

	if (GetNetMode() != NM_DedicatedServer)
	{
		UpdateMood(DeltaSeconds);
		AdvanceAmbientBed(DeltaSeconds);
	}
}

void AArenaBuilder::AdvanceAmbientBed(float DeltaSeconds)
{
	// Ambient wind bed (retriggered, no loop flag needed on the asset).
	AmbientAccum -= DeltaSeconds;
	if (AmbientAccum <= 0.f)
	{
		SpiritsAudio::Play2D(this, TEXT("S_Ambient"), 0.35f);
		AmbientAccum = 11.2f;
#if WITH_DEV_AUTOMATION_TESTS
		++AmbientRetriggerCountForAutomation;
#endif
	}
}

void AArenaBuilder::UpdateMood(float DeltaSeconds)
{
	// Jenova Chen pass: the palette follows the emotion curve —
	// calm blue opening → tenser violet as waves escalate → red pulse in crisis
	// → warm gold on victory / desaturated void on defeat.
	if (!FogActor || !FogActor->GetComponent())
	{
		return;
	}

	MoodTime += DeltaSeconds;

	const ASpiritsGameState* GS = GetWorld()->GetGameState<ASpiritsGameState>();
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;

	// Cache our shrine's health once a second.
	ShrineScanAccum += DeltaSeconds;
	if (ShrineScanAccum > 1.f && PS)
	{
		ShrineScanAccum = 0.f;
		for (TActorIterator<ASoulShrine> It(GetWorld()); It; ++It)
		{
			if (It->TeamId == PS->TeamId)
			{
				LocalShrinePct = It->GetHealthPercent();
				break;
			}
		}
	}

	// Calm baseline follows the active map style; the beats below override it.
	FLinearColor TargetFog = Style.FogColor;
	float TargetDensity = Style.FogDensity;

	if (GS && GS->Phase == ESpiritsMatchPhase::Ended && PS)
	{
		if (GS->WinningTeam == PS->TeamId)
		{
			TargetFog = FLinearColor(0.2f, 0.15f, 0.06f); // warm gold
			TargetDensity = 0.006f;
		}
		else
		{
			TargetFog = FLinearColor(0.015f, 0.015f, 0.025f); // drained void
			TargetDensity = 0.011f;
		}
	}
	else if (GS)
	{
		// Escalating tension: shift the style fog toward a tenser tint as waves grow.
		const float Danger = FMath::Clamp(GS->CurrentWave / 8.f, 0.f, 1.f);
		const FLinearColor Tense = Style.FogColor * 0.7f + FLinearColor(0.07f, 0.f, 0.09f);
		TargetFog = FMath::Lerp(Style.FogColor, Tense, Danger);
		TargetDensity = FMath::Lerp(Style.FogDensity, Style.FogDensity * 1.35f, Danger);

		// Shrine crisis: slow red heartbeat in the air itself.
		if (LocalShrinePct < 0.35f)
		{
			const float Pulse = (FMath::Sin(MoodTime * 2.4f) * 0.5f + 0.5f) * 0.05f;
			TargetFog += FLinearColor(Pulse, 0.f, 0.f);
		}
	}

	UExponentialHeightFogComponent* FogComp = FogActor->GetComponent();
	const FLinearColor Current = FogComp->FogInscatteringLuminance;
	FogComp->SetFogInscatteringColor(FMath::Lerp(Current, TargetFog, FMath::Min(1.f, DeltaSeconds * 1.5f)));
	FogComp->SetFogDensity(FMath::Lerp(FogComp->FogDensity, TargetDensity, FMath::Min(1.f, DeltaSeconds * 1.5f)));
}
