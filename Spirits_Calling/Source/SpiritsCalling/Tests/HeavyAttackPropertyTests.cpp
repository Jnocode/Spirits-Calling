#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

namespace
{
	constexpr int32 Property4Seed = 0x50340001;
	constexpr int32 Property4Iterations = 256;
	constexpr float TimerToleranceSeconds = 0.001f;

	FString DescribeCase(
		int32 Iteration,
		float BaseDamage,
		float BaseKnockback,
		float TargetDistance,
		bool bCooldownReady,
		bool bInterrupted,
		int32 CancellationBucket,
		float CancellationTime)
	{
		return FString::Printf(
			TEXT("seed=%d iteration=%d baseDamage=%.6f baseKnockback=%.6f targetDistance=%.6f "
			     "cooldownReady=%s interrupted=%s cancellationBucket=%d cancellationTime=%.6f"),
			Property4Seed,
			Iteration,
			BaseDamage,
			BaseKnockback,
			TargetDistance,
			bCooldownReady ? TEXT("true") : TEXT("false"),
			bInterrupted ? TEXT("true") : TEXT("false"),
			CancellationBucket,
			CancellationTime);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsHeavyAttackProperty4AutomationTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 4: Heavy attack wind-up, hit-stop, multipliers, cancellation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsHeavyAttackProperty4AutomationTest::RunTest(const FString& Parameters)
{
	FRandomStream Random(Property4Seed);
	AddInfo(FString::Printf(
		TEXT("Feature: spirits-calling-requirements, Property 4; seed=%d; iterations=%d"),
		Property4Seed,
		Property4Iterations));

	for (int32 Iteration = 0; Iteration < Property4Iterations; ++Iteration)
	{
		// Generated target context is deliberately valid. Target filtering and range
		// queries belong to UnitBase; this pure seam verifies the resolved attack.
		const float BaseDamage = Random.FRandRange(0.01f, 1000.f);
		const float BaseKnockback = Random.FRandRange(0.01f, 2000.f);
		const float TargetDistance = Random.FRandRange(1.f, 1000.f);
		const bool bCooldownReady = Random.RandBool();
		const bool bInterrupted = Random.RandBool();
		const bool bCanAttack = bCooldownReady && !bInterrupted;
		const int32 CancellationBucket = Random.RandRange(0, 2);

		float CancellationTime = 0.f;
		switch (CancellationBucket)
		{
		case 0:
			// Strictly before the resolve boundary.
			CancellationTime = Random.FRandRange(0.f, SpiritsRules::HeavyAttackWindupSeconds - 0.001f);
			break;
		case 1:
			// Exactly at resolve: this is a hit, not a cancellation.
			CancellationTime = SpiritsRules::HeavyAttackWindupSeconds;
			break;
		default:
			// After resolve: the already accepted attack has reached its hit time.
			CancellationTime = Random.FRandRange(
				SpiritsRules::HeavyAttackWindupSeconds + 0.001f,
				2.f);
			break;
		}

		const SpiritsRules::FHeavyAttackResult Result = SpiritsRules::EvaluateHeavyAttack(
			BaseDamage,
			BaseKnockback,
			bCanAttack,
			CancellationTime);

		const bool bExpectedAccepted = bCanAttack;
		const bool bExpectedHit = bCanAttack && CancellationBucket != 0;
		const float ExpectedResolveTime =
			bExpectedAccepted && CancellationBucket == 0
				? CancellationTime
				: (bExpectedAccepted ? SpiritsRules::HeavyAttackWindupSeconds : 0.f);
		const float ExpectedDamage = bExpectedHit
			? BaseDamage * SpiritsRules::HeavyAttackDamageMultiplier
			: 0.f;
		const float ExpectedKnockback = bExpectedHit
			? BaseKnockback * SpiritsRules::HeavyAttackKnockbackMultiplier
			: 0.f;
		const float ExpectedHitStop = bExpectedHit
			? SpiritsRules::HeavyAttackHitStopSeconds
			: 0.f;

		const bool bMatchesProperty =
			Result.bAccepted == bExpectedAccepted &&
			Result.bHit == bExpectedHit &&
			FMath::IsNearlyEqual(Result.ResolveTime, ExpectedResolveTime, TimerToleranceSeconds) &&
			FMath::IsNearlyEqual(Result.Damage, ExpectedDamage, TimerToleranceSeconds) &&
			FMath::IsNearlyEqual(Result.KnockbackMagnitude, ExpectedKnockback, TimerToleranceSeconds) &&
			FMath::IsNearlyEqual(Result.HitStopSeconds, ExpectedHitStop, TimerToleranceSeconds) &&
			TargetDistance > 0.f;

		TestTrue(DescribeCase(
			Iteration,
			BaseDamage,
			BaseKnockback,
			TargetDistance,
			bCooldownReady,
			bInterrupted,
			CancellationBucket,
			CancellationTime), bMatchesProperty);
	}

	return true;
}
#endif
