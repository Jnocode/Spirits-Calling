#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UnitHealthBarWidget.generated.h"

class UProgressBar;

/** Minimal health bar widget built entirely in C++ (no .uasset required). */
UCLASS()
class SPIRITSCALLING_API UUnitHealthBarWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void SetHealthPercent(float Percent);
	void SetBarColor(const FLinearColor& Color);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UPROPERTY()
	TObjectPtr<UProgressBar> Bar;
};
