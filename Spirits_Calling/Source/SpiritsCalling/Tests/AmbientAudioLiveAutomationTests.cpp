#include "SpiritsCalling/ArenaBuilder.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "SpiritsCalling/SpiritsAudio.h"
#include "Sound/SoundBase.h"
#include "UObject/Package.h"

// Live observation of the documented ambient fallback (Requirement 6.10 / audio
// gate). S_Ambient has no loop flag on the asset; ArenaBuilder retriggers it every
// ~11.2s. This test proves, in a real ticked world, that (1) S_Ambient resolves as
// a runtime USoundBase via the exact game code path, and (2) the retrigger fallback
// actually fires on the interval. Scripts/ambient_smoke_runner.py turns a PASS here
// into the live ambient evidence the audio validator consumes — evidence is never
// hand-written.
namespace
{
	// Uniquely named (NOT the shared FScopedSpiritsTestWorld) to stay safe under
	// adaptive unity builds — see the P1/P2/P7 ODR pitfall.
	struct FScopedAmbientTestWorld
	{
		FScopedAmbientTestWorld()
		{
			if (!GEngine)
			{
				return;
			}
			const FName WorldName = MakeUniqueObjectName(
				GetTransientPackage(), UWorld::StaticClass(), TEXT("SpiritsAmbientTestWorld"));
			FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::Game);
			World = UWorld::CreateWorld(EWorldType::Game, false, WorldName, GetTransientPackage());
			if (!World)
			{
				return;
			}
			World->AddToRoot();
			WorldContext.SetCurrentWorld(World);
		}

		~FScopedAmbientTestWorld()
		{
			if (!World || !GEngine)
			{
				return;
			}
			if (World->HasBegunPlay())
			{
				World->EndPlay(EEndPlayReason::Quit);
			}
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
			World->RemoveFromRoot();
		}

		UWorld* World = nullptr;
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsAmbientAudioLiveTest,
	"SpiritsCalling.Requirements.Audio.S_Ambient resolves and documented retrigger fallback fires",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsAmbientAudioLiveTest::RunTest(const FString& Parameters)
{
	// 1. S_Ambient resolves as a real runtime USoundBase via the exact game path.
	USoundBase* Ambient = SpiritsAudio::Get(TEXT("S_Ambient"));
	TestNotNull(TEXT("S_Ambient resolves as a runtime USoundBase"), Ambient);

	// 2. The documented retrigger fallback fires in a live ticked world.
	FScopedAmbientTestWorld Fixture;
	if (!TestNotNull(TEXT("Transient game world is created"), Fixture.World))
	{
		return false;
	}
	AArenaBuilder* Arena = Fixture.World->SpawnActor<AArenaBuilder>();
	if (!TestNotNull(TEXT("ArenaBuilder is spawned"), Arena))
	{
		return false;
	}

	// AmbientAccum starts at 0 -> the first advance retriggers immediately.
	Arena->AdvanceAmbientBedForAutomation(0.01f);
	TestEqual(TEXT("first advance retriggers ambient"),
		Arena->GetAmbientRetriggerCountForAutomation(), 1);

	// A partial interval below 11.2s must NOT re-fire.
	Arena->AdvanceAmbientBedForAutomation(1.0f);
	TestEqual(TEXT("no re-fire before the ~11.2s interval"),
		Arena->GetAmbientRetriggerCountForAutomation(), 1);

	// Crossing the interval re-fires the ambient bed (proving continuous playback).
	Arena->AdvanceAmbientBedForAutomation(11.2f);
	TestEqual(TEXT("re-fires after the interval"),
		Arena->GetAmbientRetriggerCountForAutomation(), 2);

	return true;
}
#endif
