#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "UnitAIController.generated.h"

class AUnitBase;

/**
 * Combat AI (server only, no NavMesh requirement):
 *  - weighted target selection (nearest enemy, prefer finishing low-HP targets,
 *    march on the enemy shrine when no defenders are near);
 *  - obstacle avoidance (steer around pillars/walls via forward sphere probes);
 *  - separation (push off nearby allies so crowds don't stack into one point).
 */
UCLASS()
class SPIRITSCALLING_API AUnitAIController : public AAIController
{
	GENERATED_BODY()

public:
	AUnitAIController();

	virtual void Tick(float DeltaSeconds) override;

protected:
	void AcquireTarget();

	/** Sum of repulsion from nearby same-team units (2D, unnormalized ~ crowding). */
	FVector ComputeSeparation(const AUnitBase* Self) const;

	/** Return DesiredDir, or a steered-around direction if a static obstacle blocks it. */
	FVector AvoidObstacles(const AUnitBase* Self, const FVector& DesiredDir) const;

	UPROPERTY()
	TWeakObjectPtr<AUnitBase> Target;

	float NextTargetSearchTime = 0.f;
	float NextAvoidTime = 0.f;
	FVector CachedSteerDir = FVector::ZeroVector;

	// --- Tunables ---
	/** Beyond this range the unit ignores enemy units and marches on the objective. */
	UPROPERTY(EditDefaultsOnly, Category = "AI") float SightRadius = 3000.f;
	UPROPERTY(EditDefaultsOnly, Category = "AI") float SeparationRadius = 170.f;
	UPROPERTY(EditDefaultsOnly, Category = "AI") float SeparationWeight = 0.7f;
	UPROPERTY(EditDefaultsOnly, Category = "AI") float AvoidProbeDist = 320.f;
	/** Targets below this HP fraction are prioritized (finish the kill). */
	UPROPERTY(EditDefaultsOnly, Category = "AI") float LowHpTargetThreshold = 0.35f;
};
