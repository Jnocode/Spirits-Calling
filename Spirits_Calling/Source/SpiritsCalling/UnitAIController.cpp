#include "UnitAIController.h"

#include "Engine/World.h"
#include "SpiritsGameMode.h"
#include "SpiritsGameState.h"
#include "UnitBase.h"

AUnitAIController::AUnitAIController()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AUnitAIController::AcquireTarget()
{
	Target = nullptr;

	AUnitBase* Self = Cast<AUnitBase>(GetPawn());
	ASpiritsGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASpiritsGameMode>() : nullptr;
	if (!Self || !GM)
	{
		return;
	}

	const FVector SelfLoc = Self->GetActorLocation();

	// Track the best living enemy unit (weighted) and the nearest enemy structure
	// separately, so we can fall back to sieging the shrine when no defenders exist.
	AUnitBase* BestUnit = nullptr;
	float BestUnitScore = TNumericLimits<float>::Max();
	float BestUnitDistSq = TNumericLimits<float>::Max();

	AUnitBase* NearestStructure = nullptr;
	float NearestStructDistSq = TNumericLimits<float>::Max();

	for (const TWeakObjectPtr<AUnitBase>& Candidate : GM->GetAllUnits())
	{
		AUnitBase* Unit = Candidate.Get();
		if (!Unit || Unit == Self || Unit->IsDead() || Unit->TeamId == Self->TeamId)
		{
			continue;
		}

		const float DistSq = FVector::DistSquared(SelfLoc, Unit->GetActorLocation());

		if (Unit->bIsStructure)
		{
			if (DistSq < NearestStructDistSq)
			{
				NearestStructDistSq = DistSq;
				NearestStructure = Unit;
			}
			continue;
		}

		// Weighted score: distance, biased down for low-HP targets (finish the kill).
		float Score = DistSq;
		if (Unit->GetHealthPercent() < LowHpTargetThreshold)
		{
			Score *= 0.6f;
		}
		if (Score < BestUnitScore)
		{
			BestUnitScore = Score;
			BestUnitDistSq = DistSq;
			BestUnit = Unit;
		}
	}

	// Engage a nearby enemy unit; otherwise march on the enemy shrine; if there is
	// neither in sight but a distant unit exists, still advance toward it.
	const float SightSq = SightRadius * SightRadius;
	if (BestUnit && BestUnitDistSq <= SightSq)
	{
		Target = BestUnit;
	}
	else if (NearestStructure)
	{
		Target = NearestStructure;
	}
	else
	{
		Target = BestUnit;
	}
}

FVector AUnitAIController::ComputeSeparation(const AUnitBase* Self) const
{
	FVector Push = FVector::ZeroVector;
	ASpiritsGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASpiritsGameMode>() : nullptr;
	if (!Self || !GM)
	{
		return Push;
	}

	const FVector SelfLoc = Self->GetActorLocation();
	for (const TWeakObjectPtr<AUnitBase>& Candidate : GM->GetAllUnits())
	{
		const AUnitBase* Other = Candidate.Get();
		if (!Other || Other == Self || Other->IsDead() || Other->bIsStructure || Other->TeamId != Self->TeamId)
		{
			continue;
		}
		FVector To = SelfLoc - Other->GetActorLocation();
		const float Dist = To.Size2D();
		if (Dist > 1.f && Dist < SeparationRadius)
		{
			// Linear falloff: closer allies push harder.
			Push += To.GetSafeNormal2D() * (1.f - Dist / SeparationRadius);
		}
	}
	return Push;
}

FVector AUnitAIController::AvoidObstacles(const AUnitBase* Self, const FVector& DesiredDir) const
{
	UWorld* World = GetWorld();
	if (!World || !Self || DesiredDir.IsNearlyZero())
	{
		return DesiredDir;
	}

	const float Radius = FMath::Max(Self->GetSimpleCollisionRadius(), 34.f);
	const FVector Start = Self->GetActorLocation();
	FCollisionQueryParams Params(FName(TEXT("SpiritsAIAvoid")), false, Self);
	const FCollisionShape Probe = FCollisionShape::MakeSphere(Radius);

	auto IsClear = [&](const FVector& Dir) -> bool
	{
		const FVector End = Start + Dir * AvoidProbeDist;
		FHitResult Hit;
		// Only static level geometry (pillars/walls) blocks steering; units are handled by separation.
		return !World->SweepSingleByChannel(Hit, Start, End, FQuat::Identity, ECC_WorldStatic, Probe, Params);
	};

	if (IsClear(DesiredDir))
	{
		return DesiredDir;
	}

	// Blocked ahead: try progressively wider left/right detours; take the first clear one.
	for (const float Angle : { 35.f, -35.f, 65.f, -65.f, 100.f, -100.f })
	{
		const FVector Steered = DesiredDir.RotateAngleAxis(Angle, FVector::UpVector);
		if (IsClear(Steered))
		{
			return Steered;
		}
	}
	return DesiredDir; // boxed in — keep pushing, physics resolves it
}

void AUnitAIController::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!HasAuthority())
	{
		return;
	}

	AUnitBase* Self = Cast<AUnitBase>(GetPawn());
	if (!Self || Self->IsDead() || Self->bIsStructure)
	{
		return;
	}

	ASpiritsGameState* GS = GetWorld()->GetGameState<ASpiritsGameState>();
	if (GS && GS->Phase != ESpiritsMatchPhase::InProgress)
	{
		return;
	}

	const float Now = GetWorld()->GetTimeSeconds();
	if (Now >= NextTargetSearchTime || !Target.IsValid() || Target->IsDead())
	{
		AcquireTarget();
		NextTargetSearchTime = Now + 0.5f;
	}

	AUnitBase* TargetUnit = Target.Get();
	if (!TargetUnit)
	{
		return;
	}

	const FVector ToTarget = TargetUnit->GetActorLocation() - Self->GetActorLocation();
	const float Dist2D = ToTarget.Size2D();

	// Account for large targets (e.g. shrines) by their collision extent.
	const float TargetRadius = TargetUnit->GetSimpleCollisionRadius();
	const float EffectiveRange = Self->Stats.AttackRange + TargetRadius;

	if (Dist2D > EffectiveRange * 0.9f)
	{
		const FVector ToTargetDir = ToTarget.GetSafeNormal2D();

		// Obstacle avoidance is the expensive part (sphere traces): recompute the
		// steer direction a few times a second and reuse it in between.
		if (Now >= NextAvoidTime || CachedSteerDir.IsNearlyZero())
		{
			CachedSteerDir = AvoidObstacles(Self, ToTargetDir);
			NextAvoidTime = Now + 0.12f;
		}

		// Blend steering with allied separation so crowds spread out instead of stacking.
		FVector MoveDir = CachedSteerDir + ComputeSeparation(Self) * SeparationWeight;
		MoveDir = MoveDir.GetSafeNormal2D();
		if (MoveDir.IsNearlyZero())
		{
			MoveDir = ToTargetDir;
		}
		Self->AddMovementInput(MoveDir, 1.f);
	}
	else
	{
		// In range: face the target, then swing.
		const FRotator FaceRot(0.f, ToTarget.Rotation().Yaw, 0.f);
		Self->SetActorRotation(FMath::RInterpTo(Self->GetActorRotation(), FaceRot, DeltaSeconds, 10.f));
		Self->TryAttack();
	}
}
