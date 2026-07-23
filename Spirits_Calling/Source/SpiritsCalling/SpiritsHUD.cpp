#include "SpiritsHUD.h"

#include "Blueprint/UserWidget.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "SpiritsHUDWidget.h"
#include "SpiritsPlayerController.h"
#include "UnitBase.h"

void ASpiritsHUD::BeginPlay()
{
	Super::BeginPlay();

	APlayerController* PC = GetOwningPlayerController();
	if (PC && PC->IsLocalController())
	{
		HUDWidget = CreateWidget<USpiritsHUDWidget>(PC, USpiritsHUDWidget::StaticClass());
		if (HUDWidget)
		{
			HUDWidget->AddToViewport(5);
		}
	}
}

void ASpiritsHUD::AddDamageNumber(const FVector& WorldLocation, float Amount)
{
	FDamageNumber Num;
	Num.WorldLocation = WorldLocation + FVector(FMath::FRandRange(-18.f, 18.f), FMath::FRandRange(-18.f, 18.f), 0.f);
	Num.Amount = Amount;
	Num.SpawnTime = GetWorld()->GetTimeSeconds();
	DamageNumbers.Add(Num);
}

void ASpiritsHUD::AddKillFeed(const FString& Message, const FLinearColor& Color)
{
	if (HUDWidget)
	{
		HUDWidget->AddKillFeedLine(Message, Color);
	}
}

void ASpiritsHUD::AddAnnouncement(const FString& Message, const FLinearColor& Color)
{
	if (HUDWidget)
	{
		HUDWidget->ShowAnnouncement(Message, Color);
	}
}

void ASpiritsHUD::DrawHUD()
{
	Super::DrawHUD();

	if (!Canvas)
	{
		return;
	}

	APlayerController* PC = GetOwningPlayerController();
	UFont* Font = GEngine->GetMediumFont();
	const float Now = GetWorld()->GetTimeSeconds();

	// --- Floating damage numbers ---
	for (int32 i = DamageNumbers.Num() - 1; i >= 0; --i)
	{
		const FDamageNumber& Num = DamageNumbers[i];
		const float Age = Now - Num.SpawnTime;
		if (Age > 0.9f)
		{
			DamageNumbers.RemoveAt(i);
			continue;
		}

		FVector2D ScreenPos;
		if (PC && UGameplayStatics::ProjectWorldToScreen(PC, Num.WorldLocation + FVector(0, 0, Age * 90.f), ScreenPos))
		{
			const float Alpha = 1.f - FMath::Square(Age / 0.9f);
			const FLinearColor Color(1.f, 0.9f, 0.35f, Alpha);
			DrawText(FString::Printf(TEXT("%.0f"), Num.Amount), Color, ScreenPos.X, ScreenPos.Y, Font, 1.25f);
		}
	}

	// --- Possessed: crosshair + health bar ---
	const AUnitBase* Possessed = PC ? Cast<AUnitBase>(PC->GetPawn()) : nullptr;
	if (Possessed)
	{
		const float W = Canvas->SizeX;
		const float H = Canvas->SizeY;

		DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.9f), W * 0.5f - 6.f, H * 0.5f - 1.f, 12.f, 2.f);
		DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.9f), W * 0.5f - 1.f, H * 0.5f - 6.f, 2.f, 12.f);

		const float BarW = 340.f;
		const float Pct = Possessed->GetHealthPercent();
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), W * 0.5f - BarW * 0.5f - 3.f, H - 96.f, BarW + 6.f, 20.f);
		DrawRect(FLinearColor(0.9f - 0.9f * Pct, 0.9f * Pct, 0.15f, 1.f), W * 0.5f - BarW * 0.5f, H - 93.f, BarW * Pct, 14.f);
		DrawText(FString::Printf(TEXT("%s  %.0f / %.0f"), *Possessed->Stats.DisplayName, Possessed->Health, Possessed->Stats.MaxHP),
		         FLinearColor::White, W * 0.5f - 60.f, H - 92.f, GEngine->GetSmallFont());
	}
}
