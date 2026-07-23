# -*- coding: utf-8 -*-
"""
P1-6 接材質 — UE Editor Python 腳本（在編輯器 Python 命令列輸入本檔路徑執行）
============================================================================
做三件事，全程式化、可重跑、寫結果檔到磁碟供 shell 驗證：
  1. 匯入 9 張 AI 貼圖 → /Game/Textures/{Civilizations,Arenas}
  2. 建 M_UnitBody 材質：Color(VectorParameter) → BaseColor；
     PatternTex(TextureSampleParameter2D) * Color * EmissiveStrength → Emissive
  3. 存檔並寫 _p16_result.txt（每項 asset 的 OK/FAIL）

設計原則（見 ComfyUI_Asset_Pipeline.md）：貼圖偏中性，顏色交給引擎，
所以 PatternTex 當 emissive 圖騰疊層、Color 走既有隊色×文明色調。
"""
import unreal
import os
import json

PROJ = r"D:/Workspace/03_Dev_Projects/Spirits-Calling/Spirits_Calling"
RAW = os.path.join(PROJ, "RawAssets", "AI")
MANIFEST = os.path.join(RAW, "asset_manifest.json")
RESULT = os.path.join(PROJ, "_p16_result.txt")

log = []
def rec(tag, msg):
    line = "[%s] %s" % (tag, msg)
    log.append(line)
    unreal.log(line)

# ---------------------------------------------------------------- 1. 匯入貼圖

def load_runtime_manifest():
    try:
        with open(MANIFEST, "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, ValueError) as exc:
        rec("FAIL", "無法讀取 canonical manifest %s: %s" % (MANIFEST, exc))
        return []
    entries = []
    for entry in manifest.get("entries", []):
        if entry.get("cookClass") != "runtime":
            continue
        if not entry.get("hook"):
            rec("FAIL", "缺少 runtime hook: %s" % entry.get("source", "<unknown>"))
            continue
        entries.append(entry)
    return entries


def import_texture(entry):
    source = entry["source"]
    src = os.path.join(PROJ, source.replace("/", os.sep))
    dest_dir = entry["destinationPath"]
    name = entry["destinationName"]
    game_path = entry["runtimePath"]
    if unreal.EditorAssetLibrary.does_asset_exist(game_path):
        rec("SKIP", "%s -> %s [%s]" % (source, game_path, entry["hook"]))
        return unreal.EditorAssetLibrary.load_asset(game_path)
    if not os.path.exists(src):
        rec("FAIL", "來源不存在 %s [hook=%s]" % (source, entry["hook"]))
        return None
    task = unreal.AssetImportTask()
    task.filename = src
    task.destination_path = dest_dir
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if unreal.EditorAssetLibrary.does_asset_exist(game_path):
        rec("OK", "匯入 %s [hook=%s]" % (game_path, entry["hook"]))
        return unreal.EditorAssetLibrary.load_asset(game_path)
    rec("FAIL", "匯入後找不到 %s [hook=%s]" % (game_path, entry["hook"]))
    return None


manifest_entries = load_runtime_manifest()
tex_assets = {}
for entry in manifest_entries:
    tex_assets[entry["id"]] = import_texture(entry)

# ---------------------------------------------------------------- 2. 建材質
MAT_DIR = "/Game/Materials"
MAT_PATH = "%s/M_UnitBody" % MAT_DIR

def build_material():
    if unreal.EditorAssetLibrary.does_asset_exist(MAT_PATH):
        unreal.EditorAssetLibrary.delete_asset(MAT_PATH)
        rec("INFO", "刪除舊 M_UnitBody 重建")
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset("M_UnitBody", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        rec("FAIL", "建材質失敗")
        return None
    MEL = unreal.MaterialEditingLibrary

    # Color 向量參數（C++ SetVectorParameterValue("Color", ...) 對得上）
    color = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -600, -100)
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))

    # PatternTex 貼圖參數（預設 East，C++ 之後 SetTextureParameterValue 換文明）
    pat = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -600, 150)
    pat.set_editor_property("parameter_name", "PatternTex")
    if tex_assets.get("civilization.east.pattern"):
        pat.set_editor_property("texture", tex_assets["civilization.east.pattern"])

    # EmissiveStrength 純量參數
    emis = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -600, 380)
    emis.set_editor_property("parameter_name", "EmissiveStrength")
    emis.set_editor_property("default_value", 2.0)

    # PatternTex.RGB * Color
    mul1 = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -300, 60)
    MEL.connect_material_expressions(pat, "RGB", mul1, "A")
    MEL.connect_material_expressions(color, "", mul1, "B")

    # (PatternTex*Color) * EmissiveStrength
    mul2 = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -120, 150)
    MEL.connect_material_expressions(mul1, "", mul2, "A")
    MEL.connect_material_expressions(emis, "", mul2, "B")

    # 接 material 屬性
    MEL.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(mul2, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(MAT_PATH)
    if unreal.EditorAssetLibrary.does_asset_exist(MAT_PATH):
        rec("OK", "建材質 %s（Color→BaseColor；PatternTex*Color*Emis→Emissive）" % MAT_PATH)
        return mat
    rec("FAIL", "材質存檔後不存在")
    return None

build_material()

ARENA_MAT_PATH = "%s/M_ArenaSurface" % MAT_DIR

def build_arena_material():
    if unreal.EditorAssetLibrary.does_asset_exist(ARENA_MAT_PATH):
        unreal.EditorAssetLibrary.delete_asset(ARENA_MAT_PATH)
        rec("INFO", "刪除舊 M_ArenaSurface 重建")
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset("M_ArenaSurface", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        rec("FAIL", "建 Arena surface 材質失敗")
        return None
    MEL = unreal.MaterialEditingLibrary
    texture = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -500, 0)
    texture.set_editor_property("parameter_name", "Texture")
    color = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -500, 220)
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    multiply = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -180, 80)
    MEL.connect_material_expressions(texture, "RGB", multiply, "A")
    MEL.connect_material_expressions(color, "", multiply, "B")
    MEL.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(ARENA_MAT_PATH)
    if unreal.EditorAssetLibrary.does_asset_exist(ARENA_MAT_PATH):
        rec("OK", "建 Arena surface 材質 %s（Texture→BaseColor）" % ARENA_MAT_PATH)
        return mat
    rec("FAIL", "Arena surface 材質存檔後不存在")
    return None

build_arena_material()

# Required hook audit: missing imported assets are failures, never a silent
# primitive-material pass.  The runtime emits the same stable asset codes.
for entry in manifest_entries:
    if tex_assets.get(entry["id"]) is None:
        rec("FAIL", "Asset.MissingCookReference source=%s hook=%s runtimePath=%s" %
            (entry["source"], entry["hook"], entry["runtimePath"]))
if not unreal.EditorAssetLibrary.does_asset_exist(MAT_PATH):
    rec("FAIL", "Asset.MissingHook hook=BodyMID.PatternTex|SoulShrine.PatternTex material=%s" % MAT_PATH)
if not unreal.EditorAssetLibrary.does_asset_exist(ARENA_MAT_PATH):
    rec("FAIL", "Asset.MissingHook hook=ArenaMaterialHook.* material=%s" % ARENA_MAT_PATH)

# ---------------------------------------------------------------- 3. 寫結果檔
ok = sum(1 for l in log if l.startswith("[OK]"))
skip = sum(1 for l in log if l.startswith("[SKIP]"))
fail = sum(1 for l in log if l.startswith("[FAIL]"))
header = "P1-6 接材質結果  OK=%d SKIP=%d FAIL=%d\n%s\n" % (ok, skip, fail, "=" * 40)
with open(RESULT, "w", encoding="utf-8") as f:
    f.write(header + "\n".join(log) + "\n")
unreal.log("=== P1-6 DONE  OK=%d SKIP=%d FAIL=%d  → %s ===" % (ok, skip, fail, RESULT))
