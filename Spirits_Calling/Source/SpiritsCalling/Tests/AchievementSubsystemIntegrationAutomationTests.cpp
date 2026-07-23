#include "SpiritsCalling/SpiritsAchievements.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Misc/AutomationTest.h"
#include "SpiritsCalling/SpiritsRules.h"

// Integration regression for the production USpiritsAchievements GameInstance
// subsystem — the exact glue the ASpiritsPlayerController client RPCs call.
// Property 5 covers the pure SpiritsRules router via a fake backend; this suite
// drives the real subsystem's event routing, exact-ID gate, deduplication and
// fallback semantics with no Steam backend available. It asserts that, without
// approved Steam credentials, the subsystem stays in a development fallback
// state that never claims Steam release acceptance while still preserving local
// achievement progress. Real Steam write acceptance (approved App ID, identity,
// eight external definitions, live write callbacks) remains a separate gate.
namespace
{
	USpiritsAchievements* MakeAchievementsSubsystem()
	{
		if (!GEngine)
		{
			return nullptr;
		}
		// A GameInstanceSubsystem's ClassWithin is UGameInstance, so it must be
		// outered to a real GameInstance. The subsystem's fallback path only reads
		// config/OSS and never dereferences the instance, so a bare instance is a
		// sufficient, headless-safe outer for this regression.
		UGameInstance* GameInstance = NewObject<UGameInstance>(GEngine);
		USpiritsAchievements* Subsystem = NewObject<USpiritsAchievements>(GameInstance);
		if (Subsystem)
		{
			Subsystem->InitializeForAutomation();
		}
		return Subsystem;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsAchievementSubsystemIntegrationTest,
	"SpiritsCalling.Achievements.SubsystemIntegration event routing, dedup, and fallback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsAchievementSubsystemIntegrationTest::RunTest(const FString& Parameters)
{
	// The canonical runtime ID set is exactly the eight documented achievements.
	const TArray<FString>& CanonicalIds = SpiritsRules::GetAchievementIds();
	TestEqual(TEXT("canonical achievement count is exactly eight"), CanonicalIds.Num(), 8);
	for (const FString& Id : {
			SpiritsAch::FirstWin, SpiritsAch::WinEasy, SpiritsAch::WinNormal, SpiritsAch::WinHard,
			SpiritsAch::PossessKill50, SpiritsAch::Summon100, SpiritsAch::WinAllCivs, SpiritsAch::LanWin })
	{
		TestTrue(FString::Printf(TEXT("canonical set contains %s"), *Id), CanonicalIds.Contains(Id));
	}

	// ---------------------------------------------------- fallback state gate
	USpiritsAchievements* Ach = MakeAchievementsSubsystem();
	if (!TestNotNull(TEXT("achievement subsystem is constructed"), Ach))
	{
		return false;
	}
	// With no approved App ID configured the subsystem must not be write-eligible
	// and must never assert Steam release acceptance; fallback stays available.
	TestFalse(TEXT("no approved App ID means not Steam write eligible"), Ach->IsSteamWriteEligible());
	TestFalse(TEXT("fallback subsystem never claims Steam release acceptance"), Ach->IsSteamReleaseAcceptance());
	TestTrue(TEXT("development fallback remains available without Steam"), Ach->IsDevelopmentFallbackPass());

	// ---------------------------------------------------- unknown ID rejection
	Ach->UnlockAchievement(TEXT("ACH_DOES_NOT_EXIST"));
	TestEqual(TEXT("unknown achievement ID is not recorded"), Ach->GetUnlockedCountForAutomation(), 0);
	TestFalse(TEXT("unknown achievement ID stays locked"), Ach->HasUnlockedForAutomation(TEXT("ACH_DOES_NOT_EXIST")));

	// ----------------------------------------------------- win event routing
	Ach->ReportWin(/*Difficulty=*/0, /*Civ=*/0, /*bLan=*/false);
	TestTrue(TEXT("first win unlocks ACH_FIRST_WIN"), Ach->HasUnlockedForAutomation(SpiritsAch::FirstWin));
	TestTrue(TEXT("easy win unlocks ACH_WIN_EASY"), Ach->HasUnlockedForAutomation(SpiritsAch::WinEasy));
	TestFalse(TEXT("easy win does not unlock ACH_WIN_NORMAL"), Ach->HasUnlockedForAutomation(SpiritsAch::WinNormal));
	TestFalse(TEXT("easy win does not unlock ACH_WIN_HARD"), Ach->HasUnlockedForAutomation(SpiritsAch::WinHard));
	TestFalse(TEXT("offline win does not unlock ACH_LAN_WIN"), Ach->HasUnlockedForAutomation(SpiritsAch::LanWin));

	// Deduplication: repeating the same easy win adds no new unlocks.
	const int32 AfterFirstEasyWin = Ach->GetUnlockedCountForAutomation();
	Ach->ReportWin(0, 0, false);
	TestEqual(TEXT("repeating the same win does not re-unlock"), Ach->GetUnlockedCountForAutomation(), AfterFirstEasyWin);

	// A hard LAN win adds exactly the hard-difficulty and LAN achievements.
	Ach->ReportWin(/*Difficulty=*/2, /*Civ=*/1, /*bLan=*/true);
	TestTrue(TEXT("hard win unlocks ACH_WIN_HARD"), Ach->HasUnlockedForAutomation(SpiritsAch::WinHard));
	TestTrue(TEXT("LAN win unlocks ACH_LAN_WIN"), Ach->HasUnlockedForAutomation(SpiritsAch::LanWin));

	// ----------------------------------------------- possession-kill threshold
	for (int32 Kill = 0; Kill < 49; ++Kill)
	{
		Ach->ReportPossessKill();
	}
	TestFalse(TEXT("49 possession kills do not unlock the milestone"),
		Ach->HasUnlockedForAutomation(SpiritsAch::PossessKill50));
	Ach->ReportPossessKill(); // 50th
	TestTrue(TEXT("50 possession kills unlock ACH_POSSESS_KILL_50"),
		Ach->HasUnlockedForAutomation(SpiritsAch::PossessKill50));
	TestEqual(TEXT("possession-kill counter persists across events"), Ach->GetPossessKillsForAutomation(), 50);

	// -------------------------------------------------------- summon threshold
	for (int32 Summon = 0; Summon < 99; ++Summon)
	{
		Ach->ReportSummon();
	}
	TestFalse(TEXT("99 summons do not unlock the milestone"),
		Ach->HasUnlockedForAutomation(SpiritsAch::Summon100));
	Ach->ReportSummon(); // 100th
	TestTrue(TEXT("100 summons unlock ACH_SUMMON_100"),
		Ach->HasUnlockedForAutomation(SpiritsAch::Summon100));

	// --------------------------------------------- all-civilizations bitmask
	USpiritsAchievements* CivAch = MakeAchievementsSubsystem();
	if (TestNotNull(TEXT("all-civ subsystem is constructed"), CivAch))
	{
		CivAch->ReportWin(1, 0, false);
		CivAch->ReportWin(1, 1, false);
		CivAch->ReportWin(1, 2, false);
		TestFalse(TEXT("three civilizations do not complete the set"),
			CivAch->HasUnlockedForAutomation(SpiritsAch::WinAllCivs));
		CivAch->ReportWin(1, 3, false);
		TestTrue(TEXT("winning with all four civilizations unlocks ACH_WIN_ALL_CIVS"),
			CivAch->HasUnlockedForAutomation(SpiritsAch::WinAllCivs));
	}

	// The subsystem still never claims Steam release acceptance after local writes.
	TestFalse(TEXT("local fallback progress never becomes Steam release acceptance"),
		Ach->IsSteamReleaseAcceptance());

	return true;
}
#endif
