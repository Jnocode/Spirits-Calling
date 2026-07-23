#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Math/RandomStream.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsPropertyP3SummonTransactionTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 3: Server summon validation and economy invariant",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

namespace
{
	FString DescribeCase(
		int32 CaseIndex,
		int32 Balance,
		int32 LoadoutSize,
		int32 ArchetypeIndex,
		ESpiritsMatchPhase Phase,
		bool bLocationValid,
		bool bSpawnSucceeded,
		const SpiritsRules::FSummonValidation& Validation)
	{
		return FString::Printf(
			TEXT("case=%d balance=%d loadoutSize=%d archetypeIndex=%d phase=%d locationValid=%s spawnSucceeded=%s accepted=%s cost=%d failure=%s"),
			CaseIndex,
			Balance,
			LoadoutSize,
			ArchetypeIndex,
			static_cast<int32>(Phase),
			bLocationValid ? TEXT("true") : TEXT("false"),
			bSpawnSucceeded ? TEXT("true") : TEXT("false"),
			Validation.bAccepted ? TEXT("true") : TEXT("false"),
			Validation.Cost,
			*Validation.FailureCode);
	}

	void AddPropertyFailure(
		FAutomationTestBase& Test,
		int32 Seed,
		const FString& CaseDescription,
		const FString& Assertion)
	{
		Test.AddError(FString::Printf(
			TEXT("Property 3 counterexample (seed=%d): %s; %s"),
			Seed,
			*CaseDescription,
			*Assertion));
	}
}

bool FSpiritsPropertyP3SummonTransactionTest::RunTest(const FString& Parameters)
{
	// Generated deterministic cases make failures reproducible without relying on
	// a world, actor spawning, Steam, or editor-only state.
	constexpr int32 Seed = 0x3F17A;
	constexpr int32 Iterations = 256;
	FRandomStream Random(Seed);

	for (int32 CaseIndex = 0; CaseIndex < Iterations; ++CaseIndex)
	{
		const int32 Balance = Random.RandRange(0, 240);
		const int32 Civilization = Random.RandRange(0, SpiritsRules::Civilizations - 1);
		TArray<FMinionArchetype> Loadout = SpiritsRules::BuildCivLoadout(Civilization);
		const bool bValidLoadout = Random.GetFraction() >= 0.25f;
		if (!bValidLoadout)
		{
			if (Random.GetFraction() < 0.5f)
			{
				Loadout.RemoveAt(0);
			}
			else
			{
				Loadout.Add(FMinionArchetype());
			}
		}

		const int32 PhaseValue = Random.RandRange(0, 2);
		const ESpiritsMatchPhase Phase = static_cast<ESpiritsMatchPhase>(PhaseValue);
		const int32 ArchetypeIndex = Random.RandRange(-1, 3);
		const bool bLocationValid = Random.GetFraction() >= 0.25f;
		const bool bSpawnSucceeded = Random.GetFraction() >= 0.5f;
		const SpiritsRules::FMatchSettings Settings{
			Phase,
			1,
			0,
			static_cast<ECivilization>(Civilization),
			ECivilization::Norse,
			false};
		const SpiritsRules::FSummonValidation Validation = SpiritsRules::ValidateSummon(
			Settings, Loadout, ArchetypeIndex, Balance, bLocationValid);
		const FString CaseDescription = DescribeCase(
			CaseIndex,
			Balance,
			Loadout.Num(),
			ArchetypeIndex,
			Phase,
			bLocationValid,
			bSpawnSucceeded,
			Validation);

		const bool bExpectedValid =
			Phase == ESpiritsMatchPhase::InProgress &&
			Loadout.Num() == SpiritsRules::ArchetypesPerCivilization &&
			Loadout.IsValidIndex(ArchetypeIndex) &&
			Loadout[ArchetypeIndex].SummonCost >= 0 &&
			Balance >= Loadout[ArchetypeIndex].SummonCost &&
			bLocationValid;
		if (Validation.bAccepted != bExpectedValid)
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("validation acceptance differs from generated oracle"));
			continue;
		}
		if (!Validation.bAccepted && Validation.FailureCode.IsEmpty())
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("invalid request has no failure indication"));
			continue;
		}

		const FString Token = FString::Printf(TEXT("p3-%d"), CaseIndex);
		const SpiritsRules::FSummonTransactionState Initial =
			SpiritsRules::BeginSummonTransaction(Validation, Balance, Token);
		const SpiritsRules::FSummonTransactionResult First =
			SpiritsRules::EvaluateSummonTransaction(Validation, Initial, bSpawnSucceeded);
		const SpiritsRules::FSummonTransactionResult Second =
			SpiritsRules::EvaluateSummonTransaction(Validation, First.State, !bSpawnSucceeded);

		if (!Validation.bAccepted)
		{
			if (Initial.bCostDeducted || First.bSpawned || First.bRefundApplied || First.bRefundEventEmitted ||
				First.SoulsAfter != Balance || !First.bFailureIndicated)
			{
				AddPropertyFailure(*this, Seed, CaseDescription, TEXT("invalid request changed spawn/economy or omitted failure indication"));
			}
			continue;
		}

		if (!Initial.bCostDeducted || Initial.TransactionToken != Token || First.TransactionToken != Token ||
			First.State.TransactionToken != Token)
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("accepted transaction did not carry its token or exact deduction state"));
			continue;
		}
		const int32 ExpectedSoulsAfter = bSpawnSucceeded
			? Balance - Validation.Cost
			: Balance;
		if (First.bSpawned != bSpawnSucceeded || First.SoulsAfter != ExpectedSoulsAfter)
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("spawn result or Soul balance does not match exact-cost oracle"));
			continue;
		}
		if (bSpawnSucceeded)
		{
			if (First.bRefundApplied || First.bRefundEventEmitted || First.bFailureIndicated ||
				Balance - First.SoulsAfter != Validation.Cost)
			{
				AddPropertyFailure(*this, Seed, CaseDescription, TEXT("successful summon did not commit exactly the archetype cost"));
			}
		}
		else if (!First.bRefundApplied || !First.bRefundEventEmitted || !First.bFailureIndicated ||
			First.FailureCode != SpiritsRules::FailureCodes::SpawnFailedRefunded)
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("validated spawn failure did not refund exactly once and indicate failure"));
		}

		if (!Second.bAlreadySettled || Second.bRefundEventEmitted || Second.SoulsAfter != First.SoulsAfter)
		{
			AddPropertyFailure(*this, Seed, CaseDescription, TEXT("repeated transaction callback was not idempotent"));
		}
	}

	return !HasAnyErrors();
}
#endif
