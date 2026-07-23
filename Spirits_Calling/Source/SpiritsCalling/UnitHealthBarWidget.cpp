#include "UnitHealthBarWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/ProgressBar.h"

TSharedRef<SWidget> UUnitHealthBarWidget::RebuildWidget()
{
	if (!Bar && WidgetTree)
	{
		Bar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass(), TEXT("HealthBar"));
		Bar->SetPercent(1.f);
		Bar->SetFillColorAndOpacity(FLinearColor::Green);
		WidgetTree->RootWidget = Bar;
	}
	return Super::RebuildWidget();
}

void UUnitHealthBarWidget::SetHealthPercent(float Percent)
{
	if (Bar)
	{
		Bar->SetPercent(FMath::Clamp(Percent, 0.f, 1.f));
	}
}

void UUnitHealthBarWidget::SetBarColor(const FLinearColor& Color)
{
	if (Bar)
	{
		Bar->SetFillColorAndOpacity(Color);
	}
}
