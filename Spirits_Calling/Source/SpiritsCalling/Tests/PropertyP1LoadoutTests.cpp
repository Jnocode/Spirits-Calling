#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Math/RandomStream.h"

namespace
{
	constexpr int32 PropertyIterations = 256;
	constexpr int32 PropertySeed = 0x51C1A11;

	FString DescribeArchetype(const FMinionArchetype& Archetype)
	{
		return FString::Printf(
			TEXT("{name=\"%s\", health=%.3f, attack=%.3f, range=%.3f, interval=%.3f, speed=%.3f, cost=%d, tint=(%.3f,%.3f,%.3f,%.3f), meshScale=%.3f}"),
			*Archetype.DisplayName,
			Archetype.MaxHP,
			Archetype.AttackDamage,
			Archetype.AttackRange,
			Archetype.AttackInterval,
			Archetype.MoveSpeed,
			Archetype.SummonCost,
			Archetype.Tint.R,
			Archetype.Tint.G,
			Archetype.Tint.B,
			Archetype.Tint.A,
			Archetype.MeshScale);
	}

	bool HasFinitePositiveValue(float Value)
	{
		return FMath::IsFinite(Value) && Value > 0.f;
	}

	bool HasConfiguredTint(const FLinearColor& Tint)
	{
		return FMath::IsFinite(Tint.R) &&
			FMath::IsFinite(Tint.G) &&
			FMath::IsFinite(Tint.B) &&
			FMath::IsFinite(Tint.A) &&
			(FMath::Abs(Tint.R) > KINDA_SMALL_NUMBER ||
				FMath::Abs(Tint.G) > KINDA_SMALL_NUMBER ||
				FMath::Abs(Tint.B) > KINDA_SMALL_NUMBER ||
				FMath::Abs(Tint.A) > KINDA_SMALL_NUMBER);
	}

	bool RequiredFieldsEqual(const FMinionArchetype& Left, const FMinionArchetype& Right)
	{
		return FMath::IsNearlyEqual(Left.MaxHP, Right.MaxHP) &&
			FMath::IsNearlyEqual(Left.AttackDamage, Right.AttackDamage) &&
			FMath::IsNearlyEqual(Left.AttackRange, Right.AttackRange) &&
			FMath::IsNearlyEqual(Left.AttackInterval, Right.AttackInterval) &&
			FMath::IsNearlyEqual(Left.MoveSpeed, Right.MoveSpeed) &&
			Left.SummonCost == Right.SummonCost &&
			Left.Tint.Equals(Right.Tint) &&
			FMath::IsNearlyEqual(Left.MeshScale, Right.MeshScale);
	}

	FString DescribeLoadout(const TArray<FMinionArchetype>& Loadout)
	{
		FString Description;
		for (int32 EntryIndex = 0; EntryIndex < Loadout.Num(); ++EntryIndex)
		{
			if (EntryIndex > 0)
			{
				Description += TEXT(", ");
			}
			Description += FString::Printf(TEXT("[%d]=%s"), EntryIndex, *DescribeArchetype(Loadout[EntryIndex]));
		}
		return Description;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsCivilizationLoadoutPropertyTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 1: Civilization loadout shape, configured values, and distinct entries",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsCivilizationLoadoutPropertyTest::RunTest(const FString& Parameters)
{
	FRandomStream Generator(PropertySeed);
	bool bSawCivilization[SpiritsRules::Civilizations] = { false, false, false, false };

	for (int32 Iteration = 0; Iteration < PropertyIterations; ++Iteration)
	{
		const int32 CivilizationValue = Generator.RandRange(0, SpiritsRules::Civilizations - 1);
		const int32 ArchetypeIndex = Generator.RandRange(0, SpiritsRules::ArchetypesPerCivilization - 1);
		const ECivilization Civilization = static_cast<ECivilization>(CivilizationValue);
		const TArray<FMinionArchetype> Loadout = SpiritsRules::BuildCivLoadout(Civilization);
		const FString Context = FString::Printf(
			TEXT("seed=%d iteration=%d civilization=%d archetypeIndex=%d"),
			PropertySeed,
			Iteration,
			CivilizationValue,
			ArchetypeIndex);

		bSawCivilization[CivilizationValue] = true;
		TestEqual(
			FString::Printf(TEXT("%s: exactly three summonable entries"), *Context),
			Loadout.Num(),
			SpiritsRules::ArchetypesPerCivilization);
		if (Loadout.Num() != SpiritsRules::ArchetypesPerCivilization)
		{
			AddError(FString::Printf(TEXT("Counterexample: %s loadout=%s"), *Context, *DescribeLoadout(Loadout)));
			continue;
		}

		TestTrue(
			FString::Printf(TEXT("%s: generated archetype index is valid"), *Context),
			Loadout.IsValidIndex(ArchetypeIndex));
		if (!Loadout.IsValidIndex(ArchetypeIndex))
		{
			AddError(FString::Printf(TEXT("Counterexample: %s loadout=%s"), *Context, *DescribeLoadout(Loadout)));
			continue;
		}

		for (int32 EntryIndex = 0; EntryIndex < Loadout.Num(); ++EntryIndex)
		{
			const FMinionArchetype& Entry = Loadout[EntryIndex];
			const FString EntryContext = FString::Printf(
				TEXT("%s entry=%d stats=%s"),
				*Context,
				EntryIndex,
				*DescribeArchetype(Entry));

			TestTrue(
				FString::Printf(TEXT("%s: health is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.MaxHP));
			TestTrue(
				FString::Printf(TEXT("%s: attack is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.AttackDamage));
			TestTrue(
				FString::Printf(TEXT("%s: range is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.AttackRange));
			TestTrue(
				FString::Printf(TEXT("%s: interval is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.AttackInterval));
			TestTrue(
				FString::Printf(TEXT("%s: movement speed is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.MoveSpeed));
			TestTrue(
				FString::Printf(TEXT("%s: cost is configured"), *EntryContext),
				Entry.SummonCost >= 0);
			TestTrue(
				FString::Printf(TEXT("%s: tint is configured"), *EntryContext),
				HasConfiguredTint(Entry.Tint));
			TestTrue(
				FString::Printf(TEXT("%s: mesh scale is configured"), *EntryContext),
				HasFinitePositiveValue(Entry.MeshScale));
		}

		for (int32 LeftIndex = 0; LeftIndex < Loadout.Num(); ++LeftIndex)
		{
			for (int32 RightIndex = LeftIndex + 1; RightIndex < Loadout.Num(); ++RightIndex)
			{
				const bool bDistinct = !RequiredFieldsEqual(Loadout[LeftIndex], Loadout[RightIndex]);
				TestTrue(
					FString::Printf(
						TEXT("%s: entries %d and %d differ in required stat vector"),
						*Context,
						LeftIndex,
						RightIndex),
					bDistinct);
				if (!bDistinct)
				{
					AddError(FString::Printf(
						TEXT("Counterexample: %s entries %d and %d are identical: %s == %s"),
						*Context,
						LeftIndex,
						RightIndex,
						*DescribeArchetype(Loadout[LeftIndex]),
						*DescribeArchetype(Loadout[RightIndex])));
				}
			}
		}
	}

	for (int32 CivilizationValue = 0; CivilizationValue < SpiritsRules::Civilizations; ++CivilizationValue)
	{
		TestTrue(
			FString::Printf(TEXT("seed=%d generated civilization %d at least once"), PropertySeed, CivilizationValue),
			bSawCivilization[CivilizationValue]);
	}

	return true;
}
#endif
