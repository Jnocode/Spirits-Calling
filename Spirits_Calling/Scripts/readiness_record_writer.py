#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build and write Release_Readiness_Record JSON plus a human-readable Markdown view."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import subprocess
from typing import Any, Iterable, Mapping, Optional

try:
    from .readiness_record_validator import (
        AUDIO_CHECK_IDS,
        AUDIO_SOURCE_PATHS,
        AMBIENT_CHECK_ID,
        REQUIRED_RELEASE_GATE_IDS,
        REQUIRED_SCOPE_EXCLUDES,
        REQUIRED_SCOPE_INCLUDES,
        validate_record,
    )
    from .platform_smoke_runner import attach_hardware_evidence as _attach_hardware_evidence
except ImportError:  # Direct execution: python Scripts/readiness_record_writer.py
    from readiness_record_validator import (
        AUDIO_CHECK_IDS,
        AUDIO_SOURCE_PATHS,
        AMBIENT_CHECK_ID,
        REQUIRED_RELEASE_GATE_IDS,
        REQUIRED_SCOPE_EXCLUDES,
        REQUIRED_SCOPE_INCLUDES,
        validate_record,
    )
    from platform_smoke_runner import attach_hardware_evidence as _attach_hardware_evidence

SCHEMA_VERSION = "1.0"
DEFAULT_COOK_MAP = "/Game/Maps/DemoMap"
DEFAULT_PACKAGE_PATH = "Builds/Windows"
DEFAULT_LAUNCH_LOG = "evidence/launch.log"
AUTOMATED_REPORT_GATES = {
    "package_closure": "validation.package_closure",
    "package_launch": "validation.package_launch",
    "audio_validation": "release.audio.imports",
    "version_consistency": "validation.version_consistency",
}
AUTOMATED_GATE_OWNERS = {
    "validation.package_closure": "release-engineering",
    "validation.package_launch": "release-engineering",
    "validation.version_consistency": "release-engineering",
}
VERSION_COMPARISON_FIELDS = {
    "ProjectVersion": "projectVersion",
    "ProjectName": "projectName",
    "CompanyName": "companyName",
}


def _timestamp(value: Optional[dt.datetime] = None) -> str:
    moment = value or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _status(value: Any) -> str:
    normalized = str(value or "not_run").strip().lower()
    return normalized if normalized in {"pass", "fail", "not_run", "blocked"} else "not_run"


def _relative(path: str, project_root: str) -> str:
    return os.path.relpath(path, project_root).replace(os.sep, "/")


def _existing_candidate(candidates: Iterable[str], project_root: str) -> Optional[str]:
    for candidate in candidates:
        if not candidate:
            continue
        absolute = candidate if os.path.isabs(candidate) else os.path.join(project_root, candidate)
        if os.path.exists(absolute):
            return _relative(absolute, project_root)
    return None


def _evidence_path(gate_id: str, detail: str, project_root: str) -> str:
    """Return a stable non-empty path, even when evidence is absent.

    Missing paths remain intentionally unlocatable so the validator fails closed
    instead of turning an unmeasured gate into a pass.
    """
    candidates: list[str] = []
    if gate_id == "preflight.build":
        candidates.extend(["_build_log.txt", "Binaries/Win64/Spirits_Calling.exe", "Saved/Logs/Spirits_Calling.log"])
    elif gate_id == "preflight.audio":
        candidates.extend(["RawAssets/Audio"])
    elif gate_id == "preflight.generated_assets":
        candidates.extend(["RawAssets/AI"])
    elif gate_id == "preflight.map":
        candidates.extend(["Content/Maps/DemoMap.umap"])
    elif gate_id in {"preflight.config", "preflight.version"}:
        candidates.extend(["Config/DefaultGame.ini", "Config/DefaultEngine.ini"])
    elif gate_id == "preflight.package":
        candidates.extend(["Builds/Windows"])
    elif gate_id == "preflight.release_scope":
        candidates.extend(["Docs/Release/Release_Materials/scope.md"])
    if detail:
        for token in re.split(r"[\s,;]+", detail):
            token = token.strip("`'\"()[]")
            if token and ("/" in token or "\\" in token or os.path.exists(os.path.join(project_root, token))):
                candidates.append(token)
    found = _existing_candidate(candidates, project_root)
    return found or f"evidence/missing/{gate_id}.missing"


def _source_revision(project_root: str) -> str:
    try:
        result = subprocess.run(["git", "-C", project_root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
        return result.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _package_version(project_root: str) -> str:
    config_path = os.path.join(project_root, "Config", "DefaultGame.ini")
    try:
        text = open(config_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return "unknown"
    match = re.search(r"^ProjectVersion\s*=\s*(\S+)", text, re.MULTILINE)
    return match.group(1) if match else "unknown"


def _gate_id(name: str, section: str) -> str:
    if section == "A":
        return {
            "A1 編譯綠燈": "preflight.build",
            "A2 音效素材": "preflight.audio",
            "A3 生成美術貼圖": "preflight.generated_assets",
            "A4 主地圖 DemoMap": "preflight.map",
            "A5 Steam 子系統設定": "preflight.config",
            "A5 專案版本號": "preflight.version",
            "A6 打包產物": "preflight.package",
            "A7 商店 scope 宣告": "preflight.release_scope",
        }.get(name, "preflight." + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"))
    return "smoke." + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _release_gate_rows(project_root: str, stamp: str) -> list[dict[str, Any]]:
    """Create explicit, unmeasured non-program release gates.

    These rows intentionally remain ``not_run`` with missing evidence until the
    release owner supplies real approval/material evidence.  Presence of source
    files or runtime code never upgrades one of these gates to pass.
    """
    owners = {
        "release.steam.account_app_id": "steam-release-owner",
        "release.store.capsule_art": "store-art-owner",
        "release.store.screenshots": "store-capture-owner",
        "release.store.trailer": "trailer-owner",
        "release.legal.content_rating": "legal-owner",
        "release.legal.eula_privacy": "legal-owner",
        "release.store.early_access_scope": "release-owner",
        "release.audio.imports": "audio-import-owner",
    }
    rows: list[dict[str, Any]] = []
    for gate_id in REQUIRED_RELEASE_GATE_IDS:
        evidence_path = "Docs/Release/Release_Materials/scope.md" if gate_id == "release.store.early_access_scope" else f"evidence/missing/{gate_id}.missing"
        row: dict[str, Any] = {
            "id": gate_id,
            "owner": owners[gate_id],
            "priority": "P0",
            "status": "not_run",
            "evidencePath": evidence_path,
            "timestamp": stamp,
            "failureReason": "release owner evidence not supplied",
            "resolutionStatus": "open",
        }
        if gate_id == "release.audio.imports":
            checks = []
            for check_id, source in zip(AUDIO_CHECK_IDS, AUDIO_SOURCE_PATHS):
                checks.append({
                    "id": check_id,
                    "source": source,
                    "status": "not_run",
                    "evidencePath": f"evidence/missing/{check_id}.missing",
                    "failureReason": "audio import evidence not supplied",
                })
            checks.append({
                "id": AMBIENT_CHECK_ID,
                "source": "Content/Audio/S_Ambient.uasset",
                "status": "not_run",
                "evidencePath": "evidence/missing/audio.ambient.loop_or_fallback.missing",
                "failureReason": "S_Ambient loop or documented fallback evidence not supplied",
            })
            row["checks"] = checks
        rows.append(row)
    return rows


def _automated_gate_rows(stamp: str) -> list[dict[str, Any]]:
    return [{
        "id": gate_id,
        "owner": AUTOMATED_GATE_OWNERS[gate_id],
        "priority": "P0",
        "status": "not_run",
        "evidencePath": f"evidence/missing/{gate_id}.missing",
        "timestamp": stamp,
        "failureReason": "live validation report not supplied",
        "resolutionStatus": "open",
    } for gate_id in AUTOMATED_GATE_OWNERS]


def _default_stability() -> dict[str, Any]:
    return {
        "status": "not_run",
        "measurementStatus": "not_run",
        "readinessEligible": False,
        "executionMode": "live",
        "evidenceSource": "not-recorded",
        "requestedDurationSeconds": 1800,
        "observedDurationSeconds": 0,
        "queryTimeoutSeconds": 5,
        "maxAllowedHangSeconds": 10,
        "startedAt": "not-recorded",
        "endedAt": "not-recorded",
        "crashDetected": False,
        "crashTimestamp": None,
        "hangDetected": False,
        "maxConsecutiveHangSeconds": 0,
        "queries": [],
        "memory": {
            "atFiveMinutes": {"timestamp": "not-recorded", "privateWorkingSetBytes": None},
            "atEnd": {"timestamp": "not-recorded", "privateWorkingSetBytes": None},
            "growthRatio": None,
            "maxGrowthRatio": 0.2,
            "withinThreshold": False,
        },
        "machine": {"os": "not-recorded", "cpu": "not-recorded", "gpu": "not-recorded", "ram": "not-recorded"},
        "failureReasons": ["stability telemetry has not been run"],
    }


def _load_stability(raw: dict[str, Any], project_root: str) -> Optional[dict[str, Any]]:
    value = raw.get("stability") or raw.get("telemetry")
    if isinstance(value, dict):
        return value
    supplied = raw.get("evidencePath") or raw.get("evidence_path")
    if not supplied:
        return None
    candidate = str(supplied) if os.path.isabs(str(supplied)) else os.path.join(project_root, str(supplied))
    if not os.path.isfile(candidate):
        return None
    try:
        with open(candidate, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _not_run_stability() -> dict[str, Any]:
    """Return an explicit unmeasured stability record; never imply a live pass."""
    return {
        "status": "not_run",
        "measurementStatus": "not_run",
        "readinessEligible": False,
        "executionMode": "fixture",
        "evidenceSource": "evidence/missing/stability.missing",
        "requestedDurationSeconds": 1800,
        "observedDurationSeconds": 0,
        "queryTimeoutSeconds": 5,
        "maxAllowedHangSeconds": 10,
        "startedAt": "not-recorded",
        "endedAt": "not-recorded",
        "crashDetected": False,
        "crashTimestamp": None,
        "hangDetected": False,
        "maxConsecutiveHangSeconds": 0,
        "queries": [],
        "memory": {
            "atFiveMinutes": {"timestamp": "not-recorded", "privateWorkingSetBytes": 0},
            "atEnd": {"timestamp": "not-recorded", "privateWorkingSetBytes": 0},
            "growthRatio": None,
            "maxGrowthRatio": 0.2,
            "withinThreshold": False,
        },
        "machine": {"os": "not-recorded", "cpu": "not-recorded", "gpu": "not-recorded", "ram": "not-recorded"},
        "failureReasons": ["30-minute stability evidence not supplied"],
    }


def build_record(preflight_results: Iterable[tuple[str, str, str]], smoke_records: dict[str, Any], project_root: str, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Convert the legacy smoke harness output into the canonical record."""
    stamp = _timestamp(now)
    project_root = os.path.abspath(project_root)
    gate_rows: list[dict[str, Any]] = []
    smoke_cases: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    sequence = 0
    earliest: Optional[dict[str, Any]] = None
    stability = _default_stability()

    def add_gate(gate_id: str, label: str, raw_status: Any, detail: str, evidence_path: str, section: str) -> None:
        nonlocal sequence, earliest
        status = _status(raw_status)
        gate = {
            "id": gate_id, "owner": "release-engineering", "priority": "P0",
            "status": status, "evidencePath": evidence_path, "timestamp": stamp,
        }
        if status != "pass":
            gate["failureReason"] = detail or ("not measured" if status == "not_run" else "validation failed")
            gate["resolutionStatus"] = "open"
        gate_rows.append(gate)
        evidence.append({"id": gate_id + ".evidence", "path": evidence_path, "kind": section, "description": label})
        exists = os.path.exists(os.path.join(project_root, evidence_path)) if not os.path.isabs(evidence_path) else os.path.exists(evidence_path)
        if status != "pass" or not exists:
            unresolved.append({
                "id": gate_id + ".issue", "gateId": gate_id,
                "reason": (detail or "evidence is not locatable") if status == "pass" else (detail or "gate did not pass"),
                "evidencePath": evidence_path, "resolutionStatus": "open",
            })
        if status in {"fail", "blocked"} and earliest is None:
            earliest = {"sequence": sequence, "step": label, "reason": detail or "validation failed", "logPath": evidence_path, "timestamp": stamp}
        sequence += 1

    for name, raw_status, detail in preflight_results:
        gate_id = _gate_id(name, "A")
        add_gate(gate_id, name, raw_status, detail, _evidence_path(gate_id, detail, project_root), "preflight")

    for name, description in (
        ("B1 單機-簡單", "single-player Easy"), ("B2 單機-普通", "single-player Normal"),
        ("B3 單機-困難", "single-player Hard"), ("B4 LAN-Host+Join", "LAN host and join"),
        ("B5 PC VR", "PCVR smoke"), ("B6 30分掛機", "30-minute stability"),
    ):
        raw = smoke_records.get(name, {}) if isinstance(smoke_records, dict) else {}
        if not isinstance(raw, dict):
            raw = {}
        status = _status(raw.get("status", "not_run"))
        note = str(raw.get("note", "") or "")
        if name == "B6 30分掛機":
            measured = _load_stability(raw, project_root)
            if measured is not None:
                stability = measured
                if status == "pass" and _status(stability.get("status")) != "pass":
                    status = _status(stability.get("status"))
                    note = "; ".join(str(item) for item in stability.get("failureReasons", []) if item) or "stability telemetry did not pass"
            elif status == "pass":
                status = "not_run"
                note = "B6 marked pass without stability telemetry evidence"
        supplied = raw.get("evidencePath") or raw.get("evidence_path")
        path = _existing_candidate([str(supplied)] if supplied else [], project_root)
        if path is None and note:
            path = _existing_candidate([note], project_root)
        gate_id = _gate_id(name, "B")
        path = path or f"evidence/missing/{gate_id}.missing"
        smoke_cases.append({"id": gate_id, "status": status, "evidencePath": path if status == "pass" or path else None, "note": note, "timestamp": stamp})
        add_gate(gate_id, description, status, note, path, "smoke")

    for gate in _release_gate_rows(project_root, stamp) + _automated_gate_rows(stamp):
        gate_rows.append(gate)
        evidence.append({
            "id": gate["id"] + ".evidence",
            "path": gate["evidencePath"],
            "kind": "release",
            "description": gate["id"],
        })
        unresolved.append({
            "id": gate["id"] + ".issue",
            "gateId": gate["id"],
            "reason": gate["failureReason"],
            "evidencePath": gate["evidencePath"],
            "resolutionStatus": gate["resolutionStatus"],
        })

    record: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "packageAcceptance": "blocked",
        "packageVersion": _package_version(project_root),
        "sourceRevision": _source_revision(project_root),
        "engineVersion": "5.8",
        "cookMaps": [DEFAULT_COOK_MAP],
        "platform": "Win64",
        "configuration": "Shipping",
        "ioStore": True,
        "packagePath": DEFAULT_PACKAGE_PATH,
        "launchLog": DEFAULT_LAUNCH_LOG,
        "smokeMatrix": {"cases": smoke_cases},
        "hardwareEvidence": {"schemaVersion": "1.0", "runs": []},
        "gates": gate_rows,
        "evidence": evidence,
        "unresolvedIssues": unresolved,
        "earliestFailure": earliest,
        "machine": (stability.get("machine") if stability.get("status") == "pass" else {"os": "not-recorded", "cpu": "not-recorded", "gpu": "not-recorded", "ram": "not-recorded"}),
        "stability": stability,
        "releaseScope": {
            "documentPath": "Docs/Release/Release_Materials/scope.md",
            "includedCapabilities": list(REQUIRED_SCOPE_INCLUDES),
            "excludedCapabilities": list(REQUIRED_SCOPE_EXCLUDES),
        },
    }
    record = _attach_hardware_evidence(record, [], project_root, now)
    if not unresolved and os.path.exists(os.path.join(project_root, DEFAULT_PACKAGE_PATH)) and os.path.exists(os.path.join(project_root, DEFAULT_LAUNCH_LOG)):
        record["packageAcceptance"] = "ready"
    return record


def attach_hardware_evidence(record: dict[str, Any], raw_runs: Any, project_root: str, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Public writer seam for importing live Quest Link/SteamVR evidence."""
    return _attach_hardware_evidence(record, raw_runs, project_root, now)


def attach_asset_validation(record: dict[str, Any], asset_records: Iterable[dict[str, Any]], *, timestamp: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Attach texture outcomes and fail package acceptance closed on failures.

    The exact source, affected hook, stable failure code, and human reason stay
    in ``assetValidation`` so a release reviewer can locate the failed asset
    without reconstructing the editor audit. Store-only records are retained but
    do not block runtime acceptance.
    """
    updated = copy.deepcopy(record)
    rows = [copy.deepcopy(item) for item in asset_records]
    updated["assetValidation"] = rows
    failures = [item for item in rows if item.get("runtimeReady") is False and item.get("classification") != "store_only"]
    if not failures:
        return updated

    stamp = _timestamp(timestamp)
    gate_id = "asset.texture_validation"
    evidence_path = f"evidence/missing/{gate_id}.missing"
    reason = "; ".join(
        f"{item.get('source')}: {item.get('failureReason')}" for item in failures
    )
    gates = updated.setdefault("gates", [])
    if not any(isinstance(gate, dict) and gate.get("id") == gate_id for gate in gates):
        gates.append({
            "id": gate_id,
            "owner": "asset-pipeline",
            "priority": "P0",
            "status": "blocked",
            "evidencePath": evidence_path,
            "timestamp": stamp,
            "failureReason": reason or "asset validation failed",
            "resolutionStatus": "open",
        })
    unresolved = updated.setdefault("unresolvedIssues", [])
    if not any(isinstance(item, dict) and item.get("gateId") == gate_id for item in unresolved):
        unresolved.append({
            "id": gate_id + ".issue",
            "gateId": gate_id,
            "reason": reason or "asset validation failed",
            "evidencePath": evidence_path,
            "resolutionStatus": "open",
        })
    updated["packageAcceptance"] = "blocked"
    if not isinstance(updated.get("earliestFailure"), dict):
        updated["earliestFailure"] = {
            "step": "texture import validation",
            "reason": reason or "asset validation failed",
            "logPath": evidence_path,
            "timestamp": stamp,
        }
    return updated


def _load_report(path: str, project_root: str) -> tuple[Optional[dict[str, Any]], str, Optional[str]]:
    candidate = path if os.path.isabs(path) else os.path.join(project_root, path)
    relative = _relative(candidate, project_root) if os.path.exists(candidate) else path.replace(os.sep, "/")
    if not os.path.isfile(candidate):
        return None, relative, "report JSON is not locatable"
    try:
        with open(candidate, encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            return None, relative, "report JSON root must be an object"
        return value, relative, None
    except (OSError, ValueError) as exc:
        return None, relative, f"report JSON is malformed: {exc}"


def _report_evidence_locatable(report: Mapping[str, Any], project_root: str) -> bool:
    paths = report.get("evidencePaths")
    if not isinstance(paths, list) or not paths:
        return False
    return all(
        isinstance(path, str) and bool(path.strip()) and os.path.exists(
            path if os.path.isabs(path) else os.path.join(project_root, path)
        )
        for path in paths
    )


def _report_semantics(report_type: str, report: Mapping[str, Any], project_root: str) -> bool:
    def absolute(value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value.strip():
            return None
        return value if os.path.isabs(value) else os.path.join(project_root, value)

    def locatable(value: Any) -> bool:
        candidate = absolute(value)
        return candidate is not None and os.path.exists(candidate)

    def package_has_paks(value: Any) -> bool:
        candidate = absolute(value)
        if candidate is None or not os.path.isdir(candidate):
            return False
        try:
            return os.path.isdir(os.path.join(candidate, "Content", "Paks")) or any(
                os.path.isdir(os.path.join(candidate, child, "Content", "Paks"))
                for child in os.listdir(candidate)
            )
        except OSError:
            return False

    if report_type == "package_closure":
        manifest_path = report.get("ioStoreManifestPath")
        return (
            report.get("valid") is True and report.get("errorCount") == 0 and not report.get("errors")
            and locatable(manifest_path) and str(manifest_path).casefold().endswith((".json", ".list", ".txt"))
            and manifest_path in report.get("evidencePaths", []) and package_has_paks(report.get("packagePath"))
        )
    if report_type == "package_launch":
        signals = report.get("signals")
        process = report.get("process")
        package_path = absolute(report.get("packagePath"))
        executable_path = absolute(report.get("executablePath"))
        try:
            executable_in_package = bool(
                package_path and executable_path
                and os.path.commonpath([package_path, executable_path]) == os.path.abspath(package_path)
            )
        except ValueError:
            executable_in_package = False
        return (
            isinstance(signals, Mapping) and signals.get("ready") is True and not report.get("findings")
            and all(locatable(report.get(field)) for field in ("executablePath", "packagePath", "logPath"))
            and isinstance(executable_path, str) and executable_path.casefold().endswith(".exe")
            and executable_in_package and package_has_paks(report.get("packagePath"))
            and isinstance(process, Mapping) and process.get("started") is True
            and isinstance(process.get("pid"), int) and process["pid"] > 0
            and process.get("terminatedByRunner") is True
        )
    if report_type == "audio_validation":
        checks = report.get("checks")
        ambient = report.get("ambient")
        if not isinstance(checks, list):
            return False
        expected_sources = set(AUDIO_SOURCE_PATHS)
        expected_ids = set(AUDIO_CHECK_IDS)
        return (
            len(checks) == len(expected_sources)
            and {item.get("source") for item in checks if isinstance(item, Mapping)} == expected_sources
            and {item.get("id") for item in checks if isinstance(item, Mapping)} == expected_ids
            and all(
                isinstance(item, Mapping) and item.get("status") == "pass"
                and item.get("inventoryStatus") == "pass" and item.get("importStatus") == "pass"
                and item.get("cookStatus") == "pass"
                and item.get("runtimeObject") == f"/Game/Audio/{os.path.splitext(os.path.basename(str(item.get('source'))))[0]}"
                and item.get("importedAsset") == f"Content/Audio/{os.path.splitext(os.path.basename(str(item.get('source'))))[0]}.uasset"
                and locatable(item.get("source")) and locatable(item.get("importedAsset"))
                for item in checks
            )
            and isinstance(ambient, Mapping) and ambient.get("status") == "pass"
            and locatable(ambient.get("evidencePath"))
        )
    if report_type == "version_consistency":
        comparisons = report.get("comparisons")
        if not isinstance(comparisons, list):
            return False
        by_pair = {
            (item.get("iniField"), item.get("metadataField")): item
            for item in comparisons if isinstance(item, Mapping)
        }
        expected = set(VERSION_COMPARISON_FIELDS.items())
        return set(by_pair) == expected and all(
            item.get("matches") is True
            and isinstance(item.get("iniValue"), str) and bool(item["iniValue"].strip())
            and item.get("iniValue") == item.get("metadataValue")
            for item in by_pair.values()
        ) and report.get("projectVersion") == by_pair[("ProjectVersion", "projectVersion")].get("iniValue") and not report.get("failures")
    return False


def attach_validation_reports(
    record: dict[str, Any],
    project_root: str,
    *,
    closure_report: Optional[str] = None,
    launch_report: Optional[str] = None,
    audio_report: Optional[str] = None,
    version_report: Optional[str] = None,
    now: Optional[dt.datetime] = None,
) -> dict[str, Any]:
    """Ingest locatable live reports without promoting unrelated external gates.

    Successful reports upgrade only their corresponding gate. A failed or
    malformed supplied report blocks acceptance; successful ingestion never
    changes ``packageAcceptance`` to ready.
    """
    updated = copy.deepcopy(record)
    project_root = os.path.abspath(project_root)
    stamp = _timestamp(now)
    supplied = {
        "package_closure": closure_report,
        "package_launch": launch_report,
        "audio_validation": audio_report,
        "version_consistency": version_report,
    }
    gates = updated.setdefault("gates", [])
    evidence = updated.setdefault("evidence", [])
    unresolved = updated.setdefault("unresolvedIssues", [])

    for report_type, path in supplied.items():
        if not path:
            continue
        gate_id = AUTOMATED_REPORT_GATES[report_type]
        report, report_path, load_error = _load_report(path, project_root)
        eligible = bool(
            report is not None
            and report.get("reportType") == report_type
            and report.get("executionMode") == "live"
            and report.get("status") == "pass"
            and report.get("readinessEligible") is True
            and _report_evidence_locatable(report, project_root)
            and _report_semantics(report_type, report, project_root)
        )
        if eligible:
            status = "pass"
            reason = ""
        elif load_error:
            status, reason = "blocked", load_error
        elif report is not None and report.get("executionMode") != "live":
            status, reason = "not_run", "fixture/dry-run report cannot upgrade readiness"
        elif report is not None and report.get("status") == "fail":
            status, reason = "fail", "live validation report failed"
        else:
            status, reason = "blocked", "report does not contain complete locatable live evidence"

        gate = next((item for item in gates if isinstance(item, dict) and item.get("id") == gate_id), None)
        if gate is None:
            gate = {
                "id": gate_id,
                "owner": AUTOMATED_GATE_OWNERS.get(gate_id, "audio-import-owner"),
                "priority": "P0",
            }
            gates.append(gate)
        gate.update({"status": status, "evidencePath": report_path, "timestamp": stamp})
        if status == "pass":
            gate.pop("failureReason", None)
            gate.pop("resolutionStatus", None)
        else:
            gate.update({"failureReason": reason, "resolutionStatus": "open"})

        evidence_id = gate_id + ".report"
        stale_evidence_ids = {evidence_id, gate_id + ".evidence"}
        evidence[:] = [item for item in evidence if not (isinstance(item, dict) and item.get("id") in stale_evidence_ids)]
        evidence.append({"id": evidence_id, "path": report_path, "kind": "validation-report", "description": report_type})
        unresolved[:] = [item for item in unresolved if not (isinstance(item, dict) and item.get("gateId") == gate_id)]
        if status != "pass":
            unresolved.append({
                "id": gate_id + ".issue", "gateId": gate_id, "reason": reason,
                "evidencePath": report_path, "resolutionStatus": "open",
            })
            updated["packageAcceptance"] = "blocked"
            if status in {"fail", "blocked"} and not isinstance(updated.get("earliestFailure"), dict):
                updated["earliestFailure"] = {
                    "step": gate_id, "reason": reason, "logPath": report_path, "timestamp": stamp,
                }

        if report_type == "package_launch":
            matrix = updated.setdefault("smokeMatrix", {}).setdefault("cases", [])
            matrix[:] = [item for item in matrix if not (isinstance(item, dict) and item.get("id") == "package.launch")]
            matrix.append({"id": "package.launch", "status": status, "evidencePath": report_path, "note": reason, "timestamp": stamp})
            if eligible and report is not None:
                launch_log = report.get("logPath")
                if isinstance(launch_log, str) and os.path.exists(launch_log if os.path.isabs(launch_log) else os.path.join(project_root, launch_log)):
                    updated["launchLog"] = _relative(launch_log, project_root) if os.path.isabs(launch_log) else launch_log.replace(os.sep, "/")
                package_path = report.get("packagePath")
                if isinstance(package_path, str) and os.path.exists(package_path if os.path.isabs(package_path) else os.path.join(project_root, package_path)):
                    updated["packagePath"] = _relative(package_path, project_root) if os.path.isabs(package_path) else package_path.replace(os.sep, "/")
        elif report_type == "audio_validation" and report is not None:
            gate["checks"] = [{
                "id": str(item.get("id")),
                "source": str(item.get("source")),
                "status": "pass" if eligible and item.get("status") == "pass" else status,
                "evidencePath": report_path,
                **({"failureReason": reason or "; ".join(item.get("failureReasons", []))} if not eligible else {}),
            } for item in report.get("checks", []) if isinstance(item, Mapping)]
            ambient = report.get("ambient")
            if isinstance(ambient, Mapping):
                gate["checks"].append({
                    "id": AMBIENT_CHECK_ID,
                    "source": "Content/Audio/S_Ambient.uasset",
                    "status": "pass" if eligible and ambient.get("status") == "pass" else status,
                    "evidencePath": report_path,
                    **({"failureReason": reason or "; ".join(ambient.get("failureReasons", []))} if not eligible else {}),
                })
        elif report_type == "version_consistency" and eligible and report is not None:
            updated["packageVersion"] = str(report.get("projectVersion"))
    return updated


def render_markdown(record: dict[str, Any], issues: Optional[list[Any]] = None) -> str:
    def cell(value: Any) -> str:
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")
    lines = ["# Spirits Calling Release Readiness", "", f"- **Package acceptance:** `{record.get('packageAcceptance', 'blocked')}`", f"- **Package version:** `{record.get('packageVersion', '—')}`", f"- **Source revision:** `{record.get('sourceRevision', '—')}`", f"- **Engine/platform/configuration:** `{record.get('engineVersion', '—')}` / `{record.get('platform', '—')}` / `{record.get('configuration', '—')}`", f"- **IoStore:** `{record.get('ioStore', '—')}`", f"- **Package path:** `{record.get('packagePath', '—')}`", f"- **Launch log:** `{record.get('launchLog', '—')}`", "", "## Smoke Matrix", "", "| Case | Status | Evidence |", "|---|---|---|"]
    for case in record.get("smokeMatrix", {}).get("cases", []):
        lines.append(f"| {cell(case.get('id'))} | {cell(case.get('status'))} | `{cell(case.get('evidencePath'))}` |")
    lines += ["", "## Gates", "", "| ID | Owner | Priority | Status | Evidence | Failure / resolution |", "|---|---|---|---|---|---|"]
    for gate in record.get("gates", []):
        detail = gate.get("failureReason", "")
        if gate.get("resolutionStatus"):
            detail += f" ({gate['resolutionStatus']})"
        lines.append(f"| {cell(gate.get('id'))} | {cell(gate.get('owner'))} | {cell(gate.get('priority'))} | {cell(gate.get('status'))} | `{cell(gate.get('evidencePath'))}` | {cell(detail)} |")
    lines += ["", "## Unresolved Issues", ""]
    if record.get("unresolvedIssues"):
        lines += ["| ID | Gate | Reason | Evidence | Resolution |", "|---|---|---|---|---|"]
        for issue in record["unresolvedIssues"]:
            lines.append(f"| {cell(issue.get('id'))} | {cell(issue.get('gateId'))} | {cell(issue.get('reason'))} | `{cell(issue.get('evidencePath'))}` | {cell(issue.get('resolutionStatus'))} |")
    else:
        lines.append("None.")
    lines += ["", "## Earliest Reproducible Failure", "", "```json", json.dumps(record.get("earliestFailure"), ensure_ascii=False, indent=2), "```"]
    if issues:
        lines += ["", "## Validator Findings", ""]
        for issue in issues:
            item = issue.as_dict() if hasattr(issue, "as_dict") else issue
            lines.append(f"- `{item.get('path')}` **{item.get('code')}**: {item.get('message')}")
    return "\n".join(lines) + "\n"


def write_record(record: dict[str, Any], json_path: str, markdown_path: Optional[str] = None, base_dir: Optional[str] = None) -> list[Any]:
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    issues = validate_record(record, base_dir or os.path.dirname(os.path.abspath(json_path)))
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    md_path = markdown_path or os.path.splitext(json_path)[0] + ".md"
    os.makedirs(os.path.dirname(os.path.abspath(md_path)), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(render_markdown(record, issues))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Markdown beside a canonical readiness JSON and validate it")
    parser.add_argument("input", help="canonical readiness JSON")
    parser.add_argument("--json", dest="json_path", help="output JSON path; defaults to input path")
    parser.add_argument("--markdown", dest="markdown_path")
    parser.add_argument("--base-dir")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        record = json.load(handle)
    json_path = args.json_path or args.input
    issues = write_record(record, json_path, args.markdown_path, args.base_dir)
    print(json.dumps({"json": json_path, "markdown": args.markdown_path or os.path.splitext(json_path)[0] + ".md", "valid": not issues, "issues": [item.as_dict() for item in issues]}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
