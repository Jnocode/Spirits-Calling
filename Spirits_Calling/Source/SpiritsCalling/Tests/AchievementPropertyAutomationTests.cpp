#include "SpiritsCalling/SpiritsRules.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

namespace
{
	struct FFakeUser
	{
		bool bIdentityAvailable = false;
		bool bQuerySucceeds = false;
		TSet<FString> Definitions;
	};

	class FFakeAchievementBackend final : public SpiritsRules::IAchievementBackend
	{
	public:
		TMap<FString, FFakeUser> Users;
		TArray<FString> Operations;
		TArray<SpiritsRules::FAchievementUnlockRequest> Writes;
		TArray<SpiritsRules::FAchievementLocalRecord> FallbackRecords;

		virtual bool IsIdentityAvailable(const FString& OwnerId) const override
		{
			const FFakeUser* User = Users.Find(OwnerId);
			return User != nullptr && User->bIdentityAvailable;
		}

		virtual bool QueryDefinitions(
			const FString& OwnerId,
			TSet<FString>& OutDefinitions) override
		{
			Operations.Add(FString::Printf(TEXT("Q:%s"), *OwnerId));
			const FFakeUser* User = Users.Find(OwnerId);
			if (User == nullptr || !User->bQuerySucceeds)
			{
				return false;
			}
			OutDefinitions = User->Definitions;
			return true;
		}

		virtual bool WriteAchievement(
			const FString& OwnerId,
			const FString& AchievementId) override
		{
			Operations.Add(FString::Printf(TEXT("W:%s:%s"), *OwnerId, *AchievementId));
			SpiritsRules::FAchievementUnlockRequest Write;
			Write.OwnerId = OwnerId;
			Write.AchievementId = AchievementId;
			Writes.Add(Write);
			return true;
		}

		virtual void RecordFallback(const SpiritsRules::FAchievementLocalRecord& Record) override
		{
			FallbackRecords.Add(Record);
		}
	};

	void AddWin(TArray<SpiritsRules::FAchievementEvent>& Events, const FString& OwnerId, int32 Difficulty, int32 Civilization, bool bLan)
	{
		SpiritsRules::FAchievementEvent Event;
		Event.Type = SpiritsRules::EAchievementEventType::Win;
		Event.OwnerId = OwnerId;
		Event.Difficulty = Difficulty;
		Event.Civilization = Civilization;
		Event.bLan = bLan;
		Events.Add(Event);
	}

	void AddCountEvent(
		TArray<SpiritsRules::FAchievementEvent>& Events,
		SpiritsRules::EAchievementEventType Type,
		const FString& OwnerId)
	{
		SpiritsRules::FAchievementEvent Event;
		Event.Type = Type;
		Event.OwnerId = OwnerId;
		Events.Add(Event);
	}

	TSet<FString> AllDefinitions(const TArray<FString>& Ids)
	{
		TSet<FString> Definitions;
		for (const FString& Id : Ids)
		{
			Definitions.Add(Id);
		}
		return Definitions;
	}

	bool HasIntent(
		const TArray<SpiritsRules::FAchievementUnlockRequest>& Intents,
		const FString& OwnerId,
		const FString& AchievementId)
	{
		for (const SpiritsRules::FAchievementUnlockRequest& Intent : Intents)
		{
			if (Intent.OwnerId == OwnerId && Intent.AchievementId == AchievementId)
			{
				return true;
			}
		}
		return false;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsAchievementPropertyAutomationTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 5: Achievement definition, event semantics, ownership, and deduplication, 128 generated iterations",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsAchievementPropertyAutomationTest::RunTest(const FString& Parameters)
{
	constexpr int32 Iterations = 128;
	const TArray<FString> Owners = { TEXT("user_0"), TEXT("user_1"), TEXT("user_2"), TEXT("user_3") };
	const TArray<FString> ExpectedExactIds =
	{
		TEXT("ACH_FIRST_WIN"),
		TEXT("ACH_WIN_EASY"),
		TEXT("ACH_WIN_NORMAL"),
		TEXT("ACH_WIN_HARD"),
		TEXT("ACH_POSSESS_KILL_50"),
		TEXT("ACH_SUMMON_100"),
		TEXT("ACH_WIN_ALL_CIVS"),
		TEXT("ACH_LAN_WIN")
	};
	const TArray<FString>& ExactIds = ExpectedExactIds;
	const TArray<FString>& RegisteredIds = SpiritsRules::GetAchievementIds();
	bool bAllPassed = RegisteredIds.Num() == ExpectedExactIds.Num();
	if (!bAllPassed)
	{
		AddError(FString::Printf(TEXT("registered achievement ID count=%d expected=%d"), RegisteredIds.Num(), ExpectedExactIds.Num()));
	}
	for (int32 Index = 0; Index < ExpectedExactIds.Num(); ++Index)
	{
		if (!RegisteredIds.IsValidIndex(Index) || RegisteredIds[Index] != ExpectedExactIds[Index])
		{
			AddError(FString::Printf(TEXT("registered achievement ID mismatch at index=%d"), Index));
			bAllPassed = false;
		}
	}

	for (int32 Iteration = 0; Iteration < Iterations; ++Iteration)
	{
		const int32 Seed = 0x5A170000 + Iteration * 7919;
		FRandomStream Random(Seed);
		FFakeAchievementBackend Backend;
		const TSet<FString> Definitions = AllDefinitions(ExactIds);

		FFakeUser ReadyUser;
		ReadyUser.bIdentityAvailable = true;
		ReadyUser.bQuerySucceeds = true;
		ReadyUser.Definitions = Definitions;
		Backend.Users.Add(Owners[0], ReadyUser);

		FFakeUser IdentityFailure;
		IdentityFailure.bIdentityAvailable = false;
		IdentityFailure.bQuerySucceeds = true;
		IdentityFailure.Definitions = Definitions;
		Backend.Users.Add(Owners[1], IdentityFailure);

		FFakeUser QueryFailure;
		QueryFailure.bIdentityAvailable = true;
		QueryFailure.bQuerySucceeds = false;
		QueryFailure.Definitions = Definitions;
		Backend.Users.Add(Owners[2], QueryFailure);

		FFakeUser DefinitionMutation;
		DefinitionMutation.bIdentityAvailable = true;
		DefinitionMutation.bQuerySucceeds = true;
		DefinitionMutation.Definitions = Definitions;
		const FString MissingDefinition = ExactIds[Random.RandRange(0, ExactIds.Num() - 1)];
		DefinitionMutation.Definitions.Remove(MissingDefinition);
		Backend.Users.Add(Owners[3], DefinitionMutation);

		TArray<SpiritsRules::FAchievementEvent> Events;
		// Generated boundary prefix guarantees that every threshold is exercised;
		// the randomized suffix below still covers arbitrary bounded sequences.
		for (int32 Index = 0; Index < 50; ++Index)
		{
			AddCountEvent(Events, SpiritsRules::EAchievementEventType::PossessionKill, Owners[0]);
		}
		for (int32 Index = 0; Index < 100; ++Index)
		{
			AddCountEvent(Events, SpiritsRules::EAchievementEventType::Summon, Owners[0]);
		}
		for (int32 Civilization = 0; Civilization < 4; ++Civilization)
		{
			AddWin(Events, Owners[0], Civilization - 2, Civilization, false);
		}
		AddWin(Events, Owners[0], 1, 0, true);
		AddWin(Events, Owners[1], 1, 0, false);
		AddWin(Events, Owners[2], 1, 0, false);
		{
			SpiritsRules::FAchievementEvent UnknownEvent;
			UnknownEvent.Type = SpiritsRules::EAchievementEventType::Unlock;
			UnknownEvent.OwnerId = Owners[2];
			UnknownEvent.AchievementId = TEXT("ACH_NOT_REGISTERED");
			Events.Add(UnknownEvent);
		}
		{
			SpiritsRules::FAchievementEvent MissingDefinitionEvent;
			MissingDefinitionEvent.Type = SpiritsRules::EAchievementEventType::Unlock;
			MissingDefinitionEvent.OwnerId = Owners[3];
			MissingDefinitionEvent.AchievementId = MissingDefinition;
			Events.Add(MissingDefinitionEvent);
		}

		const int32 EventCount = Random.RandRange(80, 240);
		for (int32 Index = 0; Index < EventCount; ++Index)
		{
			const int32 OwnerIndex = Random.RandRange(0, Owners.Num() - 1);
			const int32 EventKind = Random.RandRange(0, 16);
			if (EventKind <= 6)
			{
				AddWin(
					Events,
					Owners[OwnerIndex],
					Random.RandRange(-4, 6),
					Random.RandRange(-4, 7),
					Random.RandBool());
			}
			else if (EventKind <= 11)
			{
				AddCountEvent(Events, SpiritsRules::EAchievementEventType::PossessionKill, Owners[OwnerIndex]);
			}
			else if (EventKind <= 14)
			{
				AddCountEvent(Events, SpiritsRules::EAchievementEventType::Summon, Owners[OwnerIndex]);
			}
			else
			{
				SpiritsRules::FAchievementEvent Event;
				Event.Type = SpiritsRules::EAchievementEventType::Unlock;
				Event.OwnerId = Owners[OwnerIndex];
				Event.AchievementId = (Index % 2 == 0) ? ExactIds[Random.RandRange(0, ExactIds.Num() - 1)] : TEXT("ACH_NOT_REGISTERED");
				Events.Add(Event);
			}
		}

		SpiritsRules::FAchievementEventRouter Router(Backend);
		TMap<FString, TSet<FString>> ExpectedIntents;
		TMap<FString, int32> KillCounts;
		TMap<FString, int32> SummonCounts;
		TMap<FString, uint8> CivMasks;
		TSet<FString> ExpectedFallbackUsers;
		bool bUnknownEventGenerated = false;

		for (const SpiritsRules::FAchievementEvent& Event : Events)
		{
			Router.ProcessEvent(Event);
			if (Event.OwnerId == Owners[1] || Event.OwnerId == Owners[2])
			{
				ExpectedFallbackUsers.Add(Event.OwnerId);
			}

			TSet<FString>& UserIntents = ExpectedIntents.FindOrAdd(Event.OwnerId);
			switch (Event.Type)
			{
			case SpiritsRules::EAchievementEventType::Win:
				UserIntents.Add(SpiritsRules::AchievementIds::FirstWin);
				switch (FMath::Clamp(Event.Difficulty, 0, 2))
				{
				case 0: UserIntents.Add(SpiritsRules::AchievementIds::WinEasy); break;
				case 2: UserIntents.Add(SpiritsRules::AchievementIds::WinHard); break;
				default: UserIntents.Add(SpiritsRules::AchievementIds::WinNormal); break;
				}
				if (Event.bLan)
				{
					UserIntents.Add(SpiritsRules::AchievementIds::LanWin);
				}
				CivMasks.FindOrAdd(Event.OwnerId) |= static_cast<uint8>(1u << FMath::Clamp(Event.Civilization, 0, 3));
				if (CivMasks[Event.OwnerId] == 0x0F)
				{
					UserIntents.Add(SpiritsRules::AchievementIds::WinAllCivilizations);
				}
				break;
			case SpiritsRules::EAchievementEventType::PossessionKill:
				if (++KillCounts.FindOrAdd(Event.OwnerId) == 50)
				{
					UserIntents.Add(SpiritsRules::AchievementIds::PossessKill50);
				}
				break;
			case SpiritsRules::EAchievementEventType::Summon:
				if (++SummonCounts.FindOrAdd(Event.OwnerId) == 100)
				{
					UserIntents.Add(SpiritsRules::AchievementIds::Summon100);
				}
				break;
			case SpiritsRules::EAchievementEventType::Unlock:
				if (ExactIds.Contains(Event.AchievementId))
				{
					UserIntents.Add(Event.AchievementId);
				}
				else
				{
					bUnknownEventGenerated = true;
				}
				break;
			}
		}

		for (const FString& OwnerId : Owners)
		{
			const TSet<FString>* Expected = ExpectedIntents.Find(OwnerId);
			if (Expected == nullptr)
			{
				continue;
			}
			for (const FString& ExpectedId : *Expected)
			{
				if (!HasIntent(Router.GetUnlockIntents(), OwnerId, ExpectedId))
				{
					AddError(FString::Printf(TEXT("seed=%d owner=%s missing intent=%s"), Seed, *OwnerId, *ExpectedId));
					bAllPassed = false;
				}
			}
		}

		for (const SpiritsRules::FAchievementUnlockRequest& Intent : Router.GetUnlockIntents())
		{
			if (!ExactIds.Contains(Intent.AchievementId))
			{
				AddError(FString::Printf(TEXT("seed=%d emitted non-canonical ID=%s"), Seed, *Intent.AchievementId));
				bAllPassed = false;
			}
		}

		TMap<FString, int32> IntentCounts;
		for (const SpiritsRules::FAchievementUnlockRequest& Intent : Router.GetUnlockIntents())
		{
			const FString Key = Intent.OwnerId + TEXT("\n") + Intent.AchievementId;
			if (++IntentCounts.FindOrAdd(Key) > 1)
			{
				AddError(FString::Printf(TEXT("seed=%d duplicate intent=%s owner=%s"), Seed, *Intent.AchievementId, *Intent.OwnerId));
				bAllPassed = false;
			}
		}

		TMap<FString, int32> WriteCounts;
		for (const SpiritsRules::FAchievementUnlockRequest& Write : Backend.Writes)
		{
			const FString Key = Write.OwnerId + TEXT("\n") + Write.AchievementId;
			if (++WriteCounts.FindOrAdd(Key) > 1 || !ExactIds.Contains(Write.AchievementId))
			{
				AddError(FString::Printf(TEXT("seed=%d duplicate/non-canonical write=%s owner=%s"), Seed, *Write.AchievementId, *Write.OwnerId));
				bAllPassed = false;
			}
			if (!HasIntent(Router.GetUnlockIntents(), Write.OwnerId, Write.AchievementId))
			{
				AddError(FString::Printf(TEXT("seed=%d write without owning intent=%s owner=%s"), Seed, *Write.AchievementId, *Write.OwnerId));
				bAllPassed = false;
			}
		}

		for (const FString& OwnerId : { Owners[1], Owners[2] })
		{
			for (const SpiritsRules::FAchievementUnlockRequest& Write : Backend.Writes)
			{
				if (Write.OwnerId == OwnerId)
				{
					AddError(FString::Printf(TEXT("seed=%d unavailable owner produced Steam write=%s owner=%s"), Seed, *Write.AchievementId, *OwnerId));
					bAllPassed = false;
				}
			}
		}

		for (int32 WriteIndex = 0; WriteIndex < Backend.Operations.Num(); ++WriteIndex)
		{
			if (!Backend.Operations[WriteIndex].StartsWith(TEXT("W:")))
			{
				continue;
			}
			const int32 LastSeparator = Backend.Operations[WriteIndex].Find(TEXT(":"), ESearchCase::CaseSensitive, ESearchDir::FromEnd, INDEX_NONE);
			const FString OwnerId = Backend.Operations[WriteIndex].Mid(2, LastSeparator - 2);
			bool bQuerySeen = false;
			for (int32 QueryIndex = 0; QueryIndex < WriteIndex; ++QueryIndex)
			{
				if (Backend.Operations[QueryIndex] == FString::Printf(TEXT("Q:%s"), *OwnerId))
				{
					bQuerySeen = true;
					break;
				}
			}
			if (!bQuerySeen)
			{
				AddError(FString::Printf(TEXT("seed=%d write occurred before definition query: %s"), Seed, *Backend.Operations[WriteIndex]));
				bAllPassed = false;
			}
		}

		for (const SpiritsRules::FAchievementUnlockRequest& Write : Backend.Writes)
		{
			if (Write.OwnerId == Owners[3] && Write.AchievementId == MissingDefinition)
			{
				AddError(FString::Printf(TEXT("seed=%d missing definition produced a Steam write=%s"), Seed, *MissingDefinition));
				bAllPassed = false;
			}
		}

		if (bUnknownEventGenerated && Backend.Writes.ContainsByPredicate([](const SpiritsRules::FAchievementUnlockRequest& Write)
		{
			return Write.AchievementId == TEXT("ACH_NOT_REGISTERED");
		}))
		{
			AddError(FString::Printf(TEXT("seed=%d unknown achievement produced a Steam write"), Seed));
			bAllPassed = false;
		}
		for (const FString& OwnerId : ExpectedFallbackUsers)
		{
			if (!Backend.FallbackRecords.ContainsByPredicate([&OwnerId](const SpiritsRules::FAchievementLocalRecord& Record)
			{
				return Record.OwnerId == OwnerId && Record.bFallback;
			}))
			{
				AddError(FString::Printf(TEXT("seed=%d fallback record missing for owner=%s"), Seed, *OwnerId));
				bAllPassed = false;
			}
		}

		for (const SpiritsRules::FAchievementUnlockRequest& Write : Backend.Writes)
		{
			if (Write.OwnerId == TEXT("server"))
			{
				AddError(FString::Printf(TEXT("seed=%d LAN/event write routed to server identity"), Seed));
				bAllPassed = false;
			}
		}
	}

	return bAllPassed;
}
#endif
