#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "SpiritsTypes.h"
#include "SpiritsGameState.generated.h"

UCLASS()
class SPIRITSCALLING_API ASpiritsGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	ASpiritsGameState();

	UPROPERTY(ReplicatedUsing = OnRep_Phase, BlueprintReadOnly, Category = "Spirits")
	ESpiritsMatchPhase Phase = ESpiritsMatchPhase::WaitingToStart;

	UPROPERTY(ReplicatedUsing = OnRep_WinningTeam, BlueprintReadOnly, Category = "Spirits")
	uint8 WinningTeam = SpiritsTeams::NoTeam;

	/** The authoritative difficulty snapshot captured before InProgress. */
	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	uint8 Difficulty = 1;

	/** Civilization snapshots captured for the two teams before InProgress. */
	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	uint8 TeamACivilization = static_cast<uint8>(ECivilization::East);

	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	uint8 TeamBCivilization = static_cast<uint8>(ECivilization::Norse);

	/** Monotonic match generation; reset to a new value for every restart. */
	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	int32 MatchGeneration = 0;

	/** Team A's summonable archetypes, filled by the GameMode and replicated so client HUDs can show names/costs. */
	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	TArray<FMinionArchetype> SummonOptions;

	/** Team B's summonable archetypes (its civilization loadout). */
	UPROPERTY(ReplicatedUsing = OnRep_MatchSnapshot, BlueprintReadOnly, Category = "Spirits")
	TArray<FMinionArchetype> SummonOptionsB;

	/** The summon list a given team should see (A -> SummonOptions, B -> SummonOptionsB). */
	const TArray<FMinionArchetype>& OptionsForTeam(uint8 InTeamId) const
	{
		return (InTeamId == SpiritsTeams::TeamB) ? SummonOptionsB : SummonOptions;
	}

	/** Selected battlefield (0 = Void, 1 = Sands). Replicated so every instance
	 *  builds identical arena geometry/collision. */
	UPROPERTY(ReplicatedUsing = OnRep_MapIndex, BlueprintReadOnly, Category = "Spirits")
	uint8 MapIndex = 0;

	/** Current AI wave number (0 = none yet). Drives HUD and the mood/color script. */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Spirits")
	uint8 CurrentWave = 0;

	/** Server world time of the next AI wave (0 = no waves scheduled). For the HUD countdown. */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Spirits")
	float NextWaveTime = 0.f;

	/** Server → all clients: center-screen announcement. SoundId: 0 none, 1 alarm. */
	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_Announce(const FString& Message, FLinearColor Color, uint8 SoundId = 0);

	/** Server → all clients: kill feed entry. */
	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_KillFeed(const FString& Message, FLinearColor Color);

	virtual void BeginPlay() override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	UFUNCTION()
	void OnRep_Phase();

	UFUNCTION()
	void OnRep_WinningTeam();

	UFUNCTION()
	void OnRep_MapIndex();

	/** Refreshes client-side arena/menu consumers when the authoritative match
	 *  settings or loadout snapshot changes. The replicated values remain the
	 *  server authority; this callback only re-reads the snapshot. */
	UFUNCTION()
	void OnRep_MatchSnapshot();

	void RefreshArenaPresentation();

#if WITH_DEV_AUTOMATION_TESTS
	const FString& GetLastRoutedMessageForAutomation() const { return LastRoutedMessage; }
	bool WasLastRouteKillFeedForAutomation() const { return bLastRouteWasKillFeed; }
	void ClearRouteCaptureForAutomation();
#endif

protected:
	void RouteToHUD(const FString& Message, const FLinearColor& Color, bool bKillFeed);

#if WITH_DEV_AUTOMATION_TESTS
	FString LastRoutedMessage;
	bool bLastRouteWasKillFeed = false;
#endif
};
