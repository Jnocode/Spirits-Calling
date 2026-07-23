#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "MainMenuWidget.generated.h"

class UButton;
class UEditableTextBox;
class UTextBlock;
class UVerticalBox;

/** In-game menu built entirely in C++: resume/offline, host LAN, join by IP, quit. */
UCLASS()
class SPIRITSCALLING_API UMainMenuWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	/** Shows a stable, owner-facing LAN connection error code (e.g. Match.JoinFailed). */
	void ShowConnectionError(const FString& Code);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	UFUNCTION() void OnResumeClicked();
	UFUNCTION() void OnHostClicked();
	UFUNCTION() void OnJoinClicked();
	UFUNCTION() void OnQuitClicked();
	UFUNCTION() void OnDifficultyClicked();
	UFUNCTION() void OnMapClicked();
	UFUNCTION() void OnCivClicked();

	void RefreshDifficultyLabel();
	void RefreshMapLabel();
	void RefreshCivLabel();

	UButton* MakeButton(UVerticalBox* Parent, const FString& Label);

	UPROPERTY() TObjectPtr<UButton> ResumeButton;
	UPROPERTY() TObjectPtr<UButton> DifficultyButton;
	UPROPERTY() TObjectPtr<UTextBlock> DifficultyText;
	UPROPERTY() TObjectPtr<UButton> MapButton;
	UPROPERTY() TObjectPtr<UTextBlock> MapText;
	UPROPERTY() TObjectPtr<UButton> CivButton;
	UPROPERTY() TObjectPtr<UTextBlock> CivText;
	UPROPERTY() TObjectPtr<UButton> HostButton;
	UPROPERTY() TObjectPtr<UButton> JoinButton;
	UPROPERTY() TObjectPtr<UButton> QuitButton;
	UPROPERTY() TObjectPtr<UEditableTextBox> IPBox;
	UPROPERTY() TObjectPtr<UTextBlock> ConnectionErrorText;

	bool bTreeBuilt = false;
};
