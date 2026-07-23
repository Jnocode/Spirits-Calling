#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spirits Calling — 冒煙測試 harness (P0-1)
=========================================
獨立 Python 腳本（用系統 python 跑，非 UE in-editor python）。

用途：把 SHIP_CHECKLIST 的「冒煙測試矩陣」攤成
  A 段：確定性 pre-flight 檢查（自動，秒級，出包前每次跑）
  B 段：手動實測矩陣的結果記錄器（打勾 + 落證據，寫 timestamp+git hash 的結果檔）

用法：
  python smoke_preflight.py                 # 只跑 A 段 pre-flight，並印出 B 段待填矩陣
  python smoke_preflight.py --build         # A 段前先觸發一次 UBT 重編（確認真的綠燈）
  python smoke_preflight.py --record R.json # 讀 B 段結果 JSON，合併 A 段，產出 SMOKE_RESULT_<ts>.md
  python smoke_preflight.py --emit-template  # 產一份 B 段結果 JSON 範本供填寫

退出碼：A 段全部 PASS/WARN → 0；任何 FAIL → 1。B 段有 FAIL → 1。
"""
import os, sys, json, glob, subprocess, datetime, argparse

from readiness_record_writer import attach_validation_reports, build_record, write_record
from readiness_record_validator import validate_scope_file
from audio_validation import build_audio_report
from version_consistency_validator import build_version_report

# 專案根 = 此腳本上兩層（Scripts/ 的父目錄）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SCRIPT_DIR)            # .../Spirits_Calling
ROOT = os.path.dirname(PROJ)                   # .../Spirits-Calling (git root)
VALIDATION_DIR = os.path.join(PROJ, "Saved", "Validation")
AUDIO_REPORT_PATH = os.path.join(VALIDATION_DIR, "audio_validation.json")
VERSION_REPORT_PATH = os.path.join(VALIDATION_DIR, "version_consistency.json")

GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
def _c(tag):
    return {"PASS": GREEN + "PASS" + RST, "FAIL": RED + "FAIL" + RST,
            "WARN": YEL + "WARN" + RST, "SKIP": "SKIP"}.get(tag, tag)

results = []  # list of (name, status, detail)
def check(name, status, detail=""):
    results.append((name, status, detail))
    print(f"  [{_c(status)}] {name}" + (f" — {detail}" if detail else ""))

# ---------------------------------------------------------------- A 段
def preflight(do_build=False):
    print(f"\n=== A 段 pre-flight ===  (proj: {PROJ})\n")

    # A0（可選）觸發 UBT 重編
    if do_build:
        bat = os.path.join(ROOT, "_build_s2s3.bat")
        if os.path.exists(bat):
            print("  觸發 UBT 重編中（可能 2-3 分鐘）...")
            subprocess.run(["cmd", "/c", bat], capture_output=True, text=True)
            # 不信任 wrapper exit code（bat 最後一行 echo 會蓋掉真正的 build errorlevel）；
            # 直接回讀 log 的 EXITCODE 行才是編譯結果的權威。
            _log = os.path.join(ROOT, "_build_log.txt")
            _txt = open(_log, encoding="utf-8", errors="replace").read() if os.path.exists(_log) else ""
            _ok = "EXITCODE=0" in _txt
            check("A0 UBT 重編", "PASS" if _ok else "FAIL",
                  "log EXITCODE=0" if _ok else "log 顯示編譯失敗（見 A1 與 _build_log.txt）")
        else:
            check("A0 UBT 重編", "SKIP", "_build_s2s3.bat 不存在")

    # A1 編譯狀態（讀 build log）
    log = os.path.join(ROOT, "_build_log.txt")
    if os.path.exists(log):
        txt = open(log, encoding="utf-8", errors="replace").read()
        ok = ("Result: Succeeded" in txt) and ("EXITCODE=0" in txt)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(log))
        age = (datetime.datetime.now() - mtime).days
        detail = f"last build {mtime:%Y-%m-%d %H:%M}（{age} 天前）"
        if age > 3:
            detail += " ⚠建議 --build 重編確認"
        check("A1 編譯綠燈", "PASS" if ok else "FAIL", detail)
    else:
        check("A1 編譯綠燈", "FAIL", "_build_log.txt 不存在，請先 --build")

    # A2 音效 inventory/import/cook/ambient。raw WAV 存在本身不等於 import pass。
    os.makedirs(VALIDATION_DIR, exist_ok=True)
    cooked_manifest = os.path.join(VALIDATION_DIR, "package_manifest.json")
    ambient_evidence = os.path.join(VALIDATION_DIR, "ambient_audio.json")
    audio_report = build_audio_report(
        PROJ,
        cooked_manifest=cooked_manifest if os.path.isfile(cooked_manifest) else None,
        ambient_evidence=ambient_evidence if os.path.isfile(ambient_evidence) else None,
    )
    with open(AUDIO_REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(audio_report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    imported = sum(item["importStatus"] == "pass" for item in audio_report["checks"])
    cooked = sum(item["cookStatus"] == "pass" for item in audio_report["checks"])
    check("A2 音效素材", "PASS" if audio_report["status"] == "pass" else "FAIL",
          f"raw/imported/cooked={len(audio_report['checks'])}/{imported}/{cooked}; ambient={audio_report['ambient']['status']}; report={AUDIO_REPORT_PATH}")

    # A3 AI 貼圖（4 文明 + 4 地圖 + 1 store）
    need = {
        "East_pattern":  "RawAssets/AI/Civilizations/East/East_pattern.png",
        "Norse_pattern": "RawAssets/AI/Civilizations/Norse/Norse_pattern.png",
        "Egypt_pattern": "RawAssets/AI/Civilizations/Egypt/Egypt_pattern.png",
        "Cyber_pattern": "RawAssets/AI/Civilizations/Cyber/Cyber_pattern.png",
        "Void_ground":   "RawAssets/AI/Arenas/Void/Arena_Void_ground.png",
        "Void_sky":      "RawAssets/AI/Arenas/Void/Arena_Void_sky.png",
        "Sands_ground":  "RawAssets/AI/Arenas/Sands/Arena_Sands_ground.png",
        "Sands_sky":     "RawAssets/AI/Arenas/Sands/Arena_Sands_sky.png",
        "Store_capsule": "RawAssets/AI/Store/Store_capsule_concept.png",
    }
    miss = [k for k, p in need.items() if not os.path.exists(os.path.join(PROJ, p))]
    check("A3 生成美術貼圖", "PASS" if not miss else "FAIL",
          f"{len(need)-len(miss)}/{len(need)}" + (f"，缺:{miss}" if miss else ""))

    # A4 地圖 umap
    demomap = os.path.join(PROJ, "Content", "Maps", "DemoMap.umap")
    check("A4 主地圖 DemoMap", "PASS" if os.path.exists(demomap) else "FAIL",
          "DemoMap.umap（Sands 走 FArenaStyle runtime，非獨立 umap）")

    # A5 config 完整性
    eng = os.path.join(PROJ, "Config", "DefaultEngine.ini")
    game = os.path.join(PROJ, "Config", "DefaultGame.ini")
    eng_txt = open(eng, encoding="utf-8", errors="replace").read() if os.path.exists(eng) else ""
    game_txt = open(game, encoding="utf-8", errors="replace").read() if os.path.exists(game) else ""
    steam = "OnlineSubsystemSteam" in eng_txt
    version_report = build_version_report(PROJ)
    with open(VERSION_REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(version_report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    check("A5 Steam 子系統設定", "PASS" if steam else "WARN",
          "DefaultEngine.ini [OnlineSubsystemSteam]" if steam else "未設定（上架接成就前要補）")
    check("A5 專案版本號", "PASS" if version_report["status"] == "pass" else "FAIL",
          f"DefaultGame.ini ↔ SpiritsVersion.json: {version_report['status']}; report={VERSION_REPORT_PATH}")

    # A6 打包產物（WARN not FAIL：P0-5 未做時預期為空）
    exes = glob.glob(os.path.join(ROOT, "Builds", "Windows", "**", "*.exe"), recursive=True)
    check("A6 打包產物", "PASS" if exes else "WARN",
          f"{len(exes)} exe in Builds/Windows" if exes else "尚未打包（P0-5 待做）")

    # A7 商店 scope 靜態檢查；只驗證宣告文字，不把它當成人工核准證據。
    scope_path = os.path.join(PROJ, "Docs", "Release", "Release_Materials", "scope.md")
    scope_issues = validate_scope_file(scope_path, PROJ)
    check("A7 商店 scope 宣告", "PASS" if not scope_issues else "FAIL",
          "PC single-player/LAN-friend/PCVR 宣告與非出貨能力排除已通過"
          if not scope_issues else "; ".join(item.message for item in scope_issues))

# ---------------------------------------------------------------- B 段
MATRIX = [
    ("B1 單機-簡單", "單機 簡單難度打到分出勝負，無 crash"),
    ("B2 單機-普通", "單機 普通難度打到分出勝負，無 crash"),
    ("B3 單機-困難", "單機 困難難度打到分出勝負，無 crash"),
    ("B4 LAN-Host+Join", "雙機 LAN：Host+Join，雙方召喚/附身/擊殺/斷線正常"),
    ("B5 PC VR", "PC VR 進出附身、召喚、stat fps≈90"),
    ("B6 30分掛機", "掛機 30 分鐘無 crash / 記憶體無明顯洩漏"),
]

def emit_template(path):
    tmpl = {"records": {k: {"status": "SKIP", "note": ""} for k, _ in MATRIX}}
    json.dump(tmpl, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"B 段範本已產出：{path}\n填 status = PASS/FAIL/SKIP，note 放證據，再 --record 它")

def print_matrix():
    print(f"\n=== B 段手動實測矩陣（每次出包必跑，SHIP_CHECKLIST）===\n")
    for k, d in MATRIX:
        print(f"  [ ] {k}: {d}")
    print("\n  → 實測後 `--emit-template t.json` 填好，再 `--record t.json` 產出結果檔")

def git_hash():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def record(rec_path):
    data = json.load(open(rec_path, encoding="utf-8"))
    recs = data.get("records", {})
    ts = datetime.datetime.now()
    gh = git_hash()
    a_fail = [n for n, s, _ in results if s == "FAIL"]
    b_fail = [k for k in recs if recs[k].get("status") == "FAIL"]
    b_skip = [k for k, _ in MATRIX if recs.get(k, {}).get("status", "SKIP") != "PASS"
              and recs.get(k, {}).get("status", "SKIP") != "FAIL"]
    out = os.path.join(ROOT, f"SMOKE_RESULT_{ts:%Y%m%d_%H%M}.md")
    L = [f"# Spirits Calling 冒煙測試結果",
         f"> 時間：{ts:%Y-%m-%d %H:%M} ｜ git：`{gh}`\n",
         "## A 段 pre-flight（自動）\n",
         "| 檢查 | 結果 | 說明 |", "|------|:----:|------|"]
    for n, s, d in results:
        L.append(f"| {n} | {s} | {d} |")
    L += ["\n## B 段手動矩陣\n", "| 項目 | 結果 | 證據/備註 |", "|------|:----:|------|"]
    for k, desc in MATRIX:
        r = recs.get(k, {"status": "SKIP", "note": ""})
        L.append(f"| {k} {desc} | {r.get('status','SKIP')} | {r.get('note','')} |")
    if a_fail or b_fail:
        verdict = f"🔴 FAIL — A:{a_fail} B:{b_fail}"
        code = 1
    elif b_skip:
        verdict = f"🟡 未完成（B 段尚未全部實測，未測：{b_skip}）— 不可出包/送審"
        code = 1
    else:
        verdict = "🟢 PASS（B 段矩陣全過；A 段 WARN 為已知待辦，出包前確認）"
        code = 0
    L += [f"\n## 判定：{verdict}\n"]
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(f"\n結果檔已寫出：{out}\n判定：{verdict}")

    # Preserve the legacy report, but also emit the canonical release record.
    # Relative evidence paths are resolved from the project root, not Docs/Release.
    release_dir = os.path.join(PROJ, "Docs", "Release")
    readiness_json = os.path.join(release_dir, f"Release_Readiness_Record_{ts:%Y%m%d_%H%M}.json")
    readiness_md = os.path.splitext(readiness_json)[0] + ".md"
    readiness = build_record(results, recs, PROJ, now=ts)
    report_candidates = {
        "closure_report": os.path.join(VALIDATION_DIR, "package_closure.json"),
        "launch_report": os.path.join(VALIDATION_DIR, "package_launch.json"),
        "audio_report": AUDIO_REPORT_PATH,
        "version_report": VERSION_REPORT_PATH,
    }
    readiness = attach_validation_reports(
        readiness, PROJ, now=ts,
        **{key: path for key, path in report_candidates.items() if os.path.isfile(path)},
    )
    readiness_issues = write_record(readiness, readiness_json, readiness_md, base_dir=PROJ)
    print(f"Release_Readiness_Record JSON：{readiness_json}")
    print(f"Release_Readiness_Record Markdown：{readiness_md}")
    if readiness_issues:
        print(f"Readiness validator：BLOCKED/NOT_READY ({len(readiness_issues)} findings)")
    else:
        print(f"Readiness validator：{readiness.get('packageAcceptance', 'blocked').upper()}")
    return 0 if not readiness_issues and readiness.get("packageAcceptance") == "ready" else 1

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--emit-template", metavar="PATH", nargs="?", const="smoke_records.json")
    ap.add_argument("--record", metavar="PATH")
    a = ap.parse_args()

    if a.emit_template:
        emit_template(a.emit_template); return 0

    preflight(do_build=a.build)
    a_fail = [n for n, s, _ in results if s == "FAIL"]
    a_warn = [n for n, s, _ in results if s == "WARN"]
    print(f"\nA 段：{len(results)-len(a_fail)-len(a_warn)} PASS / {len(a_warn)} WARN / {len(a_fail)} FAIL")

    if a.record:
        return record(a.record)
    print_matrix()
    return 1 if a_fail else 0

if __name__ == "__main__":
    sys.exit(main())
