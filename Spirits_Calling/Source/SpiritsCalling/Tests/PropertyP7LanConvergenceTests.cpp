#include "SpiritsCalling/SpiritsRules.h"
#include "SpiritsCalling/SpiritsTypes.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

namespace
{
	constexpr int32 P7PropertyIterations = 256;
	constexpr int32 P7PropertySeed = 0xA7002026;

	enum class ECommandType : uint8
	{
		SelectSettings,
		StartMatch,
		Move,
		Menu,
		Summon,
		Possess,
		Combat,
		EndMatch
	};

	struct FMatchCommand
	{
		int32 ClientId = 0;
		ECommandType Type = ECommandType::Move;
		int32 Difficulty = 1;
		int32 MapIndex = 0;
		int32 TeamACivilization = 0;
		int32 TeamBCivilization = 1;
		int32 ArchetypeIndex = 0;
		int32 Sequence = 0;
	};

	FString CommandName(ECommandType Type)
	{
		switch (Type)
		{
		case ECommandType::SelectSettings: return TEXT("SelectSettings");
		case ECommandType::StartMatch: return TEXT("StartMatch");
		case ECommandType::Move: return TEXT("Move");
		case ECommandType::Menu: return TEXT("Menu");
		case ECommandType::Summon: return TEXT("Summon");
		case ECommandType::Possess: return TEXT("Possess");
		case ECommandType::Combat: return TEXT("Combat");
		case ECommandType::EndMatch: return TEXT("EndMatch");
		default: return TEXT("Unknown");
		}
	}

	struct FMatchSnapshot
	{
		TArray<uint8> TeamAssignments;
		int32 Difficulty = 1;
		int32 MapIndex = 0;
		FString MapStyle;
		FString GroundHook;
		FString SkyHook;
		int32 TeamACivilization = 0;
		int32 TeamBCivilization = 1;
		TArray<FMinionArchetype> TeamALoadout;
		TArray<FMinionArchetype> TeamBLoadout;
		ESpiritsMatchPhase Phase = ESpiritsMatchPhase::WaitingToStart;
		uint8 Winner = SpiritsTeams::NoTeam;
		bool bSummonAccepted = false;
		int32 SummonCount = 0;
		int32 LastSummonIndex = -1;
		uint8 LastSummonTeam = SpiritsTeams::NoTeam;
		bool bPossessionAccepted = false;
		int32 PossessingClient = -1;
		bool bCombatAccepted = false;
		int32 CombatEvents = 0;
		int32 MovementEvents = 0;
		int32 MenuEvents = 0;
	};

	bool ArchetypesEqual(const FMinionArchetype& Left, const FMinionArchetype& Right)
	{
		return Left.DisplayName == Right.DisplayName &&
			FMath::IsNearlyEqual(Left.MaxHP, Right.MaxHP) &&
			FMath::IsNearlyEqual(Left.AttackDamage, Right.AttackDamage) &&
			FMath::IsNearlyEqual(Left.AttackRange, Right.AttackRange) &&
			FMath::IsNearlyEqual(Left.AttackInterval, Right.AttackInterval) &&
			FMath::IsNearlyEqual(Left.MoveSpeed, Right.MoveSpeed) &&
			Left.SummonCost == Right.SummonCost &&
			Left.Tint.Equals(Right.Tint) &&
			FMath::IsNearlyEqual(Left.MeshScale, Right.MeshScale);
	}

	bool ArchetypeArraysEqual(const TArray<FMinionArchetype>& Left, const TArray<FMinionArchetype>& Right)
	{
		if (Left.Num() != Right.Num())
		{
			return false;
		}
		for (int32 Index = 0; Index < Left.Num(); ++Index)
		{
			if (!ArchetypesEqual(Left[Index], Right[Index]))
			{
				return false;
			}
		}
		return true;
	}

	bool SnapshotsEqual(const FMatchSnapshot& Left, const FMatchSnapshot& Right)
	{
		return Left.TeamAssignments == Right.TeamAssignments &&
			Left.Difficulty == Right.Difficulty &&
			Left.MapIndex == Right.MapIndex &&
			Left.MapStyle == Right.MapStyle &&
			Left.GroundHook == Right.GroundHook &&
			Left.SkyHook == Right.SkyHook &&
			Left.TeamACivilization == Right.TeamACivilization &&
			Left.TeamBCivilization == Right.TeamBCivilization &&
			ArchetypeArraysEqual(Left.TeamALoadout, Right.TeamALoadout) &&
			ArchetypeArraysEqual(Left.TeamBLoadout, Right.TeamBLoadout) &&
			Left.Phase == Right.Phase &&
			Left.Winner == Right.Winner &&
			Left.bSummonAccepted == Right.bSummonAccepted &&
			Left.SummonCount == Right.SummonCount &&
			Left.LastSummonIndex == Right.LastSummonIndex &&
			Left.LastSummonTeam == Right.LastSummonTeam &&
			Left.bPossessionAccepted == Right.bPossessionAccepted &&
			Left.PossessingClient == Right.PossessingClient &&
			Left.bCombatAccepted == Right.bCombatAccepted &&
			Left.CombatEvents == Right.CombatEvents &&
			Left.MovementEvents == Right.MovementEvents &&
			Left.MenuEvents == Right.MenuEvents;
	}

	FString DescribeSnapshot(const FMatchSnapshot& Snapshot)
	{
		return FString::Printf(
			TEXT("team=[%d,%d] difficulty=%d map=%d/%s civ=[%d,%d] loadout=[%d,%d] phase=%d winner=%d summon=%s/%d/%d possession=%s/%d combat=%s/%d movement=%d menu=%d"),
			Snapshot.TeamAssignments.IsValidIndex(0) ? Snapshot.TeamAssignments[0] : 255,
			Snapshot.TeamAssignments.IsValidIndex(1) ? Snapshot.TeamAssignments[1] : 255,
			Snapshot.Difficulty,
			Snapshot.MapIndex,
			*Snapshot.MapStyle,
			Snapshot.TeamACivilization,
			Snapshot.TeamBCivilization,
			Snapshot.TeamALoadout.Num(),
			Snapshot.TeamBLoadout.Num(),
			static_cast<int32>(Snapshot.Phase),
			Snapshot.Winner,
			Snapshot.bSummonAccepted ? TEXT("accepted") : TEXT("none"),
			Snapshot.SummonCount,
			Snapshot.LastSummonIndex,
			Snapshot.bPossessionAccepted ? TEXT("accepted") : TEXT("none"),
			Snapshot.PossessingClient,
			Snapshot.bCombatAccepted ? TEXT("accepted") : TEXT("none"),
			Snapshot.CombatEvents,
			Snapshot.MovementEvents,
			Snapshot.MenuEvents);
	}

	struct FPendingCommand
	{
		int32 DeliveryTick = 0;
		FMatchCommand Command;
	};

	struct FPendingSnapshot
	{
		int32 DeliveryTick = 0;
		int32 Revision = 0;
		int32 ClientId = 0;
		FMatchSnapshot Snapshot;
	};

	/**
	 * Test-only network seam. Commands are deliberately non-authoritative: they
	 * are requests queued with delay and tie-order reversal. Only HostSnapshot is
	 * mutated by ApplyCommand; clients only accept replicated snapshots.
	 */
	class FReplicatedMatchModel
	{
	public:
		explicit FReplicatedMatchModel(FRandomStream& InRandom)
			: Random(InRandom)
		{
			HostSnapshot.TeamAssignments = { SpiritsTeams::TeamA, SpiritsTeams::TeamB };
			HostSnapshot.TeamALoadout = SpiritsRules::BuildCivLoadout(ECivilization::East);
			HostSnapshot.TeamBLoadout = SpiritsRules::BuildCivLoadout(ECivilization::Norse);
			RefreshMapHooks(HostSnapshot);
			ClientSnapshots.SetNum(2);
			ClientSnapshots[0] = HostSnapshot;
			bConnected[0] = true;
			EventLog.Add(TEXT("host-created client=0 connected=true"));
		}

		void ApplyJoinAttempt(bool bJoinSucceeded)
		{
			bHostOperable = true;
			if (bJoinSucceeded)
			{
				bConnected[1] = true;
				bMatchConnected = true;
				ClientSnapshots[1] = HostSnapshot;
				ClientRevisions[1] = Revision;
				EventLog.Add(TEXT("join success client=1 connected=true"));
				QueueSnapshotFor(1);
				return;
			}

			bConnected[1] = false;
			bMatchConnected = false;
			LastError = TEXT("Match.JoinFailed");
			EventLog.Add(TEXT("join failure code=Match.JoinFailed connected=false"));
		}

		bool SubmitCommand(const FMatchCommand& Command, int32 Delay)
		{
			if (!IsClientConnected(Command.ClientId))
			{
				EventLog.Add(FString::Printf(TEXT("ignored client=%d command=%s reason=disconnected"),
					Command.ClientId, *CommandName(Command.Type)));
				return false;
			}

			FPendingCommand Pending;
			Pending.DeliveryTick = CurrentTick + FMath::Max(0, Delay);
			Pending.Command = Command;
			PendingCommands.Add(Pending);
			EventLog.Add(FString::Printf(TEXT("queued tick=%d client=%d command=%s seq=%d"),
				Pending.DeliveryTick, Command.ClientId, *CommandName(Command.Type), Command.Sequence));
			return true;
		}

		void DrainUntilStable()
		{
			while (PendingCommands.Num() > 0 || PendingSnapshots.Num() > 0)
			{
				int32 NextTick = MAX_int32;
				for (const FPendingCommand& Pending : PendingCommands)
				{
					NextTick = FMath::Min(NextTick, Pending.DeliveryTick);
				}
				for (const FPendingSnapshot& Pending : PendingSnapshots)
				{
					NextTick = FMath::Min(NextTick, Pending.DeliveryTick);
				}
				CurrentTick = FMath::Max(CurrentTick, NextTick);

				PendingCommands.Sort([](const FPendingCommand& Left, const FPendingCommand& Right)
				{
					if (Left.DeliveryTick != Right.DeliveryTick)
					{
						return Left.DeliveryTick < Right.DeliveryTick;
					}
					// Reverse same-tick order to exercise command reordering.
					return Left.Command.Sequence > Right.Command.Sequence;
				});

				for (int32 Index = PendingCommands.Num() - 1; Index >= 0; --Index)
				{
					if (PendingCommands[Index].DeliveryTick > CurrentTick)
					{
						continue;
					}
					const FMatchCommand Command = PendingCommands[Index].Command;
					PendingCommands.RemoveAt(Index);
					if (!IsClientConnected(Command.ClientId))
					{
						EventLog.Add(FString::Printf(TEXT("dropped client=%d command=%s reason=disconnected-before-delivery"),
							Command.ClientId, *CommandName(Command.Type)));
						continue;
					}
					const bool bAccepted = ApplyCommand(Command);
					EventLog.Add(FString::Printf(TEXT("delivered tick=%d client=%d command=%s accepted=%s revision=%d"),
						CurrentTick, Command.ClientId, *CommandName(Command.Type),
						bAccepted ? TEXT("true") : TEXT("false"), Revision));
				}

				PendingSnapshots.Sort([](const FPendingSnapshot& Left, const FPendingSnapshot& Right)
				{
					if (Left.DeliveryTick != Right.DeliveryTick)
					{
						return Left.DeliveryTick < Right.DeliveryTick;
					}
					// Reverse same-tick packet order; stale revisions must be harmless.
					return Left.Revision > Right.Revision;
				});

				for (int32 Index = PendingSnapshots.Num() - 1; Index >= 0; --Index)
				{
					if (PendingSnapshots[Index].DeliveryTick > CurrentTick)
					{
						continue;
					}
					const FPendingSnapshot Pending = PendingSnapshots[Index];
					PendingSnapshots.RemoveAt(Index);
					if (!IsClientConnected(Pending.ClientId))
					{
						continue;
					}
					if (Pending.Revision >= ClientRevisions[Pending.ClientId])
					{
						ClientSnapshots[Pending.ClientId] = Pending.Snapshot;
						ClientRevisions[Pending.ClientId] = Pending.Revision;
					}
				}
			}
		}

		void DisconnectClient(int32 ClientId)
		{
			if (ClientId <= 0 || ClientId >= 2 || !bConnected[ClientId])
			{
				return;
			}
			bConnected[ClientId] = false;
			bMatchConnected = false;
			LastError = TEXT("Match.Disconnected");
			EventLog.Add(FString::Printf(TEXT("disconnect client=%d code=Match.Disconnected"), ClientId));
		}

		bool AreConnectedClientsConverged() const
		{
			for (int32 ClientId = 0; ClientId < 2; ++ClientId)
			{
				if (bConnected[ClientId] && !SnapshotsEqual(HostSnapshot, ClientSnapshots[ClientId]))
				{
					return false;
				}
			}
			return true;
		}

		bool IsClientConnected(int32 ClientId) const
		{
			return ClientId >= 0 && ClientId < 2 && bConnected[ClientId];
		}

		bool IsHostOperable() const { return bHostOperable; }
		bool IsMatchConnected() const { return bMatchConnected; }
		bool HasJoiner() const { return bConnected[1]; }
		const FMatchSnapshot& Host() const { return HostSnapshot; }
		const FMatchSnapshot& Client(int32 ClientId) const { return ClientSnapshots[ClientId]; }
		const FString& LastCommand() const { return EventLog.Num() > 0 ? EventLog.Last() : LastError; }
		FString DescribeLog() const
		{
			FString Result;
			const int32 First = FMath::Max(0, EventLog.Num() - 12);
			for (int32 Index = First; Index < EventLog.Num(); ++Index)
			{
				if (!Result.IsEmpty())
				{
					Result += TEXT(" | ");
				}
				Result += EventLog[Index];
			}
			return Result;
		}

	private:
		void RefreshMapHooks(FMatchSnapshot& Snapshot) const
		{
			const SpiritsRules::FMapStyleHooks Hooks = SpiritsRules::ResolveMapStyle(Snapshot.MapIndex);
			Snapshot.MapStyle = Hooks.Style;
			Snapshot.GroundHook = Hooks.GroundHook;
			Snapshot.SkyHook = Hooks.SkyHook;
		}

		void PublishLoadouts()
		{
			HostSnapshot.TeamALoadout = SpiritsRules::BuildCivLoadout(static_cast<ECivilization>(SpiritsCiv::Clamp(HostSnapshot.TeamACivilization)));
			HostSnapshot.TeamBLoadout = SpiritsRules::BuildCivLoadout(static_cast<ECivilization>(SpiritsCiv::Clamp(HostSnapshot.TeamBCivilization)));
		}

		void QueueSnapshotFor(int32 ClientId)
		{
			if (!IsClientConnected(ClientId))
			{
				return;
			}
			FPendingSnapshot Pending;
			Pending.DeliveryTick = CurrentTick + Random.RandRange(0, 3);
			Pending.Revision = Revision;
			Pending.ClientId = ClientId;
			Pending.Snapshot = HostSnapshot;
			PendingSnapshots.Add(Pending);
		}

		void ReplicateAuthoritativeSnapshot()
		{
			for (int32 ClientId = 0; ClientId < 2; ++ClientId)
			{
				QueueSnapshotFor(ClientId);
			}
		}

		bool ApplyCommand(const FMatchCommand& Command)
		{
			bool bChanged = false;
			switch (Command.Type)
			{
			case ECommandType::SelectSettings:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::WaitingToStart)
				{
					HostSnapshot.Difficulty = FMath::Clamp(Command.Difficulty, SpiritsRules::MinDifficulty, SpiritsRules::MaxDifficulty);
					HostSnapshot.MapIndex = SpiritsRules::NormalizeMapIndex(Command.MapIndex);
					HostSnapshot.TeamACivilization = SpiritsCiv::Clamp(Command.TeamACivilization);
					HostSnapshot.TeamBCivilization = SpiritsCiv::Clamp(Command.TeamBCivilization);
					RefreshMapHooks(HostSnapshot);
					PublishLoadouts();
					bChanged = true;
				}
				break;
			case ECommandType::StartMatch:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::WaitingToStart)
				{
					HostSnapshot.Phase = ESpiritsMatchPhase::InProgress;
					bChanged = true;
				}
				break;
			case ECommandType::Move:
				if (HostSnapshot.Phase != ESpiritsMatchPhase::Ended)
				{
					++HostSnapshot.MovementEvents;
					bChanged = true;
				}
				break;
			case ECommandType::Menu:
				++HostSnapshot.MenuEvents;
				bChanged = true;
				break;
			case ECommandType::Summon:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::InProgress && Command.ArchetypeIndex >= 0 && Command.ArchetypeIndex < 3)
				{
					HostSnapshot.bSummonAccepted = true;
					++HostSnapshot.SummonCount;
					HostSnapshot.LastSummonIndex = Command.ArchetypeIndex;
					HostSnapshot.LastSummonTeam = HostSnapshot.TeamAssignments[Command.ClientId];
					bChanged = true;
				}
				break;
			case ECommandType::Possess:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::InProgress && HostSnapshot.bSummonAccepted)
				{
					HostSnapshot.bPossessionAccepted = true;
					HostSnapshot.PossessingClient = Command.ClientId;
					bChanged = true;
				}
				break;
			case ECommandType::Combat:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::InProgress && HostSnapshot.bPossessionAccepted)
				{
					HostSnapshot.bCombatAccepted = true;
					++HostSnapshot.CombatEvents;
					bChanged = true;
				}
				break;
			case ECommandType::EndMatch:
				if (HostSnapshot.Phase == ESpiritsMatchPhase::InProgress)
				{
					HostSnapshot.Phase = ESpiritsMatchPhase::Ended;
					HostSnapshot.Winner = HostSnapshot.TeamAssignments[Command.ClientId] == SpiritsTeams::TeamA
						? SpiritsTeams::TeamB
						: SpiritsTeams::TeamA;
					bChanged = true;
				}
				break;
			default:
				break;
			}

			if (bChanged)
			{
				++Revision;
				ReplicateAuthoritativeSnapshot();
			}
			return bChanged;
		}

		FRandomStream& Random;
		FMatchSnapshot HostSnapshot;
		TArray<FMatchSnapshot> ClientSnapshots;
		int32 ClientRevisions[2] = { 0, 0 };
		bool bConnected[2] = { false, false };
		bool bHostOperable = true;
		bool bMatchConnected = false;
		int32 Revision = 0;
		int32 CurrentTick = 0;
		FString LastError;
		TArray<FPendingCommand> PendingCommands;
		TArray<FPendingSnapshot> PendingSnapshots;
		TArray<FString> EventLog;
	};

	FMatchCommand MakeCommand(int32 ClientId, ECommandType Type, int32 Sequence)
	{
		FMatchCommand Command;
		Command.ClientId = ClientId;
		Command.Type = Type;
		Command.Sequence = Sequence;
		return Command;
	}

	bool CheckStable(FAutomationTestBase& Test, const FReplicatedMatchModel& Model, int32 Iteration, int32 Seed, const TCHAR* Event)
	{
		if (Model.AreConnectedClientsConverged())
		{
			return true;
		}

		Test.AddError(FString::Printf(
			TEXT("P7 counterexample seed=%d iteration=%d event=%s lastCommand=%s host={%s} client0={%s} client1={%s} log=%s"),
			Seed,
			Iteration,
			Event,
			*Model.LastCommand(),
			*DescribeSnapshot(Model.Host()),
			*DescribeSnapshot(Model.Client(0)),
			*DescribeSnapshot(Model.Client(1)),
			*Model.DescribeLog()));
		return false;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FSpiritsPropertyP7LanConvergenceTest,
	"SpiritsCalling.Feature: spirits-calling-requirements, Property 7: LAN replicated match convergence and remaining-client liveness",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSpiritsPropertyP7LanConvergenceTest::RunTest(const FString& Parameters)
{
	FRandomStream Generator(P7PropertySeed);
	int32 SuccessfulJoins = 0;
	int32 FailedJoins = 0;
	int32 DisconnectCases = 0;

	for (int32 Iteration = 0; Iteration < P7PropertyIterations; ++Iteration)
	{
		FReplicatedMatchModel Model(Generator);
		const bool bJoinSucceeded = (Iteration % 3) != 0;
		Model.ApplyJoinAttempt(bJoinSucceeded);
		if (bJoinSucceeded)
		{
			++SuccessfulJoins;
		}
		else
		{
			++FailedJoins;
			TestTrue(FString::Printf(TEXT("seed=%d iteration=%d failed join keeps host operable"), P7PropertySeed, Iteration), Model.IsHostOperable());
			TestFalse(FString::Printf(TEXT("seed=%d iteration=%d failed join has no connected joiner"), P7PropertySeed, Iteration), Model.HasJoiner());
			TestFalse(FString::Printf(TEXT("seed=%d iteration=%d failed join does not establish Match"), P7PropertySeed, Iteration), Model.IsMatchConnected());
		}

		const int32 SettingsClient = bJoinSucceeded ? 1 : 0;
		FMatchCommand SettingsA = MakeCommand(SettingsClient, ECommandType::SelectSettings, Iteration * 10 + 1);
		SettingsA.Difficulty = Generator.RandRange(-2, 4);
		SettingsA.MapIndex = Generator.RandRange(-1000, 1000);
		SettingsA.TeamACivilization = Generator.RandRange(-2, 5);
		SettingsA.TeamBCivilization = Generator.RandRange(-2, 5);
		FMatchCommand SettingsB = SettingsA;
		SettingsB.ClientId = 0;
		SettingsB.Sequence++;
		SettingsB.Difficulty = Generator.RandRange(0, 2);
		SettingsB.MapIndex = Generator.RandRange(-2, 3);
		Model.SubmitCommand(SettingsA, Generator.RandRange(0, 3));
		Model.SubmitCommand(SettingsB, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("settings")))
		{
			return false;
		}

		FMatchCommand Start = MakeCommand(0, ECommandType::StartMatch, Iteration * 10 + 3);
		Model.SubmitCommand(Start, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("phase InProgress")))
		{
			return false;
		}
		if (Model.Host().Phase != ESpiritsMatchPhase::InProgress)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d command=StartMatch host phase=%d log=%s"),
				P7PropertySeed, Iteration, static_cast<int32>(Model.Host().Phase), *Model.DescribeLog()));
			return false;
		}

		const int32 DisconnectStep = Generator.RandRange(0, 3);
		bool bDisconnected = false;
		auto MaybeDisconnect = [&](int32 Step) -> bool
		{
			if (bJoinSucceeded && !bDisconnected && DisconnectStep == Step)
			{
				Model.DisconnectClient(1);
				bDisconnected = true;
				++DisconnectCases;
				if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("disconnect")))
				{
					return false;
				}
			}
			return true;
		};

		if (!MaybeDisconnect(0)) return false;

		FMatchCommand Summon = MakeCommand(0, ECommandType::Summon, Iteration * 10 + 4);
		Summon.ArchetypeIndex = Generator.RandRange(0, 2);
		Model.SubmitCommand(Summon, Generator.RandRange(0, 3));
		if (bJoinSucceeded && !bDisconnected)
		{
			FMatchCommand Move = MakeCommand(1, ECommandType::Move, Iteration * 10 + 5);
			FMatchCommand Menu = MakeCommand(1, ECommandType::Menu, Iteration * 10 + 6);
			Model.SubmitCommand(Move, Generator.RandRange(0, 3));
			Model.SubmitCommand(Menu, Generator.RandRange(0, 3));
		}
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("summon"))) return false;
		if (!Model.Host().bSummonAccepted)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d command=Summon was not accepted log=%s"),
				P7PropertySeed, Iteration, *Model.DescribeLog()));
			return false;
		}

		if (!MaybeDisconnect(1)) return false;
		FMatchCommand Possess = MakeCommand(0, ECommandType::Possess, Iteration * 10 + 7);
		Model.SubmitCommand(Possess, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("possession"))) return false;
		if (!Model.Host().bPossessionAccepted)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d command=Possess was not accepted log=%s"),
				P7PropertySeed, Iteration, *Model.DescribeLog()));
			return false;
		}

		if (!MaybeDisconnect(2)) return false;
		FMatchCommand Combat = MakeCommand(0, ECommandType::Combat, Iteration * 10 + 8);
		Model.SubmitCommand(Combat, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("combat"))) return false;
		if (!Model.Host().bCombatAccepted)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d command=Combat was not accepted log=%s"),
				P7PropertySeed, Iteration, *Model.DescribeLog()));
			return false;
		}

		if (!MaybeDisconnect(3)) return false;
		if (bDisconnected)
		{
			FMatchCommand DisconnectedInput = MakeCommand(1, ECommandType::Move, Iteration * 10 + 9);
			TestFalse(FString::Printf(TEXT("seed=%d iteration=%d disconnected client cannot submit input"), P7PropertySeed, Iteration),
				Model.SubmitCommand(DisconnectedInput, 0));
		}

		FMatchCommand RemainingMove = MakeCommand(0, ECommandType::Move, Iteration * 10 + 10);
		FMatchCommand RemainingMenu = MakeCommand(0, ECommandType::Menu, Iteration * 10 + 11);
		Model.SubmitCommand(RemainingMove, Generator.RandRange(0, 3));
		Model.SubmitCommand(RemainingMenu, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("remaining-client liveness"))) return false;
		if (Model.Host().MovementEvents < 1 || Model.Host().MenuEvents < 1)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d remaining client lost input movement=%d menu=%d log=%s"),
				P7PropertySeed, Iteration, Model.Host().MovementEvents, Model.Host().MenuEvents, *Model.DescribeLog()));
			return false;
		}

		FMatchCommand End = MakeCommand(0, ECommandType::EndMatch, Iteration * 10 + 12);
		Model.SubmitCommand(End, Generator.RandRange(0, 3));
		Model.DrainUntilStable();
		if (!CheckStable(*this, Model, Iteration, P7PropertySeed, TEXT("phase Ended/winner"))) return false;
		if (Model.Host().Phase != ESpiritsMatchPhase::Ended || Model.Host().Winner == SpiritsTeams::NoTeam)
		{
			AddError(FString::Printf(TEXT("P7 counterexample seed=%d iteration=%d command=EndMatch phase=%d winner=%d log=%s"),
				P7PropertySeed, Iteration, static_cast<int32>(Model.Host().Phase), Model.Host().Winner, *Model.DescribeLog()));
			return false;
		}
	}

	const int32 ExpectedFailedJoins = ((P7PropertyIterations - 1) / 3) + 1;
	const int32 ExpectedSuccessfulJoins = P7PropertyIterations - ExpectedFailedJoins;
	TestEqual(TEXT("generated successful Join IP cases"), SuccessfulJoins, ExpectedSuccessfulJoins);
	TestEqual(TEXT("generated failed Join IP cases"), FailedJoins, ExpectedFailedJoins);
	TestTrue(TEXT("generated optional disconnect cases"), DisconnectCases > 0);
	return true;
}
#endif
