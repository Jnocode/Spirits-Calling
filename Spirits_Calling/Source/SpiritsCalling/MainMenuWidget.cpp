#include "MainMenuWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/EditableTextBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "SpiritsAudio.h"
#include "SpiritsPlayerController.h"
#include "SpiritsTypes.h"
#include "SpiritsUIStyle.h"

UButton* UMainMenuWidget::MakeButton(UVerticalBox* Parent, const FString& Label)
{
	UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
	Button->SetStyle(SpiritsUI::ButtonStyle(SpiritsUI::PanelLight(), SpiritsUI::Cyan()));

	UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	Text->SetText(FText::FromString(Label));
	Text->SetFont(SpiritsUI::Font(15, true));
	Text->SetColorAndOpacity(FSlateColor(FLinearColor::White));
	Text->SetJustification(ETextJustify::Center);
	Button->AddChild(Text);

	if (UVerticalBoxSlot* BoxSlot = Cast<UVerticalBoxSlot>(Parent->AddChild(Button)))
	{
		BoxSlot->SetPadding(FMargin(0.f, 6.f));
		BoxSlot->SetHorizontalAlignment(HAlign_Fill);
	}
	return Button;
}

TSharedRef<SWidget> UMainMenuWidget::RebuildWidget()
{
	if (!bTreeBuilt && WidgetTree)
	{
		bTreeBuilt = true;

		UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
		WidgetTree->RootWidget = Canvas;

		// Fullscreen dark veil behind the menu
		// (BackgroundBlur is intentionally avoided: its Slate GaussianBlur shader
		//  fails to compile with this project's Forward+MSAA+Substrate settings.)
		UBorder* Veil = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
		Veil->SetBrush(SpiritsUI::RoundedBrush(FLinearColor(0.f, 0.005f, 0.02f, 0.72f), 0.f));
		if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(Veil))
		{
			S->SetAnchors(FAnchors(0.f, 0.f, 1.f, 1.f));
			S->SetOffsets(FMargin(0.f));
		}

		// Center panel
		UBorder* Panel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
		Panel->SetBrush(SpiritsUI::RoundedOutline(SpiritsUI::PanelDark(), SpiritsUI::Cyan() * 0.7f, 1.5f, 18.f));
		Panel->SetPadding(FMargin(46.f, 36.f));
		if (UCanvasPanelSlot* S = Canvas->AddChildToCanvas(Panel))
		{
			S->SetAnchors(FAnchors(0.5f, 0.5f));
			S->SetAlignment(FVector2D(0.5f, 0.5f));
			S->SetAutoSize(true);
		}

		UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
		Panel->SetContent(Box);

		UTextBlock* Title = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Title->SetText(FText::FromString(TEXT("SPIRITS CALLING")));
		Title->SetFont(SpiritsUI::Font(40, true));
		Title->SetColorAndOpacity(FSlateColor(SpiritsUI::Cyan()));
		if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChild(Title)))
		{
			S->SetHorizontalAlignment(HAlign_Center);
		}

		UTextBlock* Subtitle = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Subtitle->SetText(FText::FromString(TEXT("Summon. Possess. Conquer.")));
		Subtitle->SetFont(SpiritsUI::Font(13, false));
		Subtitle->SetColorAndOpacity(FSlateColor(SpiritsUI::TextDim()));
		if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChild(Subtitle)))
		{
			S->SetHorizontalAlignment(HAlign_Center);
			S->SetPadding(FMargin(0.f, 4.f, 0.f, 22.f));
		}

		ResumeButton = MakeButton(Box, TEXT("PLAY"));

		DifficultyButton = MakeButton(Box, TEXT("DIFFICULTY: NORMAL"));
		DifficultyText = Cast<UTextBlock>(DifficultyButton->GetChildAt(0));

		MapButton = MakeButton(Box, TEXT("MAP: VOID"));
		MapText = Cast<UTextBlock>(MapButton->GetChildAt(0));

		CivButton = MakeButton(Box, TEXT("CIVILIZATION: EAST"));
		CivText = Cast<UTextBlock>(CivButton->GetChildAt(0));

		HostButton = MakeButton(Box, TEXT("HOST LAN GAME"));

		IPBox = WidgetTree->ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass());
		IPBox->SetText(FText::FromString(TEXT("127.0.0.1")));
		IPBox->SetJustification(ETextJustify::Center);
		if (UVerticalBoxSlot* IPSlot = Cast<UVerticalBoxSlot>(Box->AddChild(IPBox)))
		{
			IPSlot->SetPadding(FMargin(0.f, 12.f, 0.f, 0.f));
			IPSlot->SetHorizontalAlignment(HAlign_Fill);
		}

		JoinButton = MakeButton(Box, TEXT("JOIN IP"));

		// Owner-facing connection error line (empty until a join/connection fails).
		ConnectionErrorText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		ConnectionErrorText->SetText(FText::GetEmpty());
		ConnectionErrorText->SetFont(SpiritsUI::Font(11, true));
		ConnectionErrorText->SetColorAndOpacity(FSlateColor(FLinearColor(0.95f, 0.30f, 0.25f)));
		ConnectionErrorText->SetJustification(ETextJustify::Center);
		if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChild(ConnectionErrorText)))
		{
			S->SetHorizontalAlignment(HAlign_Center);
			S->SetPadding(FMargin(0.f, 8.f, 0.f, 0.f));
		}

		QuitButton = MakeButton(Box, TEXT("QUIT"));

		UTextBlock* Footer = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
		Footer->SetText(FText::FromString(TEXT("Map / Civilization / Difficulty apply on Host or a new match")));
		Footer->SetFont(SpiritsUI::Font(10, false));
		Footer->SetColorAndOpacity(FSlateColor(SpiritsUI::TextDim() * 0.8f));
		if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(Box->AddChild(Footer)))
		{
			S->SetHorizontalAlignment(HAlign_Center);
			S->SetPadding(FMargin(0.f, 18.f, 0.f, 0.f));
		}

		ResumeButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnResumeClicked);
		DifficultyButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnDifficultyClicked);
		MapButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnMapClicked);
		CivButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnCivClicked);
		HostButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnHostClicked);
		JoinButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnJoinClicked);
		QuitButton->OnClicked.AddDynamic(this, &UMainMenuWidget::OnQuitClicked);
		RefreshDifficultyLabel();
		RefreshMapLabel();
		RefreshCivLabel();
	}

	return Super::RebuildWidget();
}

void UMainMenuWidget::RefreshDifficultyLabel()
{
	if (DifficultyText)
	{
		const TCHAR* Names[3] = { TEXT("DIFFICULTY: EASY"), TEXT("DIFFICULTY: NORMAL"), TEXT("DIFFICULTY: HARD") };
		DifficultyText->SetText(FText::FromString(Names[FMath::Clamp(GSpiritsDifficulty, 0, 2)]));
	}
}

void UMainMenuWidget::OnDifficultyClicked()
{
	GSpiritsDifficulty = (GSpiritsDifficulty + 1) % 3;
	RefreshDifficultyLabel();
	SpiritsAudio::Play2D(this, TEXT("S_Click"), 0.6f);
}

void UMainMenuWidget::RefreshMapLabel()
{
	if (MapText)
	{
		const TCHAR* Names[SpiritsMaps::Num] = { TEXT("MAP: VOID"), TEXT("MAP: SANDS") };
		MapText->SetText(FText::FromString(Names[FMath::Clamp(GSpiritsMapIndex, 0, SpiritsMaps::Num - 1)]));
	}
}

void UMainMenuWidget::OnMapClicked()
{
	GSpiritsMapIndex = (GSpiritsMapIndex + 1) % SpiritsMaps::Num;
	RefreshMapLabel();
	SpiritsAudio::Play2D(this, TEXT("S_Click"), 0.6f);
}

void UMainMenuWidget::RefreshCivLabel()
{
	if (CivText)
	{
		CivText->SetText(FText::FromString(
			FString::Printf(TEXT("CIVILIZATION: %s"), SpiritsCiv::GetName(GSpiritsCivTeamA)).ToUpper()));
	}
}

void UMainMenuWidget::OnCivClicked()
{
	// Cycle the player's (Team A) civilization; keep the AI/opponent (Team B) on a
	// DIFFERENT civ so single-player always stays an asymmetric matchup.
	GSpiritsCivTeamA = (GSpiritsCivTeamA + 1) % SpiritsCiv::Num;
	GSpiritsCivTeamB = (GSpiritsCivTeamA + 1) % SpiritsCiv::Num;
	RefreshCivLabel();
	SpiritsAudio::Play2D(this, TEXT("S_Click"), 0.6f);
}

void UMainMenuWidget::OnResumeClicked()
{
	SpiritsAudio::Play2D(this, TEXT("S_Click"), 0.6f);
	if (ASpiritsPlayerController* PC = Cast<ASpiritsPlayerController>(GetOwningPlayer()))
	{
		PC->CloseMainMenu();
	}
}

void UMainMenuWidget::OnHostClicked()
{
	UGameplayStatics::OpenLevel(this, FName(TEXT("/Game/Maps/DemoMap")), true, TEXT("listen"));
}

void UMainMenuWidget::OnJoinClicked()
{
	APlayerController* PC = GetOwningPlayer();
	if (PC && IPBox)
	{
		const FString IP = IPBox->GetText().ToString().TrimStartAndEnd();
		if (!IP.IsEmpty())
		{
			// Record the attempt before travelling so a travel/network failure
			// resolves to Match.JoinFailed rather than a stale connected state.
			if (ASpiritsPlayerController* SpiritsPC = Cast<ASpiritsPlayerController>(PC))
			{
				SpiritsPC->BeginJoinAttempt();
			}
			if (ConnectionErrorText)
			{
				ConnectionErrorText->SetText(FText::GetEmpty());
			}
			PC->ClientTravel(IP, ETravelType::TRAVEL_Absolute);
		}
	}
}

void UMainMenuWidget::ShowConnectionError(const FString& Code)
{
	if (ConnectionErrorText)
	{
		ConnectionErrorText->SetText(FText::FromString(
			FString::Printf(TEXT("Connection failed [%s]"), *Code)));
	}
}

void UMainMenuWidget::OnQuitClicked()
{
	UKismetSystemLibrary::QuitGame(this, GetOwningPlayer(), EQuitPreference::Quit, false);
}
