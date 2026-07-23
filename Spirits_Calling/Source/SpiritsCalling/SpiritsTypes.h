#pragma once

#include "CoreMinimal.h"
#include "SpiritsTypes.generated.h"

/** Match flow phases, replicated via GameState. */
UENUM(BlueprintType)
enum class ESpiritsMatchPhase : uint8
{
	WaitingToStart,
	InProgress,
	Ended
};

/**
 * A summonable minion archetype. Defined in C++ defaults (see ASpiritsGameMode)
 * so the game is fully playable without editor-created Data Assets.
 * Can later be overridden/extended with UPDA_MinionData assets.
 */
USTRUCT(BlueprintType)
struct FMinionArchetype
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	FString DisplayName = TEXT("Warrior");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float MaxHP = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float AttackDamage = 15.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float AttackRange = 200.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float AttackInterval = 1.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float MoveSpeed = 450.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	int32 SummonCost = 50;

	/** Per-archetype tint multiplied over team color. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	FLinearColor Tint = FLinearColor::White;

	/** Uniform mesh scale, visual variety between archetypes. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Minion")
	float MeshScale = 1.f;
};

/** Host-side difficulty chosen in the main menu: 0 = Easy, 1 = Normal, 2 = Hard. */
extern SPIRITSCALLING_API int32 GSpiritsDifficulty;

/**
 * The four playable civilizations. Each fields a distinct, intentionally
 * ASYMMETRIC trio of minion archetypes (see ASpiritsGameMode::BuildCivLoadout):
 *   East  — fragile, fast, high attack rate (swarm / mobility)
 *   Norse — high HP, heavy per-hit damage, slow (bruisers)
 *   Egypt — cheap summons, balanced stats (economy / numbers)
 *   Cyber — longest reach, highest damage, low HP (glass cannon / risk)
 */
UENUM(BlueprintType)
enum class ECivilization : uint8
{
	East  = 0,
	Norse = 1,
	Egypt = 2,
	Cyber = 3
};

/** Host-side civilization selection per team (set from the main menu; defaults give
 *  an asymmetric single-player match out of the box). */
extern SPIRITSCALLING_API int32 GSpiritsCivTeamA;
extern SPIRITSCALLING_API int32 GSpiritsCivTeamB;

/** Host-side battlefield selection: 0 = Void (night), 1 = Sands (day). Replicated
 *  to clients via GameState::MapIndex so every instance builds the same geometry. */
extern SPIRITSCALLING_API int32 GSpiritsMapIndex;
namespace SpiritsMaps { constexpr int32 Num = 2; }

namespace SpiritsCiv
{
	constexpr int32 Num = 4;

	inline int32 Clamp(int32 Civ) { return FMath::Clamp(Civ, 0, Num - 1); }

	inline const TCHAR* GetName(int32 Civ)
	{
		switch (Clamp(Civ))
		{
		case 0:  return TEXT("East");
		case 1:  return TEXT("Norse");
		case 2:  return TEXT("Egypt");
		default: return TEXT("Cyber");
		}
	}

	/** Mild hue skew multiplied over the per-archetype tint; kept close to white so
	 *  the blue/red TEAM color still reads clearly in LAN. */
	inline FLinearColor GetHue(int32 Civ)
	{
		switch (Clamp(Civ))
		{
		case 0:  return FLinearColor(0.70f, 1.10f, 1.00f); // jade
		case 1:  return FLinearColor(1.10f, 0.85f, 0.70f); // bronze
		case 2:  return FLinearColor(1.15f, 1.00f, 0.60f); // gold
		default: return FLinearColor(1.00f, 0.80f, 1.20f); // violet
		}
	}
}

namespace SpiritsTeams
{
	constexpr uint8 TeamA = 0;
	constexpr uint8 TeamB = 1;
	constexpr uint8 NoTeam = 255;

	inline FLinearColor GetTeamColor(uint8 TeamId)
	{
		switch (TeamId)
		{
		case TeamA: return FLinearColor(0.1f, 0.35f, 1.f);   // blue
		case TeamB: return FLinearColor(1.f, 0.15f, 0.1f);   // red
		default:    return FLinearColor(0.5f, 0.5f, 0.5f);
		}
	}
}
