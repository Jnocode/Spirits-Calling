#include "FXFlash.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SpiritsAssets.h"

AFXFlash::AFXFlash()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = false;

	MeshComp = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(MeshComp);
	MeshComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	MeshComp->SetCastShadow(false);
}

AFXFlash* AFXFlash::Spawn(UWorld* World, UStaticMesh* Mesh, const FVector& Location, const FRotator& Rotation,
                          const FLinearColor& Color, const FVector& StartScale, const FVector& EndScale,
                          float Lifetime, float RiseSpeed)
{
	if (!World || !Mesh || World->GetNetMode() == NM_DedicatedServer)
	{
		return nullptr;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AFXFlash* Flash = World->SpawnActor<AFXFlash>(AFXFlash::StaticClass(), Location, Rotation, Params);
	if (!Flash)
	{
		return nullptr;
	}

	Flash->MeshComp->SetStaticMesh(Mesh);
	Flash->MeshComp->SetMaterial(0, SpiritsAssets::GlowMaterial());
	Flash->MID = Flash->MeshComp->CreateAndSetMaterialInstanceDynamic(0);
	Flash->BaseColor = Color;
	Flash->ScaleFrom = StartScale;
	Flash->ScaleTo = EndScale;
	Flash->Life = FMath::Max(0.05f, Lifetime);
	Flash->Rise = RiseSpeed;
	Flash->SetActorScale3D(StartScale);
	SpiritsAssets::SetColor(Flash->MID, Color);
	Flash->SetLifeSpan(Flash->Life + 0.1f);
	return Flash;
}

void AFXFlash::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	Age += DeltaSeconds;
	const float Alpha = FMath::Clamp(Age / Life, 0.f, 1.f);

	SetActorScale3D(FMath::Lerp(ScaleFrom, ScaleTo, Alpha));
	if (Rise != 0.f)
	{
		AddActorWorldOffset(FVector(0.f, 0.f, Rise * DeltaSeconds));
	}
	SpiritsAssets::SetColor(MID, BaseColor * (1.f - Alpha));

	if (Age >= Life)
	{
		Destroy();
	}
}
