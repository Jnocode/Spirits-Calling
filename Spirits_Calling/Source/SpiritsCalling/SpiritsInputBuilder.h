#pragma once

#include "CoreMinimal.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"

/**
 * Helpers to build Enhanced Input actions/mappings at runtime in pure C++,
 * so the whole game is playable without any editor-created input assets.
 */
namespace SpiritsInput
{
	inline UInputAction* MakeAction(UObject* Outer, EInputActionValueType ValueType)
	{
		UInputAction* Action = NewObject<UInputAction>(Outer);
		Action->ValueType = ValueType;
		return Action;
	}

	inline FEnhancedActionKeyMapping& Map(UInputMappingContext* IMC, UInputAction* IA, const FKey& Key)
	{
		return IMC->MapKey(IA, Key);
	}

	inline void MapNegate(UInputMappingContext* IMC, UInputAction* IA, const FKey& Key,
	                      bool bX = true, bool bY = true, bool bZ = true)
	{
		FEnhancedActionKeyMapping& Mapping = IMC->MapKey(IA, Key);
		UInputModifierNegate* Negate = NewObject<UInputModifierNegate>(IMC);
		Negate->bX = bX;
		Negate->bY = bY;
		Negate->bZ = bZ;
		Mapping.Modifiers.Add(Negate);
	}

	inline void MapSwizzle(UInputMappingContext* IMC, UInputAction* IA, const FKey& Key, bool bAlsoNegate = false)
	{
		FEnhancedActionKeyMapping& Mapping = IMC->MapKey(IA, Key);
		Mapping.Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(IMC)); // default YXZ: routes X input into Y
		if (bAlsoNegate)
		{
			Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(IMC));
		}
	}

	/** WASD onto an Axis2D action where X = right, Y = forward. */
	inline void MapWASD(UInputMappingContext* IMC, UInputAction* IA)
	{
		MapSwizzle(IMC, IA, EKeys::W);              // +Y
		MapSwizzle(IMC, IA, EKeys::S, true);        // -Y
		Map(IMC, IA, EKeys::D);                     // +X
		MapNegate(IMC, IA, EKeys::A);               // -X
	}

	/** A physical 2D stick (two 1D axis keys) onto an Axis2D action: X = right, Y = forward/up. */
	inline void MapStick2D(UInputMappingContext* IMC, UInputAction* IA, const FKey& KeyX, const FKey& KeyY)
	{
		Map(IMC, IA, KeyX);          // +X
		MapSwizzle(IMC, IA, KeyY);   // +Y
	}
}
