#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import PCVR hardware smoke evidence into Release_Readiness_Record.

This adapter is deliberately an evidence importer, not a hardware simulator.
Fixture data can validate the interchange shape, but it is always downgraded to
``not_run`` and can never produce a hardware ``pass``.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
from typing import Any, Iterable, Optional

ADAPTER_VERSION = "1.0"
VALID_STATUS = {"pass", "fail", "not_run", "blocked"}
VALID_EXECUTION_MODES = {"live", "fixture"}
REQUIRED_ADAPTERS = ("quest_link",)
OPTIONAL_ADAPTERS = ("steamvr",)
REQUIRED_CASES = ("menu", "possession", "summon", "heavy_attack", "return_to_spirit")
MACHINE_FIELDS = ("os", "cpu", "gpu", "ram")
EVIDENCE_FIELDS = ("screenshotPath", "logPath", "videoPath")
NOT_RECORDED = "not-recorded"


def _timestamp(value: Optional[dt.datetime] = None) -> str:
    moment = value or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _status(value: Any) -> str:
    normalized = str(value or "not_run").strip().lower()
    return normalized if normalized in VALID_STATUS else "not_run"


def _adapter(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    aliases = {"questlink": "quest_link", "quest-link": "quest_link", "steam_vr": "steamvr"}
    return aliases.get(normalized, normalized)


def _machine(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {field: str(source.get(field) or NOT_RECORDED).strip() for field in MACHINE_FIELDS}


def _rel_or_none(value: Any, project_root: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    path = os.path.expandvars(os.path.expanduser(str(value)))
    if project_root and os.path.isabs(path):
        try:
            return os.path.relpath(path, project_root).replace(os.sep, "/")
        except ValueError:
            return path
    return path.replace(os.sep, "/")


def _case_rows(raw: Any, execution_mode: str, project_root: Optional[str]) -> list[dict[str, Any]]:
    source: dict[str, Any] = {}
    if isinstance(raw, dict):
        source = raw
    elif isinstance(raw, list):
        source = {str(item.get("id")): item for item in raw if isinstance(item, dict) and item.get("id")}

    rows: list[dict[str, Any]] = []
    for case_id in REQUIRED_CASES:
        item = source.get(case_id, {})
        if not isinstance(item, dict):
            item = {}
        row: dict[str, Any] = {
            "id": case_id,
            "status": _status(item.get("status")),
            "note": str(item.get("note") or "").strip(),
            "screenshotPath": _rel_or_none(item.get("screenshotPath", item.get("screenshot_path")), project_root),
            "logPath": _rel_or_none(item.get("logPath", item.get("log_path")), project_root),
            "videoPath": _rel_or_none(item.get("videoPath", item.get("video_path")), project_root),
        }
        # A fixture is useful for schema tests only. It is never a hardware pass.
        if execution_mode != "live" and row["status"] == "pass":
            row["status"] = "not_run"
            row["note"] = (row["note"] + "; " if row["note"] else "") + "fixture evidence cannot prove hardware"
        rows.append(row)
    return rows


def _has_locatable_evidence(case: dict[str, Any], project_root: Optional[str]) -> bool:
    for field in EVIDENCE_FIELDS:
        path = case.get(field)
        if not path:
            continue
        candidate = path if os.path.isabs(path) else os.path.join(project_root or os.getcwd(), path)
        if os.path.exists(candidate):
            return True
    return False


def normalize_run(raw: Any, project_root: Optional[str] = None, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Normalize one imported run and fail closed on missing hardware prerequisites."""
    source = raw if isinstance(raw, dict) else {}
    adapter = _adapter(source.get("adapter", source.get("runtime")))
    if adapter not in REQUIRED_ADAPTERS + OPTIONAL_ADAPTERS:
        adapter = "quest_link"
    execution_mode = str(source.get("executionMode", source.get("execution_mode", "fixture"))).strip().lower()
    if execution_mode not in VALID_EXECUTION_MODES:
        execution_mode = "fixture"
    hardware_present = source.get("hardwarePresent", source.get("hardware_present"))
    hardware_present = hardware_present if isinstance(hardware_present, bool) else False
    mode = source.get("modeSelection", source.get("mode_selection", {}))
    if not isinstance(mode, dict):
        mode = {}
    selected_mode = str(mode.get("selectedMode", mode.get("selected_mode", source.get("selectedMode", "not-recorded"))) or NOT_RECORDED).strip()
    hmd = str(source.get("hmd", source.get("hmdModel", "not-recorded")) or NOT_RECORDED).strip()
    runtime = str(source.get("runtime", source.get("runtimeName", "not-recorded")) or NOT_RECORDED).strip()
    build_version = str(source.get("buildVersion", source.get("build_version", NOT_RECORDED)) or NOT_RECORDED).strip()
    source_revision = str(source.get("sourceRevision", source.get("source_revision", NOT_RECORDED)) or NOT_RECORDED).strip()
    cases = _case_rows(source.get("cases", source.get("evidence", {})), execution_mode, project_root)
    requested_status = _status(source.get("status"))
    status = requested_status
    reasons: list[str] = []
    if execution_mode != "live":
        if requested_status == "pass":
            reasons.append("fixture evidence cannot prove PCVR hardware")
        status = "not_run" if requested_status == "pass" else requested_status
    machine = _machine(source.get("machine"))
    mode_detected = bool(mode.get("detected", hardware_present))
    missing_hardware = not hardware_present
    missing_profile = hmd == NOT_RECORDED or runtime == NOT_RECORDED
    wrong_mode = selected_mode != "PCVR_Mode"
    if missing_hardware:
        if requested_status == "pass":
            status = "not_run"
        reasons.append("HMD/runtime hardware was not detected")
    if hmd == NOT_RECORDED:
        reasons.append("HMD model is not recorded")
    if runtime == NOT_RECORDED:
        reasons.append("XR runtime is not recorded")
    if wrong_mode:
        reasons.append("mode selection is not PCVR_Mode")
    # A live run with a detected device but incomplete identification/mode
    # evidence is an attempted run that failed validation, never a pass.
    if requested_status == "pass" and execution_mode == "live" and not missing_hardware and (missing_profile or wrong_mode):
        status = "fail"
    if status == "pass":
        if any(case["status"] != "pass" for case in cases):
            status = "fail"
            reasons.append("all five PCVR cases must pass")
        if any(not _has_locatable_evidence(case, project_root) for case in cases):
            status = "fail"
            reasons.append("every passing PCVR case needs locatable screenshot, log, or video evidence")
        if any(not value or value == NOT_RECORDED for value in machine.values()):
            status = "fail"
            reasons.append("OS/CPU/GPU/RAM machine profile is incomplete")
        if build_version == NOT_RECORDED or source_revision == NOT_RECORDED:
            status = "fail"
            reasons.append("build version and source revision metadata are incomplete")
        if not mode_detected:
            status = "fail"
            reasons.append("PCVR mode selection was not detected")
    if status == "not_run" and not reasons:
        reasons.append("hardware run was not executed")

    row: dict[str, Any] = {
        "id": str(source.get("id") or f"pcvr.{adapter}"),
        "adapter": adapter,
        "executionMode": execution_mode,
        "status": status,
        "timestamp": str(source.get("timestamp") or _timestamp(now)),
        "buildVersion": build_version,
        "sourceRevision": source_revision,
        "hmd": hmd,
        "runtime": runtime,
        "hardwarePresent": hardware_present,
        "modeSelection": {
            "selectedMode": selected_mode,
            "detected": mode_detected,
        },
        "machine": machine,
        "cases": cases,
        "evidencePaths": list(dict.fromkeys(
            [
                _rel_or_none(source.get(field), project_root)
                for field in EVIDENCE_FIELDS
                if _rel_or_none(source.get(field), project_root)
            ]
            + [
                _rel_or_none(case.get(field), project_root)
                for case in cases
                for field in EVIDENCE_FIELDS
                if _rel_or_none(case.get(field), project_root)
            ]
        )),
        "failureReasons": reasons,
    }
    # Keep an explicitly failed live run as Fail; never reinterpret it as Pass.
    if requested_status in {"fail", "blocked"} and status == "not_run" and hardware_present:
        row["status"] = requested_status
    return row


def build_hardware_evidence(raw_runs: Any, project_root: Optional[str] = None, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Build canonical hardware evidence, always including the Quest Link row."""
    if isinstance(raw_runs, dict):
        raw_runs = raw_runs.get("runs", [raw_runs])
    if not isinstance(raw_runs, list):
        raw_runs = []
    rows = [normalize_run(item, project_root, now) for item in raw_runs]
    if not any(row["adapter"] == "quest_link" for row in rows):
        rows.insert(0, normalize_run({"id": "pcvr.quest_link", "adapter": "quest_link"}, project_root, now))
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row["adapter"] in seen:
            continue
        seen.add(row["adapter"])
        unique.append(row)
    return {"schemaVersion": ADAPTER_VERSION, "runs": unique}


def attach_hardware_evidence(record: dict[str, Any], raw_runs: Any, project_root: Optional[str] = None, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Attach normalized runs and per-case Smoke_Matrix rows to a readiness record."""
    updated = copy.deepcopy(record)
    evidence = build_hardware_evidence(raw_runs, project_root, now)
    updated["hardwareEvidence"] = evidence
    matrix = updated.setdefault("smokeMatrix", {}).setdefault("cases", [])
    existing_ids = {item.get("id") for item in matrix if isinstance(item, dict)}
    stamp = _timestamp(now)
    for run in evidence["runs"]:
        for case in run["cases"]:
            case_id = f"pcvr.{run['adapter']}.{case['id']}"
            if case_id in existing_ids:
                matrix[:] = [item for item in matrix if item.get("id") != case_id]
            paths = [case.get(field) for field in EVIDENCE_FIELDS if case.get(field)]
            evidence_path = paths[0] if paths else f"evidence/missing/{case_id}.missing"
            matrix.append({
                "id": case_id,
                "status": case["status"],
                "evidencePath": evidence_path,
                "note": case.get("note", ""),
                "timestamp": run.get("timestamp", stamp),
            })
    return updated


def import_hardware_evidence(input_path: str, record_path: Optional[str], output_path: str, project_root: str) -> dict[str, Any]:
    with open(input_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if record_path:
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        output = attach_hardware_evidence(record, payload, project_root)
    else:
        output = build_hardware_evidence(payload, project_root)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Import live Quest Link/SteamVR evidence; fixtures never pass hardware")
    parser.add_argument("--input", required=True, help="hardware run JSON or {runs: [...]} JSON")
    parser.add_argument("--record", help="existing Release_Readiness_Record JSON to augment")
    parser.add_argument("--output", required=True, help="normalized evidence or augmented record JSON")
    parser.add_argument("--project-root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = parser.parse_args()
    output = import_hardware_evidence(args.input, args.record, args.output, os.path.abspath(args.project_root))
    print(json.dumps({"output": args.output, "runs": len(output.get("runs", output.get("hardwareEvidence", {}).get("runs", [])))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
