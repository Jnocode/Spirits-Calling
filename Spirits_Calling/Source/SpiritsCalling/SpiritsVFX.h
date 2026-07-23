#pragma once

#include "CoreMinimal.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

/**
 * Niagara VFX helper. Systems live in /Game/VFX (create them in the editor from the
 * generated sprite sheets: a Sprite Renderer with a SubUV/Flipbook material, Additive
 * blend, and a user-exposed LinearColor parameter named "Color" for team tinting).
 *
 * Every call is null-safe: if the asset hasn't been created yet, nothing spawns and the
 * game keeps running (mirrors SpiritsAudio) — so the C++ build stays playable without
 * any editor-created VFX assets.
 */
namespace SpiritsVFX
{
	inline UNiagaraSystem* Get(const TCHAR* Name)
	{
		return LoadObject<UNiagaraSystem>(nullptr, *FString::Printf(TEXT("/Game/VFX/%s.%s"), Name, Name));
	}

	/** Spawn a one-shot system at a world location, tinted via its "Color" user parameter. */
	inline UNiagaraComponent* SpawnAt(const UObject* Ctx, const TCHAR* Name,
	                                  const FVector& Location, const FRotator& Rotation,
	                                  const FLinearColor& Color, float Scale = 1.f)
	{
		UWorld* World = Ctx ? Ctx->GetWorld() : nullptr;
		UNiagaraSystem* System = Get(Name);
		if (!World || !System)
		{
			return nullptr;
		}
		UNiagaraComponent* Comp = UNiagaraFunctionLibrary::SpawnSystemAtLocation(
			World, System, Location, Rotation, FVector(Scale), /*bAutoDestroy=*/true, /*bAutoActivate=*/true);
		if (Comp)
		{
			Comp->SetVariableLinearColor(FName(TEXT("Color")), Color);
		}
		return Comp;
	}
}
