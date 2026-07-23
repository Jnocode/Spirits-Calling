#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ConfigCacheIni.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsSteamReadinessAutomationTest,
	"SpiritsCalling.Achievements.SteamReadinessStateMachine",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsSteamReadinessAutomationTest::RunTest(const FString& Parameters)
{
	SpiritsRules::FAchievementBackendProbe Probe;
	Probe.ApprovedAppIds = { 123456 };

	Probe.AppId = 0;
	SpiritsRules::FAchievementBackendReadiness Result =
		SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("zero App ID is disabled"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::Disabled));
	TestEqual(TEXT("zero App ID is locatable"), Result.FailureCode, FString(TEXT("Steam.AppIdInvalid")));
	TestTrue(TEXT("fallback remains available"), Result.bDevelopmentFallbackPass);
	TestFalse(TEXT("fallback is not Steam release acceptance"), Result.bSteamReleaseAcceptance);

	Probe.AppId = 480;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("480 placeholder is disabled"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::Disabled));
	TestEqual(TEXT("480 placeholder is rejected"), Result.FailureCode, FString(TEXT("Steam.AppIdInvalid")));

	Probe.AppId = 123456;
	Probe.bConfigEnabled = false;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("disabled Steam config remains fallback-only"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::ConfigValid));
	TestEqual(TEXT("disabled Steam config is locatable"), Result.FailureCode, FString(TEXT("Steam.SubsystemUnavailable")));

	Probe.bConfigEnabled = true;
	Probe.bOSSAvailable = false;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("valid config stops at ConfigValid when OSS is unavailable"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::ConfigValid));
	TestEqual(TEXT("OSS failure is locatable"), Result.FailureCode, FString(TEXT("Steam.SubsystemUnavailable")));

	Probe.bOSSAvailable = true;
	Probe.bIdentityAvailable = false;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("OSS-ready state stops before identity"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::OSSReady));
	TestEqual(TEXT("identity failure is locatable"), Result.FailureCode, FString(TEXT("Steam.IdentityUnavailable")));

	Probe.bIdentityAvailable = true;
	Probe.bDefinitionsQuerySucceeded = false;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("identity-ready state stops before definitions"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::IdentityReady));
	TestEqual(TEXT("definition failure is locatable"), Result.FailureCode, FString(TEXT("Steam.DefinitionQueryFailed")));

	Probe.bDefinitionsQuerySucceeded = true;
	Result = SpiritsRules::EvaluateAchievementBackendReadiness(Probe);
	TestEqual(TEXT("approved non-placeholder ID reaches WriteEligible"),
		static_cast<uint8>(Result.State),
		static_cast<uint8>(SpiritsRules::EAchievementBackendState::WriteEligible));
	TestTrue(TEXT("identity is ready"), Result.bIdentityAvailable);
	TestTrue(TEXT("definitions are ready"), Result.bDefinitionsAvailable);
	TestFalse(TEXT("Steam readiness uses the Steam path instead of fallback"), Result.bDevelopmentFallbackPass);
	TestFalse(TEXT("Steam release acceptance remains evidence-driven"), Result.bSteamReleaseAcceptance);

	// The UE Steam adapter reads sequential Achievement_N_Id keys and stops at
	// the first gap. Keep this local config exactly aligned with the canonical
	// runtime IDs; Steamworks still supplies the external definitions/evidence.
	const TArray<FString>& CanonicalIds = SpiritsRules::GetAchievementIds();
	TestEqual(TEXT("canonical achievement count is exactly eight"), CanonicalIds.Num(), 8);
	TSet<FString> ConfiguredIds;
	for (int32 Index = 0; Index < CanonicalIds.Num(); ++Index)
	{
		FString ConfiguredId;
		const bool bFound = GConfig && GConfig->GetString(
			TEXT("OnlineSubsystemSteam"),
			*FString::Printf(TEXT("Achievement_%d_Id"), Index),
			ConfiguredId,
			GEngineIni);
		TestTrue(FString::Printf(TEXT("Steam config defines Achievement_%d_Id"), Index), bFound);
		TestEqual(FString::Printf(TEXT("Steam config ID %d is canonical"), Index), ConfiguredId, CanonicalIds[Index]);
		ConfiguredIds.Add(ConfiguredId);
	}
	FString UnexpectedNinthId;
	const bool bHasNinthId = GConfig && GConfig->GetString(
		TEXT("OnlineSubsystemSteam"), TEXT("Achievement_8_Id"), UnexpectedNinthId, GEngineIni);
	TestFalse(TEXT("Steam config has no ninth definition"), bHasNinthId && !UnexpectedNinthId.IsEmpty());
	TestEqual(TEXT("Steam config IDs are unique"), ConfiguredIds.Num(), CanonicalIds.Num());

	return !HasAnyErrors();
}
#endif
