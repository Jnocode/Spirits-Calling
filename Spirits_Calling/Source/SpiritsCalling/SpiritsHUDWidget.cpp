#include "SpiritsHUDWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/BorderSlot.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "SpiritsAudio.h"
#include "SpiritsGameState.h"
#include "SpiritsPlayerController.h"
#include "SpiritsPlayerState.h"
#include "SpiritsUIStyle.h"
#include "UnitBase.h"

TSharedRef<SWidget> USpiritsHUDWidget::RebuildWidget()
{
	if (!bTreeBuilt && WidgetTree)
	{
		bTreeBuilt = true;

		UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("HUDCanvas"));
		WidgetTree->RootWidget = Canvas;

		auto MakeText = [&](const FString& Str, int32 Size, bool bBold, const FLinearColor& Color) -> UTextBlock*
		{
			UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
			T->SetText(FText::FromString(Str));
			T->SetFont(SpiritsUI::Font(Size, bBold));
			T->SetColorAndOpacity(FSlateColor(Color));
			return T;
		};

		// ---------- Souls panel (top-left) ----------
		{
			UBorder* Panel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
			Panel->SetBrush(SpiritsUI::RoundedOutline(SpiritsUI::PanelDark(), SpiritsUI::Cyan() * 0.6f, 1.f, 12.f));
			Panel->SetPadding(FMargin(16.f, 10.f));

			UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
			Panel->SetContent(Box);

			UTextBlock* Label = MakeText(TEXT("SOULS"), 11, true, SpiritsUI::TextDim());
			Box->AddChildToVerticalBox(Label);

			SoulsText = MakeText(TEXT("0"), 30, true, SpiritsUI::Cyan());
			Box->AddChildToVerticalBox(SoulsText);

			IncomeText = MakeText(TEXT("+3 / s"), 11, false, SpiritsUI::TextDim());
			Box->AddChildToVerticalBox(IncomeText);

			TeamText = MakeText(TEXT("TEAM"), 13, true, FLinearColor::White);
			if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChildToVerticalBox(TeamText)))
			{
				S->SetPadding(FMargin(0.f, 6.f, 0.f, 0.f));
			}

			if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(Panel))
			{
				S->SetAnchors(FAnchors(0.f, 0.f));
				S->SetAlignment(FVector2D(0.f, 0.f));
				S->SetPosition(FVector2D(24.f, 24.f));
				S->SetAutoSize(true);
			}
		}

		// ---------- Summon cards (left, vertically centered) ----------
		{
			CardsBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
			if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(CardsBox))
			{
				S->SetAnchors(FAnchors(0.f, 0.5f));
				S->SetAlignment(FVector2D(0.f, 0.5f));
				S->SetPosition(FVector2D(24.f, 0.f));
				S->SetAutoSize(true);
			}
		}

		// ---------- Announcement (top center) ----------
		AnnounceText = MakeText(TEXT(""), 26, true, SpiritsUI::Gold());
		if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(AnnounceText))
		{
			S->SetAnchors(FAnchors(0.5f, 0.f));
			S->SetAlignment(FVector2D(0.5f, 0.f));
			S->SetPosition(FVector2D(0.f, 60.f));
			S->SetAutoSize(true);
		}

		// ---------- Next-wave countdown (below announcement) ----------
		WaveText = MakeText(TEXT(""), 14, true, SpiritsUI::TextDim());
		if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(WaveText))
		{
			S->SetAnchors(FAnchors(0.5f, 0.f));
			S->SetAlignment(FVector2D(0.5f, 0.f));
			S->SetPosition(FVector2D(0.f, 108.f));
			S->SetAutoSize(true);
		}

		// ---------- Kill feed (top right) ----------
		KillFeedBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
		if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(KillFeedBox))
		{
			S->SetAnchors(FAnchors(1.f, 0.f));
			S->SetAlignment(FVector2D(1.f, 0.f));
			S->SetPosition(FVector2D(-24.f, 24.f));
			S->SetAutoSize(true);
		}

		// ---------- Hint bar (bottom center) ----------
		{
			UBorder* HintPanel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
			HintPanel->SetBrush(SpiritsUI::RoundedBrush(FLinearColor(0.f, 0.f, 0.f, 0.55f), 8.f));
			HintPanel->SetPadding(FMargin(14.f, 6.f));
			HintText = MakeText(TEXT(""), 12, false, SpiritsUI::TextDim());
			HintPanel->SetContent(HintText);
			HintPanelRef = HintPanel;

			if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(HintPanel))
			{
				S->SetAnchors(FAnchors(0.5f, 1.f));
				S->SetAlignment(FVector2D(0.5f, 1.f));
				S->SetPosition(FVector2D(0.f, -20.f));
				S->SetAutoSize(true);
			}
		}

		// ---------- End screen overlay ----------
		{
			EndOverlay = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
			EndOverlay->SetBrush(SpiritsUI::RoundedBrush(FLinearColor(0.f, 0.f, 0.02f, 0.78f), 0.f));
			EndOverlay->SetVisibility(ESlateVisibility::Collapsed);
			EndOverlay->SetHorizontalAlignment(HAlign_Center);
			EndOverlay->SetVerticalAlignment(VAlign_Center);

			UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
			EndOverlay->SetContent(Box);

			EndTitle = MakeText(TEXT("VICTORY"), 54, true, SpiritsUI::Gold());
			if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChildToVerticalBox(EndTitle)))
			{
				S->SetHorizontalAlignment(HAlign_Center);
			}
			EndSubtitle = MakeText(TEXT(""), 16, false, SpiritsUI::TextDim());
			if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChildToVerticalBox(EndSubtitle)))
			{
				S->SetHorizontalAlignment(HAlign_Center);
				S->SetPadding(FMargin(0.f, 8.f, 0.f, 24.f));
			}

			auto MakeEndButton = [&](const FString& Label) -> UButton*
			{
				UButton* B = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
				B->SetStyle(SpiritsUI::ButtonStyle(SpiritsUI::PanelLight(), SpiritsUI::Cyan()));
				UTextBlock* T = MakeText(Label, 16, true, FLinearColor::White);
				B->AddChild(T);
				if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChildToVerticalBox(B)))
				{
					S->SetHorizontalAlignment(HAlign_Center);
					S->SetPadding(FMargin(0.f, 6.f));
				}
				return B;
			};
			RestartButton = MakeEndButton(TEXT("PLAY AGAIN"));
			QuitButton = MakeEndButton(TEXT("QUIT"));
			RestartButton->OnClicked.AddDynamic(this, &USpiritsHUDWidget::OnRestartClicked);
			QuitButton->OnClicked.AddDynamic(this, &USpiritsHUDWidget::OnQuitClicked);

			if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(EndOverlay))
			{
				S->SetAnchors(FAnchors(0.f, 0.f, 1.f, 1.f));
				S->SetOffsets(FMargin(0.f));
			}
		}
	}

	return Super::RebuildWidget();
}

FString USpiritsHUDWidget::SummonOptionsSignature(const TArray<FMinionArchetype>& Options) const
{
	FString Signature;
	for (int32 Index = 0; Index < Options.Num() && Index < 3; ++Index)
	{
		const FMinionArchetype& Option = Options[Index];
		Signature += FString::Printf(TEXT("%d:%s:%d;"), Index, *Option.DisplayName, Option.SummonCost);
	}
	return Signature;
}

void USpiritsHUDWidget::BuildSummonCards()
{
	const ASpiritsGameState* GS = GetWorld() ? GetWorld()->GetGameState<ASpiritsGameState>() : nullptr;
	if (!GS || !CardsBox || !WidgetTree)
	{
		return;
	}

	// Show the LOCAL player's own civilization loadout (matters in LAN where the
	// two teams field different civs).
	const ASpiritsPlayerState* LocalPS = GetOwningPlayer() ? GetOwningPlayer()->GetPlayerState<ASpiritsPlayerState>() : nullptr;
	const uint8 LocalTeam = LocalPS ? LocalPS->TeamId : SpiritsTeams::TeamA;
	const TArray<FMinionArchetype>& Options = GS->OptionsForTeam(LocalTeam);

	if (Options.Num() == 0)
	{
		return;
	}
	bCardsBuilt = true;
	LastMatchGeneration = GS->MatchGeneration;
	LastTeamId = LocalTeam;
	LastCardSignature = SummonOptionsSignature(Options);

	for (int32 i = 0; i < Options.Num() && i < 3; ++i)
	{
		const FMinionArchetype& Opt = Options[i];

		UBorder* Card = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
		Card->SetBrush(SpiritsUI::RoundedOutline(SpiritsUI::PanelDark(), SpiritsUI::Cyan() * 0.4f, 1.f, 10.f));
		Card->SetPadding(FMargin(3.f));

		UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
		FButtonStyle Invisible;
		Invisible.SetNormal(SpiritsUI::RoundedBrush(FLinearColor(0, 0, 0, 0.001f), 8.f));
		Invisible.SetHovered(SpiritsUI::RoundedBrush(FLinearColor(1, 1, 1, 0.06f), 8.f));
		Invisible.SetPressed(SpiritsUI::RoundedBrush(FLinearColor(0, 0, 0, 0.2f), 8.f));
		Button->SetStyle(Invisible);
		Card->SetContent(Button);

		UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
		Button->AddChild(Box);

		UTextBlock* Key = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Key->SetText(FText::FromString(FString::Printf(TEXT("[%d]"), i + 1)));
		Key->SetFont(SpiritsUI::Font(10, false));
		Key->SetColorAndOpacity(FSlateColor(SpiritsUI::TextDim()));
		Box->AddChildToVerticalBox(Key);

		UTextBlock* Name = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Name->SetText(FText::FromString(Opt.DisplayName));
		Name->SetFont(SpiritsUI::Font(15, true));
		Name->SetColorAndOpacity(FSlateColor(FLinearColor::White));
		Box->AddChildToVerticalBox(Name);

		UTextBlock* Cost = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Cost->SetText(FText::FromString(FString::Printf(TEXT("%d souls"), Opt.SummonCost)));
		Cost->SetFont(SpiritsUI::Font(11, false));
		Cost->SetColorAndOpacity(FSlateColor(SpiritsUI::Cyan()));
		Box->AddChildToVerticalBox(Cost);

		if (UVerticalBoxSlot* S = CardsBox->AddChildToVerticalBox(Card))
		{
			S->SetPadding(FMargin(0.f, 5.f));
		}

		CardBorders.Add(Card);
		CardButtons.Add(Button);
		CardNameTexts.Add(Name);
		CardCostTexts.Add(Cost);
	}

	if (CardButtons.Num() > 0) { CardButtons[0]->OnClicked.AddDynamic(this, &USpiritsHUDWidget::OnCard0Clicked); }
	if (CardButtons.Num() > 1) { CardButtons[1]->OnClicked.AddDynamic(this, &USpiritsHUDWidget::OnCard1Clicked); }
	if (CardButtons.Num() > 2) { CardButtons[2]->OnClicked.AddDynamic(this, &USpiritsHUDWidget::OnCard2Clicked); }
}

void USpiritsHUDWidget::SelectCard(int32 Index)
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetOwningPlayer()))
	{
		PC->SelectedArchetype = Index;
		SpiritsAudio::Play2D(this, TEXT("S_Click"), 0.5f);
	}
}

void USpiritsHUDWidget::OnCard0Clicked() { SelectCard(0); }
void USpiritsHUDWidget::OnCard1Clicked() { SelectCard(1); }
void USpiritsHUDWidget::OnCard2Clicked() { SelectCard(2); }

void USpiritsHUDWidget::OnRestartClicked()
{
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetOwningPlayer()))
	{
		PC->RequestRestartMatch();
	}
}

void USpiritsHUDWidget::OnQuitClicked()
{
	UKismetSystemLibrary::QuitGame(this, GetOwningPlayer(), EQuitPreference::Quit, false);
}

void USpiritsHUDWidget::ShowAnnouncement(const FString& Message, const FLinearColor& Color)
{
	if (AnnounceText)
	{
		AnnounceText->SetText(FText::FromString(Message));
		AnnounceText->SetColorAndOpacity(FSlateColor(Color));
		AnnounceUntil = GetWorld() ? GetWorld()->GetTimeSeconds() + 3.5f : 0.f;
	}
}

void USpiritsHUDWidget::AddKillFeedLine(const FString& Message, const FLinearColor& Color)
{
	if (!KillFeedBox || !WidgetTree || !GetWorld())
	{
		return;
	}
	UTextBlock* Line = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	Line->SetText(FText::FromString(Message));
	Line->SetFont(SpiritsUI::Font(12, false));
	Line->SetColorAndOpacity(FSlateColor(Color));
	Line->SetJustification(ETextJustify::Right);
	KillFeedBox->AddChildToVerticalBox(Line);
	KillFeedTimes.Add(GetWorld()->GetTimeSeconds());

	while (KillFeedBox->GetChildrenCount() > 6)
	{
		KillFeedBox->RemoveChildAt(0);
		KillFeedTimes.RemoveAt(0);
	}
}

void USpiritsHUDWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);

	UWorld* World = GetWorld();
	ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetOwningPlayer());
	const ASpiritsPlayerState* PS = PC ? PC->GetPlayerState<ASpiritsPlayerState>() : nullptr;
	const ASpiritsGameState* GS = World ? World->GetGameState<ASpiritsGameState>() : nullptr;
	if (!World || !PC)
	{
		return;
	}

	if (GS && PS)
	{
		const TArray<FMinionArchetype>& Options = GS->OptionsForTeam(PS->TeamId);
		const FString CurrentSignature = SummonOptionsSignature(Options);
		if (bCardsBuilt && (LastMatchGeneration != GS->MatchGeneration || LastTeamId != PS->TeamId || LastCardSignature != CurrentSignature))
		{
			CardsBox->ClearChildren();
			CardBorders.Reset();
			CardButtons.Reset();
			CardNameTexts.Reset();
			CardCostTexts.Reset();
			bCardsBuilt = false;
		}
		if (!bCardsBuilt)
		{
			BuildSummonCards();
		}

		UpdateMatchPresentation(GS->Phase, GS->WinningTeam, PS->TeamId, PC);
	}

	// Souls / team
	if (PS)
	{
		if (SoulsText)
		{
			SoulsText->SetText(FText::AsNumber(PS->Souls));
		}
		if (TeamText)
		{
			const bool bBlue = PS->TeamId == SpiritsTeams::TeamA;
			TeamText->SetText(FText::FromString(bBlue ? TEXT("BLUE SPIRITS") : TEXT("RED SPIRITS")));
			TeamText->SetColorAndOpacity(FSlateColor(SpiritsTeams::GetTeamColor(PS->TeamId) * 1.4f));
		}
	}

	// Card highlight + affordability
	for (int32 i = 0; i < CardBorders.Num(); ++i)
	{
		const bool bSelected = (PC->SelectedArchetype == i);
		if (CardBorders[i])
		{
			CardBorders[i]->SetBrush(bSelected
				? SpiritsUI::RoundedOutline(SpiritsUI::PanelLight(), SpiritsUI::Gold(), 2.f, 10.f)
				: SpiritsUI::RoundedOutline(SpiritsUI::PanelDark(), SpiritsUI::Cyan() * 0.4f, 1.f, 10.f));
		}
		if (CardCostTexts[i] && GS && PS && GS->OptionsForTeam(PS->TeamId).IsValidIndex(i))
		{
			const bool bAffordable = PS->Souls >= GS->OptionsForTeam(PS->TeamId)[i].SummonCost;
			CardCostTexts[i]->SetColorAndOpacity(FSlateColor(bAffordable ? SpiritsUI::Cyan() : SpiritsUI::Danger()));
		}
	}

	// Hints
	if (HintText)
	{
		const bool bPossessed = PC->GetPawn() && PC->GetPawn()->IsA<AUnitBase>();
		HintText->SetText(FText::FromString(bPossessed
			? TEXT("LMB Attack   |   SPACE Jump   |   Q Return to Spirit")
			: TEXT("LMB Possess   |   RMB Summon   |   1-3 Unit   |   WASD Pan   |   Q/E Rotate   |   Wheel Zoom   |   M Menu")));
	}

	// Next-wave countdown
	if (WaveText && GS)
	{
		if (GS->Phase == ESpiritsMatchPhase::InProgress && GS->NextWaveTime > 0.f)
		{
			const float Remain = GS->NextWaveTime - GS->GetServerWorldTimeSeconds();
			if (Remain > 0.f && Remain < 90.f)
			{
				WaveText->SetText(FText::FromString(FString::Printf(TEXT("Next wave in %.0fs"), Remain)));
				WaveText->SetColorAndOpacity(FSlateColor(Remain < 6.f ? SpiritsUI::Danger() : SpiritsUI::TextDim()));
			}
			else
			{
				WaveText->SetText(FText::GetEmpty());
			}
		}
		else
		{
			WaveText->SetText(FText::GetEmpty());
		}
	}

	// Chen's subtraction: the hint bar retires after the onboarding window.
	if (HintPanelRef)
	{
		if (HUDStartTime < 0.f)
		{
			HUDStartTime = World->GetTimeSeconds();
		}
		const float HUDAge = World->GetTimeSeconds() - HUDStartTime;
		HintPanelRef->SetRenderOpacity(FMath::Clamp((120.f - HUDAge) / 30.f, 0.f, 1.f));
	}

	// Announcement fade
	if (AnnounceText && AnnounceUntil > 0.f)
	{
		const float Remain = AnnounceUntil - World->GetTimeSeconds();
		AnnounceText->SetRenderOpacity(FMath::Clamp(Remain / 0.6f, 0.f, 1.f));
	}

	// Kill feed fade
	for (int32 i = KillFeedTimes.Num() - 1; i >= 0; --i)
	{
		const float Age = World->GetTimeSeconds() - KillFeedTimes[i];
		if (UWidget* Child = KillFeedBox->GetChildAt(i))
		{
			Child->SetRenderOpacity(FMath::Clamp((7.f - Age) / 1.5f, 0.f, 1.f));
		}
		if (Age > 7.f)
		{
			KillFeedBox->RemoveChildAt(i);
			KillFeedTimes.RemoveAt(i);
		}
	}

}

void USpiritsHUDWidget::UpdateMatchPresentation(
	ESpiritsMatchPhase Phase,
	uint8 WinningTeam,
	uint8 LocalTeam,
	ASpiritsPlayerController* PlayerController)
{
	if (Phase == ESpiritsMatchPhase::WaitingToStart && bEndShown)
	{
		bEndShown = false;
		if (EndOverlay)
		{
			EndOverlay->SetVisibility(ESlateVisibility::Collapsed);
		}
		if (KillFeedBox)
		{
			KillFeedBox->ClearChildren();
		}
		KillFeedTimes.Reset();
		return;
	}

	if (Phase != ESpiritsMatchPhase::Ended || bEndShown || !EndOverlay || !EndTitle || !EndSubtitle)
	{
		return;
	}

	bEndShown = true;
	const bool bWon = WinningTeam == LocalTeam;
	EndTitle->SetText(FText::FromString(bWon ? TEXT("V I C T O R Y") : TEXT("D E F E A T")));
	EndTitle->SetColorAndOpacity(FSlateColor(bWon ? SpiritsUI::Gold() : SpiritsUI::Danger()));
	EndSubtitle->SetText(FText::FromString(bWon
		? TEXT("The enemy shrine has fallen. The spirits sing your name.")
		: TEXT("Your shrine has been destroyed. The void claims all.")));
	EndOverlay->SetVisibility(ESlateVisibility::Visible);
	SpiritsAudio::Play2D(this, bWon ? TEXT("S_Victory") : TEXT("S_Defeat"), 0.9f);

	if (PlayerController)
	{
		PlayerController->bShowMouseCursor = true;
		FInputModeGameAndUI Mode;
		Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		PlayerController->SetInputMode(Mode);
	}
}

#if WITH_DEV_AUTOMATION_TESTS
void USpiritsHUDWidget::ApplyMatchPresentationForAutomation(
	ESpiritsMatchPhase Phase,
	uint8 WinningTeam,
	uint8 LocalTeam)
{
	UpdateMatchPresentation(Phase, WinningTeam, LocalTeam, nullptr);
}

bool USpiritsHUDWidget::IsEndOverlayVisibleForAutomation() const
{
	return EndOverlay && EndOverlay->GetVisibility() == ESlateVisibility::Visible;
}

FString USpiritsHUDWidget::GetEndTitleForAutomation() const
{
	return EndTitle ? EndTitle->GetText().ToString() : FString();
}

int32 USpiritsHUDWidget::GetKillFeedCountForAutomation() const
{
	return KillFeedBox ? KillFeedBox->GetChildrenCount() : 0;
}
#endif
