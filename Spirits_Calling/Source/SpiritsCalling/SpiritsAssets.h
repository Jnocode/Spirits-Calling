#pragma once

#include "CoreMinimal.h"

class UStaticMesh;
class UMaterialInterface;
class UTexture2D;
class UMaterialInstanceDynamic;

/**
 * Central runtime asset references (engine + project content), so the whole
 * art pass works without creating any new .uasset files.
 */
namespace SpiritsAssets
{
	UStaticMesh* Mesh(const TCHAR* Path);
	UMaterialInterface* Material(const TCHAR* Path);

	// Engine basic shapes
	UStaticMesh* Sphere();
	UStaticMesh* Cube();
	UStaticMesh* Cylinder();

	// LevelPrototyping meshes
	UStaticMesh* ChamferCube();
	UStaticMesh* CircularBand();
	UStaticMesh* CircularGlow();
	UStaticMesh* QuarterCylinder();
	UStaticMesh* Plane();

	// Materials
	UMaterialInterface* BasicShapeMaterial(); // param "Color"
	UMaterialInterface* GlowMaterial();       // M_SimpleGlow, param "Color"
	UMaterialInterface* GridMaterialDark();   // MI_PrototypeGrid_TopDark
	UMaterialInterface* GridMaterialGray();   // MI_PrototypeGrid_Gray
	UMaterialInterface* UnitBodyMaterial();    // M_UnitBody with PatternTex hook
	UMaterialInterface* ArenaSurfaceMaterial(); // M_ArenaSurface with Texture hook

	// Canonical generated asset hooks. Missing required assets are logged as
	// explicit failures; callers may keep a prototype visual fallback, but must
	// never treat the hook as resolved when the texture is absent.
	UTexture2D* CivilizationPattern(int32 Civilization);
	UTexture2D* ArenaGroundTexture(int32 MapIndex);
	UTexture2D* ArenaSkyTexture(int32 MapIndex);
	bool SetTexture(class UMaterialInstanceDynamic* MID, UTexture2D* Texture, const TCHAR* ParameterName);
	UTexture2D* LoadRequiredTexture(const TCHAR* Path, const TCHAR* Hook);

	/** Sets the best-guess color parameter on a dynamic material instance. */
	void SetColor(class UMaterialInstanceDynamic* MID, const FLinearColor& Color);
}
