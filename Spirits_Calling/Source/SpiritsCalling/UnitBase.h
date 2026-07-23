#pragma once

#include "CoreMinimal.h"
#include "Engine/NetSerialization.h"
#include "GameFramework/Character.h"
#include "PlatformActionRouter.h"
#include "SpiritsTypes.h"
#include "UnitBase.generated.h"

class UStaticMeshComponent;
class UPointLightComponent;
class UWidgetComponent;
class USpringArmComponent;
class UCameraComponent;
class UMaterialInstanceDynamic;
class UInputAction;
class UInputMappingContext;
class UUnitHealthBarWidget;
struct FInputActionValue;

/**
 * A summonable, possessable spirit combat unit ("ghost" visual built from
 * glowing primitives, animated in code — no skeletal animations required).
 * - AI controlled by default (AUnitAIController, server side).
 * - Can be possessed by a player (PC: third person; VR: first person w/ HMD).
 * - All input assets are created at runtime in C++ (no editor wiring needed).
 */
UCLASS()
class SPIRITSCALLING_API AUnitBase : public ACharacter
{
	GENERATED_BODY()

public:
	AUnitBase();

	/** Server only: apply archetype stats, team and visuals. */
	void InitUnit(const FMinionArchetype& InStats, uint8 InTeamId,
	              ECivilization InCivilization = ECivilization::East);

	UPROPERTY(ReplicatedUsing = OnRep_Visuals, BlueprintReadOnly, Category = "Spirits")
	FMinionArchetype Stats;

	UPROPERTY(ReplicatedUsing = OnRep_Visuals, BlueprintReadOnly, Category = "Spirits")
	uint8 TeamId = SpiritsTeams::NoTeam;

	/** Match civilization snapshot used to resolve the canonical BodyMID pattern. */
	UPROPERTY(ReplicatedUsing = OnRep_Visuals, BlueprintReadOnly, Category = "Spirits")
	ECivilization Civilization = ECivilization::East;

	UPROPERTY(ReplicatedUsing = OnRep_Health, BlueprintReadOnly, Category = "Spirits")
	float Health = 100.f;

	/** Structures (e.g. Soul Shrine) can't move, attack or be possessed. */
	UPROPERTY(Replicated, BlueprintReadOnly, Category = "Spirits")
	bool bIsStructure = false;

	UFUNCTION(BlueprintPure, Category = "Spirits")
	bool IsDead() const { return Health <= 0.f; }

	UFUNCTION(BlueprintPure, Category = "Spirits")
	float GetHealthPercent() const { return Stats.MaxHP > 0.f ? Health / Stats.MaxHP : 0.f; }

	/** Works on server directly; from owning client sends a Server RPC. */
	UFUNCTION(BlueprintCallable, Category = "Spirits")
	void TryAttack();

	/** Heavy attack: a committed, slow, high-reward swing (player-only hero tool).
	 *  Works on server directly; from owning client sends a Server RPC. */
	UFUNCTION(BlueprintCallable, Category = "Spirits")
	void TryHeavyAttack();

	/** Server authority barrier used by death, match end, restart and actor teardown. */
	void CancelPendingCombat(bool bBroadcastCancellation = true);

#if WITH_DEV_AUTOMATION_TESTS
	/** Arms real timer/cosmetic state so automation can verify EndPlay cleanup. */
	void PrimePendingCombatForAutomation();
	bool HasPendingCombatForAutomation() const;
	int32 GetCombatCancellationBroadcastCountForAutomation() const { return CombatCancellationBroadcastCount; }
	/** Invokes the production EndPlay override when a transient test world cannot route world lifecycle. */
	void InvokeEndPlayForAutomation(EEndPlayReason::Type EndPlayReason) { EndPlay(EndPlayReason); }
#endif

	//~ ACharacter
	virtual float TakeDamage(float DamageAmount, const FDamageEvent& DamageEvent,
	                         AController* EventInstigator, AActor* DamageCauser) override;
	virtual void PossessedBy(AController* NewController) override;
	virtual void UnPossessed() override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION()
	void OnRep_Health();

	UFUNCTION()
	void OnRep_Visuals();

	UFUNCTION(Server, Reliable)
	void Server_TryAttack();

	UFUNCTION(Server, Reliable)
	void Server_TryHeavyAttack();

	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_AttackFX(FVector_NetQuantize TraceEnd, bool bHit);

	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_HeavyWindupFX();

	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_HeavyFX(FVector_NetQuantize TraceEnd, bool bHit);

	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_CancelHeavyFX();

	UFUNCTION(NetMulticast, Unreliable)
	void Multicast_DamageFX(float Amount, FVector_NetQuantize Location);

	void PerformAttack_Server();

	/** Server: begin the heavy attack windup (movement slows; strike lands after a delay). */
	void BeginHeavy_Server();

	/** Server: resolve the heavy strike at the end of the windup. */
	void PerformHeavy_Server();
	bool CanResolveCombat_Server() const;
	void HandleDeath(AController* Killer);
	virtual void ApplyVisuals();
	void UpdateCosmetics(float DeltaSeconds);

	// --- Ghost visual rig (all cosmetic) ---
	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<USceneComponent> VisualRoot;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> BodyMesh;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> HeadMesh;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> EyeLeft;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> EyeRight;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UStaticMeshComponent> BaseRing;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UPointLightComponent> GlowLight;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UWidgetComponent> HealthBarComp;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<USpringArmComponent> SpringArm;

	UPROPERTY(VisibleAnywhere, Category = "Spirits")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BodyMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> HeadMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> EyeMIDL;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> EyeMIDR;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RingMID;

	UPROPERTY()
	TObjectPtr<UUnitHealthBarWidget> HealthWidget;

	// --- Runtime-built input ---
	UPROPERTY()
	TObjectPtr<UInputMappingContext> PossessedIMC;

	UPROPERTY() TObjectPtr<UInputAction> IA_Move;
	UPROPERTY() TObjectPtr<UInputAction> IA_Look;
	UPROPERTY() TObjectPtr<UInputAction> IA_Attack;
	UPROPERTY() TObjectPtr<UInputAction> IA_HeavyAttack;
	UPROPERTY() TObjectPtr<UInputAction> IA_Unpossess;
	UPROPERTY() TObjectPtr<UInputAction> IA_Jump;
	UPROPERTY() TObjectPtr<UInputAction> IA_SnapTurn;

	void BuildInputAssets();
	void OnMoveInput(const FInputActionValue& Value);
	void OnLookInput(const FInputActionValue& Value);
	void OnAttackInput(const FInputActionValue& Value);
	void OnHeavyAttackInput(const FInputActionValue& Value);
	void OnUnpossessInput(const FInputActionValue& Value);
	void OnJumpInput(const FInputActionValue& Value);
	void OnSnapTurnInput(const FInputActionValue& Value);

	// Cosmetic animation state
	float HoverTime = 0.f;
	float AttackAnim = 0.f;
	float DeathAnim = 0.f;
	float SpawnAnim = 1.f;
	float DamageFlash = 0.f;
	bool bDeathSoundPlayed = false;
	FTimerHandle HitStopHandle;
	float CurrentLean = 0.f;
	bool bDeathFXDone = false;

	// Heavy-attack cosmetic state (client): winds the body back, then a big lunge.
	bool bHeavyCharging = false;
	bool bHeavyLunge = false;
	float HeavyChargeTime = 0.f;

	float LastAttackTime = -1000.f;
	SpiritsPlatform::FComfortTurnGate ComfortTurnGate;
	bool bDeathHandled = false;

	// Heavy-attack server state.
	float LastHeavyTime = -1000.f;
	float HeavyWindupEndTime = 0.f;   // world time the strike lands (0 = not winding up)
	float HeavySavedWalkSpeed = 0.f;  // MaxWalkSpeed restored after the windup
	FTimerHandle HeavyWindupHandle;

	/** Heavy-attack tuning (Sakurai: commit to the windup, get paid on contact). */
	static constexpr float HeavyWindup = 0.4f;         // front-swing commitment (s)
	static constexpr float HeavyDamageMult = 2.2f;     // vs. light attack damage
	static constexpr float HeavyKnockback = 480.f;     // ~2x light knockback
	static constexpr float HeavyRangeMult = 1.3f;
	static constexpr float HeavyRadius = 90.f;         // vs. 60 light
	static constexpr float HeavyCooldownMult = 2.2f;   // of AttackInterval
	static constexpr float HeavyHitStop = 0.12f;

#if WITH_DEV_AUTOMATION_TESTS
	int32 CombatCancellationBroadcastCount = 0;
#endif
};
