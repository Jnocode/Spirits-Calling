#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ArenaBuilder.generated.h"

class UStaticMeshComponent;
class UTexture2D;

/**
 * A parameterized battlefield "look". Two presets are selected by the
 * replicated GameState::MapIndex (0 = Void night arena, 1 = Sands day arena).
 * Adding a new map is just adding another preset in AArenaBuilder::MakeStyle.
 *
 * IMPORTANT: floor size must stay large enough to contain the team bases at
 * +/- ASpiritsGameMode::FallbackBaseDistance (3400), so shrines land on ground.
 */
struct FArenaStyle
{
	// Geometry
	float FloorHalfX = 4500.f;
	float FloorHalfY = 2750.f;
	float FloorTopZ = 12.f;
	FVector PillarScale = FVector(3.2f, 3.2f, 6.5f);
	TArray<FVector2D> Pillars;

	// Accents (wall trim / center line / pillar caps)
	FLinearColor GlowColor = FLinearColor(0.15f, 0.9f, 1.f);

	// Sky / lighting
	bool bNightDome = true;                                  // dark void dome + moon (false = open day sky)
	FLinearColor DomeColor = FLinearColor(0.015f, 0.02f, 0.06f);
	FRotator SunRotation = FRotator(-42.f, 35.f, 0.f);
	FLinearColor SunColor = FLinearColor(0.85f, 0.9f, 1.f);
	float SunIntensity = 6.f;
	FLinearColor SkyColor = FLinearColor(0.55f, 0.65f, 0.9f);
	float SkyIntensity = 1.1f;
	FLinearColor FogColor = FLinearColor(0.06f, 0.1f, 0.22f);
	float FogDensity = 0.007f;
	float ExposureBias = 0.9f;
};

/**
 * Procedurally builds the battlefield: floor, walls, pillars, glow accents,
 * sky, moon, lighting, fog and post processing — all driven by an FArenaStyle.
 *
 * Spawned locally on every instance (server and each client) by
 * ASpiritsGameState. The active style is chosen from the *replicated*
 * GameState::MapIndex so every instance builds identical collision geometry.
 */
UCLASS()
class SPIRITSCALLING_API AArenaBuilder : public AActor
{
	GENERATED_BODY()

public:
	AArenaBuilder();

	virtual void Tick(float DeltaSeconds) override;

	/** Build one of the preset styles (0 = Void, 1 = Sands; clamped). */
	static FArenaStyle MakeStyle(int32 MapIndex);

	/** Re-resolve generated geometry after the replicated GameState snapshot changes. */
	void ApplyMapIndex(int32 MapIndex);
	bool IsCollisionReady() const { return bCollisionReady; }
	int32 GetResolvedMapIndex() const { return ResolvedMapIndex; }
	const FString& GetGroundHook() const { return GroundHook; }
	const FString& GetSkyHook() const { return SkyHook; }

	// Convenience accessors (were compile-time constants before styles existed).
	float FloorHalfX() const { return Style.FloorHalfX; }
	float FloorHalfY() const { return Style.FloorHalfY; }
	float FloorTopZ() const { return Style.FloorTopZ; }

protected:
	/** Active style, resolved from GameState::MapIndex in BeginPlay. */
	FArenaStyle Style;

	virtual void BeginPlay() override;

	void BuildGeometry();
	void BuildLighting();
	void ClearGeneratedScene();
	bool ApplyTextureHook(UStaticMeshComponent* Component, UTexture2D* Texture, const FString& Hook);

	int32 ResolvedMapIndex = 0;
	FString GroundHook;
	FString SkyHook;
	bool bCollisionReady = false;

	UStaticMeshComponent* AddMesh(UStaticMesh* Mesh, class UMaterialInterface* Mat,
	                              const FVector& Location, const FRotator& Rotation, const FVector& Scale,
	                              const FLinearColor* GlowColor = nullptr, bool bCollision = true);

	UPROPERTY()
	TArray<TObjectPtr<UStaticMeshComponent>> SpinningRings;

	// Mood / color-script actors (Jenova Chen pass: emotion curve drives the palette)
	UPROPERTY() TObjectPtr<class ADirectionalLight> SunActor;
	UPROPERTY() TObjectPtr<class AExponentialHeightFog> FogActor;
	UPROPERTY() TObjectPtr<class APostProcessVolume> PPActor;

	void UpdateMood(float DeltaSeconds);
	/** Documented ambient fallback: S_Ambient is retriggered every ~11.2s (no loop
	 *  flag on the asset). Extracted so automation can observe the retrigger live. */
	void AdvanceAmbientBed(float DeltaSeconds);
	float ShrineScanAccum = 0.f;
	float LocalShrinePct = 1.f;
	float MoodTime = 0.f;
	float AmbientAccum = 0.f;

#if WITH_DEV_AUTOMATION_TESTS
public:
	/** Live observation seam: how many times the ambient bed retriggered S_Ambient. */
	int32 GetAmbientRetriggerCountForAutomation() const { return AmbientRetriggerCountForAutomation; }
	/** Drives the real ambient fallback so automation can observe it live. */
	void AdvanceAmbientBedForAutomation(float DeltaSeconds) { AdvanceAmbientBed(DeltaSeconds); }
private:
	int32 AmbientRetriggerCountForAutomation = 0;
#endif
};
