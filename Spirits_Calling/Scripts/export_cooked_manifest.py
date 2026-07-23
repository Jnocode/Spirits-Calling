#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cooked-manifest 導出器
======================
把 UE cook 產出的權威證據轉成 validator 可消費的 JSON manifest。

來源（皆為真 cook 產物，非推導）：
  1. Saved/Cooked/Windows/Spirits_Calling/Metadata/ReferencedSet.txt
     — cooker 寫出的權威 cooked 物件清單（小寫路徑）。
  2. Builds/Windows/SpiritsCalling-PackageMetadata.json
     — build_shipping.ps1 寫的 package metadata（configuration/ioStore/cookMaps/…）。

問題：ReferencedSet 路徑全小寫，但 closure/audio validator 對 /Game/ 路徑
      大小寫敏感。解法：走 Content/ 建 lowercase→canonical 映射，翻譯回正確大小寫。

輸出：Saved/Validation/package_manifest.json
  - cookedObjects：canonical-case /Game 物件路徑（含 /Game/X.X 與 /Game/X 兩種拼法）
  - configuration / projectCodeBuild / ioStore / cookMaps / packagePath：取自 metadata

用法：
  python export_cooked_manifest.py                      # 用預設路徑
  python export_cooked_manifest.py --json               # 印出摘要 JSON
退出碼：成功且有 cooked 物件 → 0；缺 ReferencedSet 或零物件 → 1。
"""
import os, sys, json, argparse, glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SCRIPT_DIR)  # .../Spirits_Calling

REFERENCED_SET = os.path.join(
    PROJ, "Saved", "Cooked", "Windows", "Spirits_Calling", "Metadata", "ReferencedSet.txt")
PACKAGE_METADATA = os.path.join(PROJ, "Builds", "Windows", "SpiritsCalling-PackageMetadata.json")
OUT_PATH = os.path.join(PROJ, "Saved", "Validation", "package_manifest.json")
CONTENT_DIR = os.path.join(PROJ, "Content")


def build_case_map():
    """走 Content/ 建 lowercase /game 物件路徑 → canonical-case 映射。"""
    case_map = {}
    for ext in ("*.uasset", "*.umap"):
        for f in glob.glob(os.path.join(CONTENT_DIR, "**", ext), recursive=True):
            rel = os.path.relpath(f, CONTENT_DIR).replace("\\", "/")
            rel_noext = rel.rsplit(".", 1)[0]           # Audio/S_Alarm
            canonical = "/Game/" + rel_noext             # /Game/Audio/S_Alarm
            case_map[canonical.lower()] = canonical
    return case_map


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--referenced-set", default=REFERENCED_SET)
    ap.add_argument("--package-metadata", default=PACKAGE_METADATA)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.referenced_set):
        print(f"[FAIL] ReferencedSet 不存在（需先 cook）：{a.referenced_set}", file=sys.stderr)
        return 1

    case_map = build_case_map()

    # 讀 ReferencedSet 的 /game/ 物件（小寫）
    cooked_canonical = []
    unmapped = []
    with open(a.referenced_set, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.strip()
            if not p or p.startswith("#") or not p.startswith("/game/"):
                continue
            canonical = case_map.get(p)
            if canonical is None:
                # /game/maps/demomap 這種 umap，或 Content 找不到對應檔（引擎內容例外）
                # 保底：首字母大寫 /Game，其餘保留（validator casefold 的欄位仍可比對）
                canonical = "/Game/" + p[len("/game/"):]
                unmapped.append(p)
            cooked_canonical.append(canonical)

    # 展開成兩種拼法：/Game/X 與 /Game/X.X（UAT 兩種都可能用）
    objects = []
    seen = set()
    for c in cooked_canonical:
        for variant in (c, f"{c}.{c.rsplit('/', 1)[-1]}"):
            if variant not in seen:
                seen.add(variant)
                objects.append(variant)

    # 取 package metadata 欄位
    meta = {}
    if os.path.isfile(a.package_metadata):
        with open(a.package_metadata, encoding="utf-8-sig") as fh:
            meta = json.load(fh)

    manifest = {
        "schemaVersion": 1,
        "generatedFrom": os.path.relpath(a.referenced_set, PROJ).replace("\\", "/"),
        "configuration": meta.get("configuration", "Shipping"),
        "projectCodeBuild": meta.get("projectCodeBuild", True),
        "ioStore": meta.get("ioStore", True),
        "cookMaps": meta.get("cookMaps", ["/Game/Maps/DemoMap"]),
        "packagePath": meta.get("packagePath", os.path.join(PROJ, "Builds", "Windows")),
        "sourceRevision": meta.get("sourceRevision"),
        "cookedObjects": objects,
    }

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    game_count = len(cooked_canonical)
    summary = {
        "out": a.out,
        "cookedGameObjects": game_count,
        "totalEntries": len(objects),
        "unmappedCase": len(unmapped),
    }
    if a.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] cooked-manifest 導出 → {a.out}")
        print(f"     /game 物件 {game_count} 個（含 audio/materials/textures），"
              f"展開 {len(objects)} entries，未映射大小寫 {len(unmapped)}")
    return 0 if game_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
