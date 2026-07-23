#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsCoreRuntimeAuthorityAutomationTest,
	"SpiritsCalling.Requirements.CoreRuntime.Authority gates, difficulty snapshot, AI wave suppression, and combat phase",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsCoreRuntimeAuthorityAutomationTest::RunTest(const FString& Parameters)
{
	constexpr int32 Seed = 0x51A17E;
	constexpr int32 Iterations = 256;
	FRandomStream Random(Seed);

	const SpiritsRules::FDifficultyTuning Easy = SpiritsRules::ResolveDifficultyTuning(0);
	const SpiritsRules::FDifficultyTuning Normal = SpiritsRules::ResolveDifficultyTuning(1);
	const SpiritsRules::FDifficultyTuning Hard = SpiritsRules::ResolveDifficultyTuning(2);
	TestEqual(TEXT("Easy is normalized"), Easy.Difficulty, 0);
	TestEqual(TEXT("Normal is normalized"), Normal.Difficulty, 1);
	TestEqual(TEXT("Hard is normalized"), Hard.Difficulty, 2);
	TestTrue(TEXT("Every difficulty pair differs in pressure or economy"),
		Easy.AIWaveInterval != Normal.AIWaveInterval &&
		Easy.AIWaveInterval != Hard.AIWaveInterval &&
		Normal.AIWaveInterval != Hard.AIWaveInterval);
	TestTrue(TEXT("Hard has greater wave pressure than Normal"),
		Hard.AIWaveInterval < Normal.AIWaveInterval && Hard.MaxWaveSize > Normal.MaxWaveSize);

	for (int32 Iteration = 0; Iteration < Iterations; ++Iteration)
	{
		const int32 RawDifficulty = Random.RandRange(-20, 20);
		const SpiritsRules::FDifficultyTuning Tuning = SpiritsRules::ResolveDifficultyTuning(RawDifficulty);
		const int32 ExpectedDifficulty = FMath::Clamp(
			RawDifficulty, SpiritsRules::MinDifficulty, SpiritsRules::MaxDifficulty);
		TestEqual(
			FString::Printf(TEXT("difficulty normalization seed=%d iteration=%d"), Seed, Iteration),
			Tuning.Difficulty,
			ExpectedDifficulty);

		const ESpiritsMatchPhase Phase = static_cast<ESpiritsMatchPhase>(Random.RandRange(0, 2));
		const bool bHumanTeamBSeen = Random.RandBool();
		const bool bTeamBHasHuman = Random.RandBool();
		const bool bExpectedWaves =
			Phase == ESpiritsMatchPhase::InProgress && !bHumanTeamBSeen && !bTeamBHasHuman;
		TestEqual(
			FString::Printf(TEXT("AI wave authority seed=%d iteration=%d"), Seed, Iteration),
			SpiritsRules::ShouldRunAIWaves(Phase, bHumanTeamBSeen, bTeamBHasHuman),
			bExpectedWaves);

		const bool bAlive = Random.RandBool();
		const bool bIsStructure = Random.RandBool();
		const bool bExpectedCombat =
			Phase == ESpiritsMatchPhase::InProgress && bAlive && !bIsStructure;
		TestEqual(
			FString::Printf(TEXT("combat authority seed=%d iteration=%d"), Seed, Iteration),
			SpiritsRules::CanResolveCombat(Phase, bAlive, bIsStructure),
			bExpectedCombat);
	}

	// Once observed, Team B remains a permanent wave barrier even if the current
	// player snapshot temporarily reports no Team B player (disconnect/reorder).
	TestFalse(TEXT("Team B seen permanently suppresses future waves"),
		SpiritsRules::ShouldRunAIWaves(ESpiritsMatchPhase::InProgress, true, false));
	TestFalse(TEXT("Ended phase rejects queued combat"),
		SpiritsRules::CanResolveCombat(ESpiritsMatchPhase::Ended, true, false));

	return !HasAnyErrors();
}
#endif
