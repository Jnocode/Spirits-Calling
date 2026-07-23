#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SpiritsTypes.h"
#include "SpiritsGameMode.generated.h"

class AUnitBase;
class ASoulShrine;
class ASpiritsPlayerController;

/**
 * Match rules:
 * - Two teams, each with an auto-spawned Soul Shrine. Destroy the enemy shrine to win.
 * - Players passively earn Souls and spend them to summon minions.
 * - Kills reward the killer's whole team.
 * - Single player: enemy AI waves spawn automatically so solo mode is playable.
 */
UCLASS()
class SPIRITSCALLING_API ASpiritsGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASpiritsGameMode();

	virtual void InitGameState() override;
	virtual void BeginPlay() override;
	virtual void PostLogin(APlayerController* NewPlayer) override;
	virtual UClass* GetDefaultPawnClassForController_Implementation(AController* InController) override;

	// --- Unit registry (server) ---
	void RegisterUnit(AUnitBase* Unit);
	void UnregisterUnit(AUnitBase* Unit);
	const TArray<TWeakObjectPtr<AUnitBase>>& GetAllUnits() const { return AllUnits; }

	void NotifyUnitDied(AUnitBase* Unit, AController* Killer);

	/** Server. Validates cost, phase, placement policy, and settles the summon transaction. */
	AUnitBase* SpawnUnitForPlayer(ASpiritsPlayerController* PC, int32 ArchetypeIndex, const FVector& Location);

	/** Server. Spawns a unit for an arbitrary team (AI waves). */
	AUnitBase* SpawnUnitForTeam(int32 ArchetypeIndex, uint8 TeamId, const FVector& Location);

	/** Server. Called when a client reports its HMD state; respawns the proper spirit pawn. */
	void SetPlayerVRMode(ASpiritsPlayerController* PC, bool bVR);

	void EndMatch(uint8 InWinningTeam);

	/** Server-only restart request; resets the authoritative match in place. */
	void RequestRestartMatch(ASpiritsPlayerController* RequestingPC);

	/** Server. Rate-limited "shrine under attack" alarm. */
	void NotifyShrineDamaged(const AUnitBase* Shrine);

#if WITH_DEV_AUTOMATION_TESTS
	/** Connects a transient-world GameState without booting a full GameInstance. */
	void SetGameStateForAutomation(AGameStateBase* InGameState) { GameState = InGameState; }
#endif

	// --- Tunables ---
	/** Team A's summonable archetypes (its civilization loadout). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Spirits")
	TArray<FMinionArchetype> SummonOptions;

	/** Team B's summonable archetypes (its civilization loadout). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Spirits")
	TArray<FMinionArchetype> SummonOptionsB;

	/** Fill Out with the 3 asymmetric archetypes of a civilization (see ECivilization). */
	void BuildCivLoadout(int32 Civ, TArray<FMinionArchetype>& Out) const;

	/** Rebuild both teams' loadouts from GSpiritsCivTeamA/B (server, at match init). */
	void RebuildLoadouts();

	/** The active loadout for a team (A -> SummonOptions, B -> SummonOptionsB). */
	const TArray<FMinionArchetype>& LoadoutForTeam(uint8 InTeamId) const
	{
		return (InTeamId == SpiritsTeams::TeamB) ? SummonOptionsB : SummonOptions;
	}

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	TSubclassOf<AUnitBase> UnitClass;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	TSubclassOf<ASoulShrine> ShrineClass;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	TSubclassOf<APawn> PCSpiritPawnClass;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	TSubclassOf<APawn> VRSpiritPawnClass;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	int32 SoulsPerSecond = 3;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	int32 KillReward = 25;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	float AIWaveInterval = 30.f;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	int32 AIWaveSize = 2;

	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	int32 MaxWaveSize = 6;

	/** Desired distance of each team base from map center if fewer than 2 PlayerStarts exist.
	 *  The spawner walks inward from this distance until it finds actual ground. */
	UPROPERTY(EditDefaultsOnly, Category = "Spirits")
	float FallbackBaseDistance = 3400.f;

protected:
	void StartBattle();
	void PublishMatchSnapshot(class ASpiritsGameState* GS);
	void ResetMatchState();
	void CleanupLegacyActors();
	void SpawnShrines();
	void SoulIncomeTick();
	void MaybeStartAIWaves();
	void SpawnAIWave();
	bool HasHumanTeamB() const;
	void StopAIWavesForHumanTeamB();
	FVector GetTeamBaseLocation(uint8 TeamId) const;
	FVector ProjectToGround(const FVector& Location, float HalfHeight) const;
	bool TraceGround(const FVector& Location, FVector& OutGroundPoint) const;
	bool IsValidSummonLocation(const FVector& Location, uint8 TeamId, float HalfHeight) const;
	/** Walks from the desired base location toward the map center until ground is found. */
	FVector FindGroundedBaseLocation(uint8 TeamId, float HalfHeight) const;

	TArray<TWeakObjectPtr<AUnitBase>> AllUnits;

	UPROPERTY()
	TArray<TObjectPtr<ASoulShrine>> Shrines;

	FTimerHandle SoulTimerHandle;
	FTimerHandle WaveTimerHandle;
	FTimerHandle WaveStartTimerHandle;
	FTimerHandle StartBattleTimerHandle;

	int32 NextTeamToAssign = 0;
	bool bAIWavesActive = false;
	/** Once a Team B human appears, no later AI wave may start in this match. */
	bool bHumanTeamBSeen = false;
	bool bEndMatchProcessed = false;
	int32 WaveNumber = 0;
	int32 MatchGeneration = 0;
	uint64 SummonTransactionCounter = 0;
	TSet<FString> SettledSummonTransactions;
	float LastShrineWarnTime[2] = { -100.f, -100.f };
};
