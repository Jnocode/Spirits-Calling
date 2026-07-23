#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ambient live-observation runner (audio gate / Requirement 6.10)
===============================================================
跑 UE automation test `SpiritsCalling.Requirements.Audio.S_Ambient resolves and
documented retrigger fallback fires`，**只有它真的 Result={Success}** 才產出
`Saved/Validation/ambient_audio.json` 的 live 證據。證據絕不手寫。

證據內容（validator audio_validation 消費）：
  executionMode=live, status=pass, assetPath=/Game/Audio/S_Ambient,
  loopEnabled=false（此作品用文件化 retrigger fallback，不是 asset loop flag）,
  fallbackDocumented=true, fallbackEvidencePath=Source/.../ArenaBuilder.cpp（可定位）

失敗／test 不存在／未跑 → 寫 status=blocked（fail-closed），不冒充通過。

用法：
  python ambient_smoke_runner.py                 # 用預設 UE 5.8 路徑跑
  python ambient_smoke_runner.py --engine <root> # 指定引擎根
  python ambient_smoke_runner.py --json          # 印摘要 JSON
"""
import os, sys, re, json, subprocess, argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SCRIPT_DIR)
UPROJECT = os.path.join(PROJ, "Spirits_Calling.uproject")
OUT = os.path.join(PROJ, "Saved", "Validation", "ambient_audio.json")
LOG = os.path.join(PROJ, "Saved", "Logs", "ambient-live.log")
REPORT = os.path.join(PROJ, "Saved", "AmbientLive")

TEST_NAME = ("SpiritsCalling.Requirements.Audio.S_Ambient resolves and "
             "documented retrigger fallback fires")
TEST_FILTER = "SpiritsCalling.Requirements.Audio"
AMBIENT_OBJECT = "/Game/Audio/S_Ambient"
# 文件化 fallback 的可定位證據：ArenaBuilder 的 retrigger 程式碼。
FALLBACK_EVIDENCE_REL = "Source/SpiritsCalling/ArenaBuilder.cpp"


def default_engine():
    return os.environ.get("UE_5_8_ROOT", r"D:\Epic Games\UE_5.8")


def run_automation(engine_root):
    exe = os.path.join(engine_root, "Engine", "Binaries", "Win64",
                       "UnrealEditor-Win64-DebugGame.exe")
    if not os.path.isfile(exe):
        # 退回一般 editor（測試若已編進 Development 也能跑；否則會 No tests matched）
        alt = os.path.join(engine_root, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
        exe = alt if os.path.isfile(alt) else exe
    if not os.path.isfile(exe):
        return None, f"engine editor exe not found under {engine_root}"
    for p in (LOG, REPORT):
        try:
            if os.path.isdir(p):
                import shutil; shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    cmd = [exe, UPROJECT, "-unattended", "-nop4", "-nullrhi", "-nosplash", "-NoSound",
           f"-ExecCmds=Automation RunTests {TEST_FILTER}; Quit",
           f"-ReportExportPath={REPORT}", f"-abslog={LOG}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.isfile(LOG):
        return None, "automation produced no log"
    return open(LOG, encoding="utf-8", errors="replace").read(), None


def parse_result(log_text):
    """回傳 (passed, detail)。只認我們那個 test 的 Result={Success}。"""
    if "No automation tests matched" in log_text:
        return False, "no automation tests matched (test not compiled in this target?)"
    # 找該 test 的完成行
    pat = re.compile(r"Test Completed\. Result=\{(\w+)\} Name=\{S_Ambient resolves")
    m = pat.search(log_text)
    if not m:
        return False, "ambient test completion not found in log"
    return (m.group(1) == "Success"), f"Result={{{m.group(1)}}}"


def write_evidence(passed, detail):
    ok_fallback = os.path.isfile(os.path.join(PROJ, FALLBACK_EVIDENCE_REL))
    if passed and ok_fallback:
        ev = {
            "schemaVersion": 1,
            "reportType": "ambient.live",
            "executionMode": "live",
            "status": "pass",
            "assetPath": AMBIENT_OBJECT,
            "loopEnabled": False,
            "fallbackDocumented": True,
            "fallbackEvidencePath": FALLBACK_EVIDENCE_REL,
            "runEvidencePath": os.path.relpath(LOG, PROJ).replace("\\", "/"),
            "observation": ("live automation: S_Ambient resolved as a runtime USoundBase "
                            "and ArenaBuilder retriggered it across the ~11.2s interval"),
            "detail": detail,
        }
    else:
        ev = {
            "schemaVersion": 1,
            "reportType": "ambient.live",
            "executionMode": "live" if passed else "fixture",
            "status": "blocked",
            "assetPath": AMBIENT_OBJECT,
            "fallbackDocumented": ok_fallback,
            "fallbackEvidencePath": FALLBACK_EVIDENCE_REL if ok_fallback else None,
            "failureReasons": [detail] + ([] if ok_fallback else ["fallback evidence file missing"]),
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=default_engine())
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    log_text, err = run_automation(a.engine)
    if err:
        ev = write_evidence(False, err)
        print(json.dumps({"status": ev["status"], "error": err}, ensure_ascii=False))
        return 1
    passed, detail = parse_result(log_text)
    ev = write_evidence(passed, detail)
    if a.json:
        print(json.dumps({"status": ev["status"], "executionMode": ev["executionMode"], "detail": detail}, ensure_ascii=False))
    else:
        tag = "PASS" if ev["status"] == "pass" else "BLOCKED"
        print(f"[{tag}] ambient live evidence -> {OUT}  ({detail})")
    return 0 if ev["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
