#include "SpiritsCalling/PlatformActionRouter.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

namespace
{
	constexpr int32 Property8Iterations = 256;
	constexpr int32 Property8Seed = 0x5082026;

	using SpiritsPlatform::EPlatformAction;
	using SpiritsPlatform::EShippedCapability;

	constexpr EPlatformAction AllActions[] =
	{
		EPlatformAction::Movement,
		EPlatformAction::View,
		EPlatformAction::SummonSelection,
		EPlatformAction::Summon,
		EPlatformAction::Possession,
		EPlatformAction::LightAttack,
		EPlatformAction::HeavyAttack,
		EPlatformAction::ReturnFromPossession,
		EPlatformAction::SnapTurn,
		EPlatformAction::MenuToggle,
		EPlatformAction::MenuHover,
		EPlatformAction::MenuClick,
		EPlatformAction::MenuRelease,
		EPlatformAction::Restart
	};

	constexpr EPlatformAction GameplayActions[] =
	{
		EPlatformAction::Movement,
		EPlatformAction::View,
		EPlatformAction::SummonSelection,
		EPlatformAction::Summon,
		EPlatformAction::Possession,
		EPlatformAction::LightAttack,
		EPlatformAction::HeavyAttack,
		EPlatformAction::ReturnFromPossession,
		EPlatformAction::SnapTurn
	};

	bool ExpectedDispatch(EPlatformAction Action, bool bMenuOpen)
	{
		if (SpiritsPlatform::IsGameplayAction(Action))
		{
			return !bMenuOpen;
		}
		if (Action == EPlatformAction::MenuHover ||
			Action == EPlatformAction::MenuClick ||
			Action == EPlatformAction::MenuRelease)
		{
			return bMenuOpen;
		}
		return Action == EPlatformAction::MenuToggle || Action == EPlatformAction::Restart;
	}

	FString DescribeActionCase(int32 Iteration, int32 Step, bool bMenuOpen, EPlatformAction Action)
	{
		return FString::Printf(
			TEXT("Property 8 seed=%d iteration=%d step=%d menuOpen=%s action=%d"),
			Property8Seed,
			Iteration,
			Step,
			bMenuOpen ? TEXT("true") : TEXT("false"),
			static_cast<int32>(Action));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsPropertyP8PlatformActionTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 8: Platform action, menu lock, snap timestamps, and scope",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FSpiritsPropertyP8PlatformActionTest::RunTest(const FString& Parameters)
{
	FRandomStream Random(Property8Seed);
	AddInfo(FString::Printf(
		TEXT("Feature: spirits-calling-requirements, Property 8; seed=%d; generated iterations=%d"),
		Property8Seed,
		Property8Iterations));

	bool bObservedPC = false;
	bool bObservedPCVR = false;
	bool bObservedMenuHover = false;
	bool bObservedMenuClick = false;
	bool bObservedBlockedMovement = false;
	bool bObservedBlockedSummon = false;
	bool bObservedBlockedPossession = false;
	bool bObservedBlockedLightAttack = false;
	bool bObservedBlockedHeavyAttack = false;

	for (int32 Iteration = 0; Iteration < Property8Iterations; ++Iteration)
	{
		SpiritsPlatform::FPlatformActionRouter Router;
		int32 GameplayHandlerCalls = 0;

		// Mandatory lock probe per generated case: none of these actions may reach
		// a gameplay handler while either the PC or PCVR menu is open.
		Router.SetMenuOpen(true);
		for (EPlatformAction Action : GameplayActions)
		{
			const int32 CallsBefore = GameplayHandlerCalls;
			if (Router.CanDispatch(Action))
			{
				++GameplayHandlerCalls;
			}
			TestEqual(DescribeActionCase(Iteration, -1, true, Action), GameplayHandlerCalls, CallsBefore);
		}
		bObservedBlockedMovement |= !Router.CanDispatch(EPlatformAction::Movement);
		bObservedBlockedSummon |= !Router.CanDispatch(EPlatformAction::Summon);
		bObservedBlockedPossession |= !Router.CanDispatch(EPlatformAction::Possession);
		bObservedBlockedLightAttack |= !Router.CanDispatch(EPlatformAction::LightAttack);
		bObservedBlockedHeavyAttack |= !Router.CanDispatch(EPlatformAction::HeavyAttack);
		bObservedMenuHover |= Router.CanDispatch(EPlatformAction::MenuHover);
		bObservedMenuClick |= Router.CanDispatch(EPlatformAction::MenuClick);

		// Generated PC/PCVR action stream. Closed-menu gameplay actions represent
		// completion at the adapter boundary; open-menu pointer actions represent
		// right-controller hover/click routing to UWidgetInteractionComponent.
		const int32 Steps = Random.RandRange(16, 64);
		for (int32 Step = 0; Step < Steps; ++Step)
		{
			const bool bMenuOpen = Random.RandBool();
			Router.SetMenuOpen(bMenuOpen);
			const EPlatformAction Action = AllActions[Random.RandRange(0, UE_ARRAY_COUNT(AllActions) - 1)];
			const bool bAccepted = Router.CanDispatch(Action);
			TestEqual(
				DescribeActionCase(Iteration, Step, bMenuOpen, Action),
				bAccepted,
				ExpectedDispatch(Action, bMenuOpen));
		}

		// Every documented adapter action is dispatchable when gameplay is active.
		Router.SetMenuOpen(false);
		for (EPlatformAction Action : GameplayActions)
		{
			TestTrue(DescribeActionCase(Iteration, Steps, false, Action), Router.CanDispatch(Action));
		}
		TestTrue(TEXT("Property 8 restart routes through the platform adapter"), Router.CanDispatch(EPlatformAction::Restart));

		// Generated XR states: a missing XR system or unavailable tracking must
		// always select PC, so no-HMD launches cannot be misclassified as PCVR.
		const bool bXRSystemAvailable = Random.RandBool();
		const bool bHeadTrackingAllowed = Random.RandBool();
		const SpiritsPlatform::EPlatformMode Mode =
			SpiritsPlatform::SelectPlatformMode(bXRSystemAvailable, bHeadTrackingAllowed);
		const bool bExpectedVR = bXRSystemAvailable && bHeadTrackingAllowed;
		TestEqual(
			FString::Printf(TEXT("Property 8 iteration=%d XR=%s tracking=%s"), Iteration,
				bXRSystemAvailable ? TEXT("true") : TEXT("false"),
				bHeadTrackingAllowed ? TEXT("true") : TEXT("false")),
			Mode == SpiritsPlatform::EPlatformMode::PCVR,
			bExpectedVR);
		bObservedPC |= Mode == SpiritsPlatform::EPlatformMode::PC;
		bObservedPCVR |= Mode == SpiritsPlatform::EPlatformMode::PCVR;

		// The first turn is accepted, a generated interval below 0.35 seconds is
		// rejected without advancing the clock, and the exact boundary is accepted.
		SpiritsPlatform::FComfortTurnGate TurnGate;
		const double FirstTimestamp = Random.FRandRange(0.f, 10000.f);
		const double RejectedDelta = Random.FRandRange(0.f, 0.349f);
		TestTrue(TEXT("Property 8 first snap turn is accepted"), TurnGate.TryAccept(FirstTimestamp));
		TestFalse(
			FString::Printf(TEXT("Property 8 iteration=%d snap delta=%.6f is below 0.35"), Iteration, RejectedDelta),
			TurnGate.TryAccept(FirstTimestamp + RejectedDelta));
		TestEqual(
			TEXT("Property 8 rejected snap does not advance accepted timestamp"),
			TurnGate.GetLastAcceptedTimestamp(),
			FirstTimestamp);
		TestTrue(
			TEXT("Property 8 exact 0.35 snap interval is accepted"),
			TurnGate.TryAccept(FirstTimestamp + SpiritsPlatform::SnapTurnIntervalSeconds));

		// Generated scope declarations exercise both shipped and explicitly absent
		// capabilities without claiming external services or server products.
		const EShippedCapability Capability = static_cast<EShippedCapability>(Random.RandRange(
			static_cast<int32>(EShippedCapability::PCSinglePlayer),
			static_cast<int32>(EShippedCapability::AntiCheat)));
		const bool bExpectedShipped = Capability == EShippedCapability::PCSinglePlayer ||
			Capability == EShippedCapability::LanFriendConnection ||
			Capability == EShippedCapability::PCVR;
		TestEqual(
			FString::Printf(TEXT("Property 8 iteration=%d capability=%d"), Iteration, static_cast<int32>(Capability)),
			SpiritsPlatform::IsShippedCapability(Capability),
			bExpectedShipped);
	}

	TestTrue(TEXT("generated mode states include PC"), bObservedPC);
	TestTrue(TEXT("generated mode states include PCVR"), bObservedPCVR);
	TestTrue(TEXT("menu routes hover to UI"), bObservedMenuHover);
	TestTrue(TEXT("menu routes click to UI"), bObservedMenuClick);
	TestTrue(TEXT("menu blocks movement handler"), bObservedBlockedMovement);
	TestTrue(TEXT("menu blocks summon handler"), bObservedBlockedSummon);
	TestTrue(TEXT("menu blocks possession handler"), bObservedBlockedPossession);
	TestTrue(TEXT("menu blocks light attack handler"), bObservedBlockedLightAttack);
	TestTrue(TEXT("menu blocks heavy attack handler"), bObservedBlockedHeavyAttack);

	TestTrue(TEXT("scope includes PC single-player"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::PCSinglePlayer));
	TestTrue(TEXT("scope includes LAN/friend connection"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::LanFriendConnection));
	TestTrue(TEXT("scope includes PCVR"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::PCVR));
	TestFalse(TEXT("scope excludes public matchmaking"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::PublicMatchmaking));
	TestFalse(TEXT("scope excludes dedicated servers"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::DedicatedServer));
	TestFalse(TEXT("scope excludes Nakama authentication"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::NakamaAuthentication));
	TestFalse(TEXT("scope excludes anti-cheat"),
		SpiritsPlatform::IsShippedCapability(EShippedCapability::AntiCheat));

	return true;
}
#endif
