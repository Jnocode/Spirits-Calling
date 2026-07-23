#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "SpiritsTypes.h"
#include "SpiritsHUDWidget.generated.h"

class UBorder;
class UButton;
class UCanvasPanel;
class UTextBlock;
class UVerticalBox;

/** Full in-game HUD built in C++: souls panel, summon cards, announcements, kill feed, hints, end screen. */
UCLASS()
class SPIRITSCALLING_API USpiritsHUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void ShowAnnouncement(const FString& Message, const FLinearColor& Color);
	void AddKillFeedLine(const FString& Message, const FLinearColor& Color);

#if WITH_DEV_AUTOMATION_TESTS
	void ApplyMatchPresentationForAutomation(ESpiritsMatchPhase Phase, uint8 WinningTeam, uint8 LocalTeam);
	bool IsEndOverlayVisibleForAutomation() const;
	FString GetEndTitleForAutomation() const;
	int32 GetKillFeedCountForAutomation() const;
#endif

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	UFUNCTION() void OnCard0Clicked();
	UFUNCTION() void OnCard1Clicked();
	UFUNCTION() void OnCard2Clicked();
	UFUNCTION() void OnRestartClicked();
	UFUNCTION() void OnQuitClicked();

	void SelectCard(int32 Index);
	void BuildSummonCards();
	FString SummonOptionsSignature(const TArray<FMinionArchetype>& Options) const;
	void UpdateMatchPresentation(
		ESpiritsMatchPhase Phase,
		uint8 WinningTeam,
		uint8 LocalTeam,
		class ASpiritsPlayerController* PlayerController);

	// Souls panel
	UPROPERTY() TObjectPtr<UTextBlock> SoulsText;
	UPROPERTY() TObjectPtr<UTextBlock> TeamText;
	UPROPERTY() TObjectPtr<UTextBlock> IncomeText;

	// Summon cards
	UPROPERTY() TObjectPtr<UVerticalBox> CardsBox;
	UPROPERTY() TArray<TObjectPtr<UBorder>> CardBorders;
	UPROPERTY() TArray<TObjectPtr<UButton>> CardButtons;
	UPROPERTY() TArray<TObjectPtr<UTextBlock>> CardNameTexts;
	UPROPERTY() TArray<TObjectPtr<UTextBlock>> CardCostTexts;
	bool bCardsBuilt = false;
	int32 LastMatchGeneration = INDEX_NONE;
	uint8 LastTeamId = SpiritsTeams::NoTeam;
	FString LastCardSignature;

	// Announcements / kill feed
	UPROPERTY() TObjectPtr<UTextBlock> AnnounceText;
	float AnnounceUntil = -1.f;

	// Next-wave countdown (Sid Meier: always hang a goal in front of the player)
	UPROPERTY() TObjectPtr<UTextBlock> WaveText;
	UPROPERTY() TObjectPtr<UBorder> HintPanelRef;
	float HUDStartTime = -1.f;

	UPROPERTY() TObjectPtr<UVerticalBox> KillFeedBox;
	TArray<float> KillFeedTimes;

	// Hints
	UPROPERTY() TObjectPtr<UTextBlock> HintText;

	// End screen
	UPROPERTY() TObjectPtr<UBorder> EndOverlay;
	UPROPERTY() TObjectPtr<UTextBlock> EndTitle;
	UPROPERTY() TObjectPtr<UTextBlock> EndSubtitle;
	UPROPERTY() TObjectPtr<UButton> RestartButton;
	UPROPERTY() TObjectPtr<UButton> QuitButton;
	bool bEndShown = false;

	bool bTreeBuilt = false;
};
