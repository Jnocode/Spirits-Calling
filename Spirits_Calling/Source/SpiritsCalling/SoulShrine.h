#pragma once

#include "CoreMinimal.h"
#include "UnitBase.h"
#include "SoulShrine.generated.h"

class UStaticMeshComponent;

/**
 * Team objective: a glowing obelisk with rotating soul rings and a floating
 * crystal. When a team's shrine is destroyed, the other team wins.
 * Spawned automatically by ASpiritsGameMode, no level editing required.
 */
UCLASS()
class SPIRITSCALLING_API ASoulShrine : public AUnitBase
{
	GENERATED_BODY()

public:
	ASoulShrine();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
	virtual void ApplyVisuals() override;

	UPROPERTY() TObjectPtr<UStaticMeshComponent> Obelisk;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Crystal;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> RingA;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> RingB;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> BaseGlow;

	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> ObeliskMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CrystalMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RingAMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RingBMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BaseGlowMID;

	float SpinTime = 0.f;
	float LastFlashHealth = -1.f;
	bool bFallFXDone = false;
};
