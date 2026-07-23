#pragma once

#include "CoreMinimal.h"
#include "Styling/CoreStyle.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"

/** Shared code-built UI styling for Spirits Calling (no editor assets). */
namespace SpiritsUI
{
	inline FLinearColor PanelDark()   { return FLinearColor(0.008f, 0.012f, 0.03f, 0.86f); }
	inline FLinearColor PanelLight()  { return FLinearColor(0.03f, 0.05f, 0.1f, 0.9f); }
	inline FLinearColor Cyan()        { return FLinearColor(0.2f, 0.85f, 1.f); }
	inline FLinearColor Gold()        { return FLinearColor(1.f, 0.82f, 0.35f); }
	inline FLinearColor Danger()      { return FLinearColor(1.f, 0.25f, 0.2f); }
	inline FLinearColor TextDim()     { return FLinearColor(0.65f, 0.72f, 0.85f); }

	inline FSlateBrush RoundedBrush(const FLinearColor& Color, float Radius = 10.f)
	{
		FSlateBrush Brush;
		Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
		Brush.TintColor = Color;
		Brush.OutlineSettings.CornerRadii = FVector4(Radius, Radius, Radius, Radius);
		Brush.OutlineSettings.RoundingType = ESlateBrushRoundingType::FixedRadius;
		return Brush;
	}

	inline FSlateBrush RoundedOutline(const FLinearColor& Fill, const FLinearColor& Outline, float Width, float Radius = 10.f)
	{
		FSlateBrush Brush = RoundedBrush(Fill, Radius);
		Brush.OutlineSettings.Color = Outline;
		Brush.OutlineSettings.Width = Width;
		return Brush;
	}

	inline FButtonStyle ButtonStyle(const FLinearColor& Base, const FLinearColor& Accent, float Radius = 8.f)
	{
		FButtonStyle Style;
		Style.SetNormal(RoundedOutline(Base, Accent * 0.5f, 1.f, Radius));
		Style.SetHovered(RoundedOutline(Base + Accent * 0.18f, Accent, 1.5f, Radius));
		Style.SetPressed(RoundedOutline(Base * 0.6f, Accent, 1.5f, Radius));
		Style.SetNormalPadding(FMargin(2.f));
		Style.SetPressedPadding(FMargin(2.f, 3.f, 2.f, 1.f));
		return Style;
	}

	inline FSlateFontInfo Font(int32 Size, bool bBold = false)
	{
		return FCoreStyle::GetDefaultFontStyle(bBold ? "Bold" : "Regular", Size);
	}
}
