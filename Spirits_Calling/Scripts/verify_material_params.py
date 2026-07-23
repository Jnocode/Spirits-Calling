# -*- coding: utf-8 -*-
"""
驗證 M_UnitBody / M_ArenaSurface 暴露的參數名是否對得上 C++ 的 hook。
C++ 端：UnitBase/SoulShrine 用 SetTextureParameterValue("PatternTex")、
        SpiritsAssets::SetColor 用 "Color"/"Base Color"/"BaseColor"/"Tint"。
名字對不上 = 靜默失效，紋樣/顏色永遠上不了身。
結果寫 _matparam_result.txt 供 shell 驗證。
"""
import unreal, os

PROJ = r"D:/Workspace/03_Dev_Projects/Spirits-Calling/Spirits_Calling"
RESULT = os.path.join(PROJ, "_matparam_result.txt")
out = []

def check_mat(path, expect_vector, expect_scalar, expect_texture):
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        out.append("[FAIL] 材質不存在 %s" % path); return
    mat = unreal.EditorAssetLibrary.load_asset(path)
    MEL = unreal.MaterialEditingLibrary
    vparams = list(MEL.get_vector_parameter_names(mat))
    sparams = list(MEL.get_scalar_parameter_names(mat))
    tparams = list(MEL.get_texture_parameter_names(mat))
    out.append("--- %s ---" % path)
    out.append("  vector:  %s" % vparams)
    out.append("  scalar:  %s" % sparams)
    out.append("  texture: %s" % tparams)
    for p in expect_vector:
        out.append(("[OK] " if p in vparams else "[FAIL] ") + "vector param '%s'" % p)
    for p in expect_scalar:
        out.append(("[OK] " if p in sparams else "[FAIL] ") + "scalar param '%s'" % p)
    for p in expect_texture:
        out.append(("[OK] " if p in tparams else "[FAIL] ") + "texture param '%s'" % p)

# M_UnitBody: C++ 需要 Color(vector) + PatternTex(texture) + EmissiveStrength(scalar)
check_mat("/Game/Materials/M_UnitBody", ["Color"], ["EmissiveStrength"], ["PatternTex"])

# 每個文明 pattern texture 能否載入
out.append("--- civ pattern textures ---")
for name in ["East_pattern", "Norse_pattern", "Egypt_pattern", "Cyber_pattern"]:
    p = "/Game/Textures/Civilizations/%s" % name
    ok = unreal.EditorAssetLibrary.does_asset_exist(p) and unreal.EditorAssetLibrary.load_asset(p) is not None
    out.append(("[OK] " if ok else "[FAIL] ") + "load %s" % p)

fails = sum(1 for l in out if l.startswith("[FAIL]"))
oks = sum(1 for l in out if l.startswith("[OK]"))
header = "Material param verify  OK=%d FAIL=%d\n%s\n" % (oks, fails, "=" * 40)
open(RESULT, "w", encoding="utf-8").write(header + "\n".join(out) + "\n")
unreal.log("=== MATPARAM DONE OK=%d FAIL=%d -> %s ===" % (oks, fails, RESULT))
