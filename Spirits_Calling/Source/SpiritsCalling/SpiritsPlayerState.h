#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"
#include "SpiritsPlayerState.generated.h"

UCLASS()
class SPIRITSCALLING_API ASpiritsPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	ASpiritsPlayerState();

	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Spirits")
	uint8 TeamId = 0;

	/** Soul currency used for summoning. */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Spirits")
	int32 Souls = 100;

	/** Server only. */
	void AddSouls(int32 Amount);

	/** Server only. Returns false if not enough souls. */
	bool TrySpendSouls(int32 Amount);

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
};
