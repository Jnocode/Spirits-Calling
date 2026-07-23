#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SpiritsTypes.h"
#include "PDA_MinionData.generated.h"

/**
 * Base Data Asset for Civilization Minions.
 * Optional: the game runs with C++ archetype defaults (ASpiritsGameMode::SummonOptions);
 * data assets of this class can be created in the editor to add civilization units
 * and assigned into the GameMode's SummonOptions later.
 */
UCLASS(BlueprintType, Blueprintable)
class SPIRITSCALLING_API UPDA_MinionData : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
	float MaxHP = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
	float BaseAttack = 10.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Identity")
	FString CivilizationName;

	/** Full combat archetype used by the summoning system. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stats")
	FMinionArchetype Archetype;

	FMinionArchetype ToArchetype() const
	{
		FMinionArchetype Result = Archetype;
		if (Result.MaxHP <= 0.f)
		{
			Result.MaxHP = MaxHP;
		}
		if (Result.AttackDamage <= 0.f)
		{
			Result.AttackDamage = BaseAttack;
		}
		return Result;
	}
};
