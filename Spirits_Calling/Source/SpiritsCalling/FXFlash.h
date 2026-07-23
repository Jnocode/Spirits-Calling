#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FXFlash.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/**
 * Lightweight cosmetic flash: a glowing mesh that scales/fades over its
 * lifetime then destroys itself. Used for attack slashes, hits, deaths,
 * summons and shrine feedback. Purely local (spawn on each client).
 */
UCLASS()
class SPIRITSCALLING_API AFXFlash : public AActor
{
	GENERATED_BODY()

public:
	AFXFlash();

	static AFXFlash* Spawn(UWorld* World, UStaticMesh* Mesh, const FVector& Location, const FRotator& Rotation,
	                       const FLinearColor& Color, const FVector& StartScale, const FVector& EndScale,
	                       float Lifetime, float RiseSpeed = 0.f);

	virtual void Tick(float DeltaSeconds) override;

protected:
	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> MeshComp;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> MID;

	FLinearColor BaseColor = FLinearColor::White;
	FVector ScaleFrom = FVector::OneVector;
	FVector ScaleTo = FVector::OneVector;
	float Life = 0.3f;
	float Age = 0.f;
	float Rise = 0.f;
};
