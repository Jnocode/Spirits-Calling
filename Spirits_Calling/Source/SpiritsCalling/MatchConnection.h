#pragma once

#include "CoreMinimal.h"

/**
 * World- and transport-independent LAN connection lifecycle used by the shared
 * player controller and by automation. The controller maps engine network and
 * travel failure enums onto this pure model so that a failed Join IP or a mid
 * match disconnect always produces a stable, machine-readable code instead of a
 * silent or falsely "connected" state.
 *
 * Scope note: this models the honest shipped surface only (PC single-player and
 * LAN/friend listen-server connections). It deliberately has no matchmaking,
 * dedicated-server or authentication state.
 */
namespace SpiritsNet
{
	/** Stable, machine-readable connection codes referenced by tests and smoke evidence. */
	inline const TCHAR* const JoinFailedCode = TEXT("Match.JoinFailed");
	inline const TCHAR* const DisconnectedCode = TEXT("Match.Disconnected");

	enum class EConnectionPhase : uint8
	{
		/** No join attempt in flight; host stays operable and the menu is usable. */
		Idle,
		/** A Join IP attempt has been issued and is awaiting the client world. */
		Joining,
		/** The joining client reached a networked client world. */
		Connected,
		/** The most recent join attempt failed; the local peer stays operable. */
		Failed
	};

	/**
	 * Local connection tracker. It never claims a connected Match unless a join
	 * attempt actually reached a client world, and both failure paths clear the
	 * connected flag so callers cannot misreport liveness.
	 */
	class FMatchConnectionModel
	{
	public:
		/** A joining client issued ClientTravel; no Match is connected yet. */
		void BeginJoinAttempt()
		{
			Phase = EConnectionPhase::Joining;
			bMatchConnected = false;
			LastErrorCode.Reset();
		}

		/** The joining client's controller reached a networked client world. */
		void MarkConnected()
		{
			Phase = EConnectionPhase::Connected;
			bMatchConnected = true;
			LastErrorCode.Reset();
		}

		/**
		 * A travel or network failure occurred before/at connection. The local
		 * peer (host or would-be joiner) stays operable and can retry; no Match
		 * is reported as connected.
		 */
		void HandleJoinFailure()
		{
			Phase = EConnectionPhase::Failed;
			bMatchConnected = false;
			LastErrorCode = JoinFailedCode;
		}

		/**
		 * An established connection dropped. The remaining peer returns to an
		 * operable idle state and records the disconnect; it is not frozen and
		 * does not keep a stale connected flag.
		 */
		void HandleDisconnect()
		{
			Phase = EConnectionPhase::Idle;
			bMatchConnected = false;
			LastErrorCode = DisconnectedCode;
		}

		/** Clears transient error state without asserting a connected Match. */
		void Reset()
		{
			Phase = EConnectionPhase::Idle;
			bMatchConnected = false;
			LastErrorCode.Reset();
		}

		bool IsMatchConnected() const { return bMatchConnected; }
		EConnectionPhase GetPhase() const { return Phase; }
		const FString& GetLastErrorCode() const { return LastErrorCode; }
		bool HasError() const { return !LastErrorCode.IsEmpty(); }

	private:
		EConnectionPhase Phase = EConnectionPhase::Idle;
		bool bMatchConnected = false;
		FString LastErrorCode;
	};
}
