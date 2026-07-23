#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SpiritsHUD.generated.h"

class USpiritsHUDWidget;

/**
 * HUD owner: creates the UMG HUD widget and draws the few things that are
 * cheaper on canvas (floating damage numbers, possessed crosshair & health bar).
 */
UCLASS()
class SPIRITSCALLING_API ASpiritsHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void BeginPlay() override;
	virtual void DrawHUD() override;

	void AddDamageNumber(const FVector& WorldLocation, float Amount);
	void AddKillFeed(const FString& Message, const FLinearColor& Color);
	void AddAnnouncement(const FString& Message, const FLinearColor& Color);

protected:
	UPROPERTY()
	TObjectPtr<USpiritsHUDWidget> HUDWidget;

	struct FDamageNumber
	{
		FVector WorldLocation;
		float Amount = 0.f;
		float SpawnTime = 0.f;
	};
	TArray<FDamageNumber> DamageNumbers;
};
