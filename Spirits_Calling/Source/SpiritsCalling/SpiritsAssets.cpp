#include "SpiritsAssets.h"

#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/UObjectGlobals.h"

namespace SpiritsAssets
{

UStaticMesh* Mesh(const TCHAR* Path)
{
	return LoadObject<UStaticMesh>(nullptr, Path);
}

UMaterialInterface* Material(const TCHAR* Path)
{
	return LoadObject<UMaterialInterface>(nullptr, Path);
}

UStaticMesh* Sphere()   { return Mesh(TEXT("/Engine/BasicShapes/Sphere.Sphere")); }
UStaticMesh* Cube()     { return Mesh(TEXT("/Engine/BasicShapes/Cube.Cube")); }
UStaticMesh* Cylinder() { return Mesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")); }

UStaticMesh* ChamferCube()     { return Mesh(TEXT("/Game/LevelPrototyping/Meshes/SM_ChamferCube.SM_ChamferCube")); }
UStaticMesh* CircularBand()    { return Mesh(TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Meshes/SM_CircularBand.SM_CircularBand")); }
UStaticMesh* CircularGlow()    { return Mesh(TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Meshes/SM_CircularGlow.SM_CircularGlow")); }
UStaticMesh* QuarterCylinder() { return Mesh(TEXT("/Game/LevelPrototyping/Meshes/SM_QuarterCylinder.SM_QuarterCylinder")); }
UStaticMesh* Plane()           { return Mesh(TEXT("/Game/LevelPrototyping/Meshes/SM_Plane.SM_Plane")); }

UMaterialInterface* BasicShapeMaterial()
{
	return Material(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
}

UMaterialInterface* GlowMaterial()
{
	UMaterialInterface* Glow = Material(TEXT("/Game/LevelPrototyping/Interactable/JumpPad/Assets/Materials/M_SimpleGlow.M_SimpleGlow"));
	return Glow ? Glow : BasicShapeMaterial();
}

UMaterialInterface* GridMaterialDark()
{
	UMaterialInterface* Grid = Material(TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_TopDark.MI_PrototypeGrid_TopDark"));
	return Grid ? Grid : BasicShapeMaterial();
}

UMaterialInterface* GridMaterialGray()
{
	UMaterialInterface* Grid = Material(TEXT("/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray.MI_PrototypeGrid_Gray"));
	return Grid ? Grid : BasicShapeMaterial();
}

UMaterialInterface* UnitBodyMaterial()
{
	return Material(TEXT("/Game/Materials/M_UnitBody.M_UnitBody"));
}

UMaterialInterface* ArenaSurfaceMaterial()
{
	return Material(TEXT("/Game/Materials/M_ArenaSurface.M_ArenaSurface"));
}

UTexture2D* LoadRequiredTexture(const TCHAR* Path, const TCHAR* Hook)
{
	UTexture2D* Texture = LoadObject<UTexture2D>(nullptr, Path);
	if (!Texture)
	{
		UE_LOG(LogTemp, Error, TEXT("[Asset.MissingCookReference] hook=%s path=%s"), Hook ? Hook : TEXT("unknown"), Path ? Path : TEXT("<null>"));
	}
	return Texture;
}

UTexture2D* CivilizationPattern(int32 Civilization)
{
	static const TCHAR* Paths[] =
	{
		TEXT("/Game/Textures/Civilizations/East_pattern.East_pattern"),
		TEXT("/Game/Textures/Civilizations/Norse_pattern.Norse_pattern"),
		TEXT("/Game/Textures/Civilizations/Egypt_pattern.Egypt_pattern"),
		TEXT("/Game/Textures/Civilizations/Cyber_pattern.Cyber_pattern")
	};
	const int32 Index = FMath::Clamp(Civilization, 0, UE_ARRAY_COUNT(Paths) - 1);
	const TCHAR* Hook = TEXT("BodyMID.PatternTex|SoulShrine.PatternTex");
	return LoadRequiredTexture(Paths[Index], Hook);
}

UTexture2D* ArenaGroundTexture(int32 MapIndex)
{
	return MapIndex == 1
		? LoadRequiredTexture(TEXT("/Game/Textures/Arenas/Sands/Arena_Sands_ground.Arena_Sands_ground"), TEXT("ArenaMaterialHook.Sands.Ground"))
		: LoadRequiredTexture(TEXT("/Game/Textures/Arenas/Void/Arena_Void_ground.Arena_Void_ground"), TEXT("ArenaMaterialHook.Void.Ground"));
}

UTexture2D* ArenaSkyTexture(int32 MapIndex)
{
	return MapIndex == 1
		? LoadRequiredTexture(TEXT("/Game/Textures/Arenas/Sands/Arena_Sands_sky.Arena_Sands_sky"), TEXT("ArenaMaterialHook.Sands.Sky"))
		: LoadRequiredTexture(TEXT("/Game/Textures/Arenas/Void/Arena_Void_sky.Arena_Void_sky"), TEXT("ArenaMaterialHook.Void.Sky"));
}

bool SetTexture(UMaterialInstanceDynamic* MID, UTexture2D* Texture, const TCHAR* ParameterName)
{
	if (!MID || !Texture || !ParameterName || !*ParameterName)
	{
		return false;
	}

	UMaterialInterface* Parent = MID->GetMaterial();
	if (!Parent)
	{
		return false;
	}

	const FName Name(ParameterName);
	TArray<FMaterialParameterInfo> Parameters;
	TArray<FGuid> LayerParameterIds;
	Parent->GetAllTextureParameterInfo(Parameters, LayerParameterIds);
	const bool bHasParameter = Parameters.ContainsByPredicate([Name](const FMaterialParameterInfo& Info)
	{
		return Info.Name == Name;
	});
	if (!bHasParameter)
	{
		return false;
	}

	MID->SetTextureParameterValue(Name, Texture);
	return true;
}

void SetColor(UMaterialInstanceDynamic* MID, const FLinearColor& Color)
{
	if (!MID)
	{
		return;
	}
	// Cover the common parameter names across the materials we use.
	MID->SetVectorParameterValue(TEXT("Color"), Color);
	MID->SetVectorParameterValue(TEXT("Base Color"), Color);
	MID->SetVectorParameterValue(TEXT("BaseColor"), Color);
	MID->SetVectorParameterValue(TEXT("Tint"), Color);
}

} // namespace SpiritsAssets
