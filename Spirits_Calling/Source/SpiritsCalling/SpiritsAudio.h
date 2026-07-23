#pragma once

#include "CoreMinimal.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

/**
 * Audio helper. Assets live in /Game/Audio (import RawAssets/Audio/*.wav once
 * via drag & drop into a Content/Audio folder). Every call is null-safe:
 * the game runs silently if the assets haven't been imported yet.
 */
namespace SpiritsAudio
{
	inline USoundBase* Get(const TCHAR* Name)
	{
		return LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/%s.%s"), Name, Name));
	}

	inline void Play2D(const UObject* Ctx, const TCHAR* Name, float Volume = 1.f, float Pitch = 1.f)
	{
		if (USoundBase* S = Get(Name))
		{
			UGameplayStatics::PlaySound2D(Ctx, S, Volume, Pitch);
		}
	}

	/** Pitch < 0 → mild random pitch variation; otherwise the exact pitch given. */
	inline void PlayAt(const UObject* Ctx, const TCHAR* Name, const FVector& Location, float Volume = 1.f, float Pitch = -1.f)
	{
		if (USoundBase* S = Get(Name))
		{
			const float FinalPitch = (Pitch < 0.f) ? FMath::FRandRange(0.92f, 1.08f) : Pitch;
			UGameplayStatics::PlaySoundAtLocation(Ctx, S, Location, Volume, FinalPitch);
		}
	}
}
