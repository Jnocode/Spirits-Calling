#pragma once

#include "CoreMinimal.h"

/**
 * World- and hardware-independent platform input rules shared by runtime and
 * automation. This seam decides whether an input may reach a gameplay/UI
 * handler; authoritative gameplay mutations remain on ASpiritsPlayerController.
 */
namespace SpiritsPlatform
{
	inline constexpr double SnapTurnIntervalSeconds = 0.35;

	enum class EPlatformMode : uint8
	{
		PC,
		PCVR
	};

	enum class EPlatformAction : uint8
	{
		Movement,
		View,
		SummonSelection,
		Summon,
		Possession,
		LightAttack,
		HeavyAttack,
		ReturnFromPossession,
		SnapTurn,
		MenuToggle,
		MenuHover,
		MenuClick,
		MenuRelease,
		Restart
	};

	enum class EShippedCapability : uint8
	{
		PCSinglePlayer,
		LanFriendConnection,
		PCVR,
		PublicMatchmaking,
		DedicatedServer,
		NakamaAuthentication,
		AntiCheat
	};

	/** Selects VR only when an XR system exists and currently permits head tracking. */
	constexpr EPlatformMode SelectPlatformMode(bool bXRSystemAvailable, bool bHeadTrackingAllowed)
	{
		return bXRSystemAvailable && bHeadTrackingAllowed ? EPlatformMode::PCVR : EPlatformMode::PC;
	}

	/** Executable release-scope declaration. Unsupported capabilities must stay false. */
	constexpr bool IsShippedCapability(EShippedCapability Capability)
	{
		switch (Capability)
		{
		case EShippedCapability::PCSinglePlayer:
		case EShippedCapability::LanFriendConnection:
		case EShippedCapability::PCVR:
			return true;
		default:
			return false;
		}
	}

	constexpr bool IsGameplayAction(EPlatformAction Action)
	{
		return Action >= EPlatformAction::Movement && Action <= EPlatformAction::SnapTurn;
	}

	/** Local dispatch gate. Opening a menu blocks all gameplay handler dispatch. */
	class FPlatformActionRouter
	{
	public:
		void SetMenuOpen(bool bOpen) { bMenuOpen = bOpen; }
		bool IsMenuOpen() const { return bMenuOpen; }

		bool CanDispatch(EPlatformAction Action) const
		{
			if (IsGameplayAction(Action))
			{
				return !bMenuOpen;
			}

			switch (Action)
			{
			case EPlatformAction::MenuHover:
			case EPlatformAction::MenuClick:
			case EPlatformAction::MenuRelease:
				return bMenuOpen;
			case EPlatformAction::MenuToggle:
			case EPlatformAction::Restart:
				return true;
			default:
				return false;
			}
		}

	private:
		bool bMenuOpen = false;
	};

	/** Monotonic timestamp gate; rejected samples never advance the accepted time. */
	class FComfortTurnGate
	{
	public:
		bool TryAccept(double TimestampSeconds)
		{
			if (!FMath::IsFinite(TimestampSeconds))
			{
				return false;
			}
			if (bHasAcceptedTurn && TimestampSeconds < LastAcceptedTimestamp + SnapTurnIntervalSeconds)
			{
				return false;
			}

			LastAcceptedTimestamp = TimestampSeconds;
			bHasAcceptedTurn = true;
			return true;
		}

		void Reset()
		{
			LastAcceptedTimestamp = 0.0;
			bHasAcceptedTurn = false;
		}

		bool HasAcceptedTurn() const { return bHasAcceptedTurn; }
		double GetLastAcceptedTimestamp() const { return LastAcceptedTimestamp; }

	private:
		double LastAcceptedTimestamp = 0.0;
		bool bHasAcceptedTurn = false;
	};
}
