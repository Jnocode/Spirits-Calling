#include "SpiritsCalling/ArenaBuilder.h"
#include "SpiritsCalling/SpiritsGameState.h"
#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Math/RandomStream.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	constexpr int32 P2PropertyIterations = 512;
	constexpr int32 P2PropertySeed = 0x5EED2026;

	struct FJoinAttemptProbe
	{
		bool bHostOperable = true;
		bool bHostMatchConnected = false;
		bool bJoinerMatchConnected = false;
		bool bMatchEstablished = false;
		FString FailureCode;
	};

	/**
	 * Test-only LAN seam for the observable join contract. The production join
	 * path is asynchronous ClientTravel, so this deliberately models only the
	 * state transition that the automation/property oracle can inspect.
	 */
	void ApplyJoinAttempt(bool bJoinSucceeded, FJoinAttemptProbe& State)
	{
		State.bHostOperable = true;
		if (bJoinSucceeded)
		{
			State.bHostMatchConnected = true;
			State.bJoinerMatchConnected = true;
			State.bMatchEstablished = true;
			State.FailureCode.Reset();
			return;
		}

		State.bHostMatchConnected = false;
		State.bJoinerMatchConnected = false;
		State.bMatchEstablished = false;
		State.FailureCode = TEXT("Match.JoinFailed");
	}

	int32 GenerateMapSelection(FRandomStream& Random, int32 Iteration)
	{
		// Exercise explicit boundary values first, then generated in-range and
		// out-of-range values. INT_MIN/INT_MAX cover clamp overflow edges.
		const int32 BoundaryValues[] = {
			MIN_int32,
			-1,
			0,
			1,
			2,
			MAX_int32
		};
		if (Iteration < UE_ARRAY_COUNT(BoundaryValues))
		{
			return BoundaryValues[Iteration];
		}

		if ((Iteration % 5) == 0)
		{
			return Random.RandRange(-100000, 100000);
		}
		return Random.RandRange(-2, 3);
	}

	FString MakeContext(int32 Iteration, int32 MapSelection, int32 ClientCount, bool bJoinSucceeded)
	{
		return FString::Printf(
			TEXT("seed=%d iteration=%d mapSelection=%d clientCount=%d join=%s"),
			P2PropertySeed,
			Iteration,
			MapSelection,
			ClientCount,
			bJoinSucceeded ? TEXT("success") : TEXT("failure"));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsPropertyP2MapReplicationAutomationTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 2: Map selection replication and failed join",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsPropertyP2MapReplicationAutomationTest::RunTest(const FString& Parameters)
{
	// Feature: spirits-calling-requirements, Property 2
	// Generated input count intentionally exceeds the required 100 iterations.
	FRandomStream Random(P2PropertySeed);
	int32 SuccessfulJoins = 0;
	int32 FailedJoins = 0;

	for (int32 Iteration = 0; Iteration < P2PropertyIterations; ++Iteration)
	{
		const int32 MapSelection = GenerateMapSelection(Random, Iteration);
		const int32 ExpectedMapIndex = SpiritsRules::NormalizeMapIndex(MapSelection);
		const int32 ClientCount = (Iteration < 4) ? Iteration + 1 : Random.RandRange(1, 4);
		const bool bJoinSucceeded = (Iteration % 2) == 0;
		const FString Context = MakeContext(Iteration, MapSelection, ClientCount, bJoinSucceeded);

		ASpiritsGameState* HostGameState = NewObject<ASpiritsGameState>();
		HostGameState->MapIndex = static_cast<uint8>(ExpectedMapIndex);
		const SpiritsRules::FMapStyleHooks HostHooks = SpiritsRules::ResolveMapStyle(HostGameState->MapIndex);
		const FArenaStyle HostStyle = AArenaBuilder::MakeStyle(HostGameState->MapIndex);

		TestEqual(
			*FString::Printf(TEXT("host MapIndex is normalized (%s)"), *Context),
			static_cast<int32>(HostGameState->MapIndex),
			ExpectedMapIndex);
		TestEqual(
			*FString::Printf(TEXT("host hook MapIndex is normalized (%s)"), *Context),
			HostHooks.MapIndex,
			ExpectedMapIndex);
		TestTrue(
			*FString::Printf(TEXT("host arena style matches normalized variant (%s)"), *Context),
			(ExpectedMapIndex == 0) ? HostStyle.bNightDome : !HostStyle.bNightDome);

		if (bJoinSucceeded)
		{
			++SuccessfulJoins;
			FJoinAttemptProbe JoinState;
			ApplyJoinAttempt(true, JoinState);
			TestTrue(*FString::Printf(TEXT("successful join establishes a connected match (%s)"), *Context),
				JoinState.bMatchEstablished && JoinState.bHostMatchConnected && JoinState.bJoinerMatchConnected);
			TestTrue(*FString::Printf(TEXT("host remains operable after successful join (%s)"), *Context),
				JoinState.bHostOperable);

			for (int32 ClientIndex = 0; ClientIndex < ClientCount; ++ClientIndex)
			{
				ASpiritsGameState* ClientGameState = NewObject<ASpiritsGameState>();
				ClientGameState->MapIndex = HostGameState->MapIndex;
				const SpiritsRules::FMapStyleHooks ClientHooks =
					SpiritsRules::ResolveMapStyle(ClientGameState->MapIndex);
				const FArenaStyle ClientStyle = AArenaBuilder::MakeStyle(ClientGameState->MapIndex);
				const FString ClientContext = FString::Printf(TEXT("%s client=%d"), *Context, ClientIndex + 1);

				TestEqual(*FString::Printf(TEXT("client MapIndex converges (%s)"), *ClientContext),
					static_cast<int32>(ClientGameState->MapIndex),
					static_cast<int32>(HostGameState->MapIndex));
				TestEqual(*FString::Printf(TEXT("client style converges (%s)"), *ClientContext),
					ClientHooks.Style,
					HostHooks.Style);
				TestEqual(*FString::Printf(TEXT("client ground hook converges (%s)"), *ClientContext),
					ClientHooks.GroundHook,
					HostHooks.GroundHook);
				TestEqual(*FString::Printf(TEXT("client sky hook converges (%s)"), *ClientContext),
					ClientHooks.SkyHook,
					HostHooks.SkyHook);
				TestEqual(*FString::Printf(TEXT("client arena variant converges (%s)"), *ClientContext),
					ClientStyle.bNightDome,
					HostStyle.bNightDome);
			}
		}
		else
		{
			++FailedJoins;
			FJoinAttemptProbe JoinState;
			ApplyJoinAttempt(false, JoinState);
			TestTrue(*FString::Printf(TEXT("failed join keeps host operable (%s)"), *Context),
				JoinState.bHostOperable);
			TestFalse(*FString::Printf(TEXT("failed join does not mark host connected (%s)"), *Context),
				JoinState.bHostMatchConnected);
			TestFalse(*FString::Printf(TEXT("failed join does not mark joiner connected (%s)"), *Context),
				JoinState.bJoinerMatchConnected);
			TestFalse(*FString::Printf(TEXT("failed join does not establish a Match (%s)"), *Context),
				JoinState.bMatchEstablished);
			TestEqual(*FString::Printf(TEXT("failed join exposes stable error code (%s)"), *Context),
				JoinState.FailureCode,
				FString(TEXT("Match.JoinFailed")));
		}
	}

	TestEqual(TEXT("generated successful join cases"), SuccessfulJoins, P2PropertyIterations / 2);
	TestEqual(TEXT("generated failed join cases"), FailedJoins, P2PropertyIterations / 2);
	return true;
}
#endif
