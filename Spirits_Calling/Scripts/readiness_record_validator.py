#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation for the versioned Release_Readiness_Record.

This module deliberately uses only the Python standard library.  The JSON schema
is the interchange contract; this validator adds the rules that require the
filesystem and the relationship between gates, evidence, failures and verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = (
    "schemaVersion", "packageAcceptance", "packageVersion", "sourceRevision",
    "engineVersion", "cookMaps", "platform", "configuration", "ioStore",
    "packagePath", "launchLog", "smokeMatrix", "gates", "evidence",
    "unresolvedIssues", "earliestFailure", "machine", "releaseScope",
)
VALID_ACCEPTANCE = {"blocked", "not_ready", "ready"}
VALID_STATUS = {"pass", "fail", "not_run", "blocked"}
VALID_RESOLUTION_STATUS = {"open", "in_progress", "resolved"}

REQUIRED_RELEASE_GATE_IDS = (
    "release.steam.account_app_id",
    "release.store.capsule_art",
    "release.store.screenshots",
    "release.store.trailer",
    "release.legal.content_rating",
    "release.legal.eula_privacy",
    "release.store.early_access_scope",
    "release.audio.imports",
)
AUTOMATED_REPORT_GATES = {
    "validation.package_closure": "package_closure",
    "validation.package_launch": "package_launch",
    "release.audio.imports": "audio_validation",
    "validation.version_consistency": "version_consistency",
}
VERSION_COMPARISON_FIELDS = {
    "ProjectVersion": "projectVersion",
    "ProjectName": "projectName",
    "CompanyName": "companyName",
}
REQUIRED_AUTOMATED_GATE_IDS = tuple(
    gate_id for gate_id in AUTOMATED_REPORT_GATES if gate_id != "release.audio.imports"
)
REQUIRED_SCOPE_INCLUDES = ("PC single-player", "LAN/friend connection", "PCVR")
REQUIRED_SCOPE_EXCLUDES = (
    "public matchmaking",
    "dedicated servers",
    "Nakama authentication",
    "anti-cheat",
)
AUDIO_SOURCE_PATHS = tuple(
    f"RawAssets/Audio/{name}.wav"
    for name in (
        "S_Alarm", "S_Ambient", "S_Attack", "S_Click", "S_Death",
        "S_Defeat", "S_Hit", "S_Summon", "S_Victory",
    )
)
AUDIO_CHECK_IDS = tuple(f"audio.import.{os.path.splitext(os.path.basename(path))[0]}" for path in AUDIO_SOURCE_PATHS)
AMBIENT_CHECK_ID = "audio.ambient.loop_or_fallback"
FORBIDDEN_SCOPE_TERMS = {
    "public matchmaking": ("public matchmaking", "公網配對", "公網多人"),
    "dedicated servers": ("dedicated server", "dedicated servers", "專用伺服器"),
    "Nakama authentication": ("nakama",),
    "anti-cheat": ("anti-cheat", "anti cheat", "反作弊"),
}
SCOPE_EXCLUSION_MARKERS = (
    "not shipped", "not included", "excluded", "not supported", "future", "roadmap",
    "planned", "不包含", "未包含", "不支援", "未出貨", "排除", "開發中",
)
ASSET_FAILURE_CODES = {
    "Asset.SourceMissing", "Asset.InvalidDimensions", "Asset.MissingHook",
    "Asset.DuplicateMapping", "Asset.InvalidMapping", "Asset.MissingCookReference", "Asset.StoreAssetInRuntime",
}
NO_HOOK_ASSIGNED = "no-hook-assigned"


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


def _issue(issues: list[ValidationIssue], path: str, code: str, message: str) -> None:
    issues.append(ValidationIssue(path, code, message))


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _locate(path: Any, base_dir: str) -> bool:
    if not _non_empty(path):
        return False
    candidate = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(candidate):
        candidate = os.path.join(base_dir, candidate)
    return os.path.exists(candidate)


def _require_string(obj: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]) -> None:
    if not _non_empty(obj.get(key)):
        _issue(issues, path, "missing_or_empty", "must be a non-empty string")


def _scope_line_is_exclusion(line: str) -> bool:
    normalized = line.casefold()
    return any(marker.casefold() in normalized for marker in SCOPE_EXCLUSION_MARKERS)


def validate_scope_text(text: Any) -> list[ValidationIssue]:
    """Validate the human-readable shipped-scope declaration.

    The declaration must advertise the three supported modes and phrase every
    non-shipped capability as an exclusion.  This deliberately does not treat
    a mere mention of a roadmap item as a shipped claim.
    """
    issues: list[ValidationIssue] = []
    if not isinstance(text, str) or not text.strip():
        return [ValidationIssue("releaseScope.documentPath", "missing_or_empty", "scope document must contain text")]
    normalized = text.casefold()
    for capability in REQUIRED_SCOPE_INCLUDES:
        if capability.casefold() not in normalized:
            _issue(issues, "releaseScope.documentPath", "missing_scope", f"scope must include {capability}")
    for capability, terms in FORBIDDEN_SCOPE_TERMS.items():
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(term.casefold() in line.casefold() for term in terms) and not _scope_line_is_exclusion(line):
                _issue(
                    issues,
                    f"releaseScope.documentPath.line{line_number}",
                    "forbidden_shipped_claim",
                    f"scope must not present {capability} as shipped",
                )
    return issues


def validate_scope_file(path: str, base_dir: Optional[str] = None) -> list[ValidationIssue]:
    """Read and validate a scope document without inventing release evidence."""
    base = os.path.abspath(base_dir or os.getcwd())
    candidate = path if os.path.isabs(path) else os.path.join(base, path)
    if not os.path.isfile(candidate):
        return [ValidationIssue("releaseScope.documentPath", "unlocatable", "scope document does not exist")]
    try:
        with open(candidate, encoding="utf-8") as handle:
            return validate_scope_text(handle.read())
    except OSError as exc:
        return [ValidationIssue("releaseScope.documentPath", "load_error", str(exc))]


def _validate_release_scope(record: dict[str, Any], base_dir: str, issues: list[ValidationIssue]) -> None:
    scope = record.get("releaseScope")
    if not isinstance(scope, dict):
        _issue(issues, "releaseScope", "type", "must be an object")
        return
    document_path = scope.get("documentPath")
    _require_string(scope, "documentPath", "releaseScope.documentPath", issues)
    includes = scope.get("includedCapabilities")
    excludes = scope.get("excludedCapabilities")
    if not isinstance(includes, list) or any(not _non_empty(item) for item in includes):
        _issue(issues, "releaseScope.includedCapabilities", "missing_or_empty", "must contain non-empty capabilities")
    elif any(required.casefold() not in {str(item).casefold() for item in includes} for required in REQUIRED_SCOPE_INCLUDES):
        _issue(issues, "releaseScope.includedCapabilities", "missing_scope", "must include PC single-player, LAN/friend connection and PCVR")
    if not isinstance(excludes, list) or any(not _non_empty(item) for item in excludes):
        _issue(issues, "releaseScope.excludedCapabilities", "missing_or_empty", "must contain non-empty exclusions")
    elif any(required.casefold() not in {str(item).casefold() for item in excludes} for required in REQUIRED_SCOPE_EXCLUDES):
        _issue(issues, "releaseScope.excludedCapabilities", "missing_exclusion", "must exclude public matchmaking, dedicated servers, Nakama authentication and anti-cheat")
    if _non_empty(document_path):
        issues.extend(validate_scope_file(document_path, base_dir))


def _validate_release_gates(gates: list[dict[str, Any]], base_dir: str, issues: list[ValidationIssue]) -> None:
    by_id = {gate.get("id"): gate for gate in gates if _non_empty(gate.get("id"))}
    for gate_id in REQUIRED_RELEASE_GATE_IDS:
        gate = by_id.get(gate_id)
        if gate is None:
            _issue(issues, "gates", "missing_release_gate", f"required release gate is missing: {gate_id}")
            continue
        if gate.get("priority") != "P0":
            _issue(issues, f"gates[{gate_id}].priority", "invalid_priority", "non-program release gates must be P0")
    audio_gate = by_id.get("release.audio.imports")
    if audio_gate is not None:
        checks = audio_gate.get("checks")
        if not isinstance(checks, list):
            _issue(issues, "gates[release.audio.imports].checks", "missing_or_empty", "audio gate must enumerate nine imports and ambient verification")
            return
        checks_by_source = {item.get("source"): item for item in checks if isinstance(item, dict)}
        check_ids = [item.get("id") for item in checks if isinstance(item, dict)]
        if len(check_ids) != len(set(check_ids)):
            _issue(issues, "gates[release.audio.imports].checks", "duplicate", "audio checks must have unique IDs")
        expected_sources = set(AUDIO_SOURCE_PATHS) | {"Content/Audio/S_Ambient.uasset"}
        actual_sources = {item.get("source") for item in checks if isinstance(item, dict)}
        for source in sorted(actual_sources - expected_sources):
            _issue(issues, "gates[release.audio.imports].checks", "unexpected_audio_check", f"unexpected audio check source: {source}")
        if len(checks) != len(expected_sources):
            _issue(issues, "gates[release.audio.imports].checks", "invalid_count", "audio gate must contain exactly nine WAV checks and one ambient check")
        for source in AUDIO_SOURCE_PATHS:
            item = checks_by_source.get(source)
            if item is None:
                _issue(issues, "gates[release.audio.imports].checks", "missing_audio_check", f"missing audio check: {source}")
                continue
            for key in ("id", "source", "status", "evidencePath"):
                _require_string(item, key, f"gates[release.audio.imports].checks[{source}].{key}", issues)
            if item.get("status") not in VALID_STATUS:
                _issue(issues, f"gates[release.audio.imports].checks[{source}].status", "invalid_status", "invalid audio check status")
            elif item.get("status") == "pass" and not _locate(item.get("evidencePath"), base_dir):
                _issue(issues, f"gates[release.audio.imports].checks[{source}].evidencePath", "unlocatable", "passed audio check needs locatable evidence")
        ambient = next((item for item in checks if isinstance(item, dict) and item.get("id") == AMBIENT_CHECK_ID), None)
        if ambient is None:
            _issue(issues, "gates[release.audio.imports].checks", "missing_ambient_check", "missing S_Ambient loop or documented fallback check")
        else:
            for key in ("id", "source", "status", "evidencePath"):
                _require_string(ambient, key, f"gates[release.audio.imports].checks[{AMBIENT_CHECK_ID}].{key}", issues)
            if ambient.get("status") not in VALID_STATUS:
                _issue(issues, f"gates[release.audio.imports].checks[{AMBIENT_CHECK_ID}].status", "invalid_status", "invalid ambient check status")
            if ambient.get("source") != "Content/Audio/S_Ambient.uasset":
                _issue(issues, f"gates[release.audio.imports].checks[{AMBIENT_CHECK_ID}].source", "invalid_source", "ambient check must identify S_Ambient runtime asset")
            if ambient.get("status") == "pass" and not _locate(ambient.get("evidencePath"), base_dir):
                _issue(issues, f"gates[release.audio.imports].checks[{AMBIENT_CHECK_ID}].evidencePath", "unlocatable", "passed ambient check needs locatable evidence")


def _load_report_evidence(path: Any, base_dir: str) -> Optional[dict[str, Any]]:
    if not _non_empty(path):
        return None
    candidate = path if os.path.isabs(path) else os.path.join(base_dir, path)
    try:
        with open(candidate, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _automated_report_semantics(report_type: str, report: dict[str, Any], base_dir: str) -> bool:
    evidence_paths = report.get("evidencePaths")
    if not isinstance(evidence_paths, list) or not evidence_paths or any(not _locate(path, base_dir) for path in evidence_paths):
        return False

    def absolute(value: Any) -> Optional[str]:
        if not _non_empty(value):
            return None
        return value if os.path.isabs(value) else os.path.join(base_dir, value)

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
            and _locate(manifest_path, base_dir) and str(manifest_path).casefold().endswith((".json", ".list", ".txt"))
            and manifest_path in evidence_paths and package_has_paks(report.get("packagePath"))
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
            isinstance(signals, dict) and signals.get("ready") is True and not report.get("findings")
            and all(_locate(report.get(field), base_dir) for field in ("executablePath", "packagePath", "logPath"))
            and isinstance(executable_path, str) and executable_path.casefold().endswith(".exe")
            and executable_in_package and package_has_paks(report.get("packagePath"))
            and isinstance(process, dict) and process.get("started") is True
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
            and {item.get("source") for item in checks if isinstance(item, dict)} == expected_sources
            and {item.get("id") for item in checks if isinstance(item, dict)} == expected_ids
            and all(
                isinstance(item, dict) and item.get("status") == "pass"
                and item.get("inventoryStatus") == "pass" and item.get("importStatus") == "pass"
                and item.get("cookStatus") == "pass"
                and item.get("runtimeObject") == f"/Game/Audio/{os.path.splitext(os.path.basename(str(item.get('source'))))[0]}"
                and item.get("importedAsset") == f"Content/Audio/{os.path.splitext(os.path.basename(str(item.get('source'))))[0]}.uasset"
                and _locate(item.get("source"), base_dir) and _locate(item.get("importedAsset"), base_dir)
                for item in checks
            )
            and isinstance(ambient, dict) and ambient.get("status") == "pass"
            and _locate(ambient.get("evidencePath"), base_dir)
        )
    if report_type == "version_consistency":
        comparisons = report.get("comparisons")
        if not isinstance(comparisons, list):
            return False
        by_pair = {
            (item.get("iniField"), item.get("metadataField")): item
            for item in comparisons if isinstance(item, dict)
        }
        expected = set(VERSION_COMPARISON_FIELDS.items())
        return set(by_pair) == expected and all(
            item.get("matches") is True
            and isinstance(item.get("iniValue"), str) and bool(item["iniValue"].strip())
            and item.get("iniValue") == item.get("metadataValue")
            for item in by_pair.values()
        ) and report.get("projectVersion") == by_pair[("ProjectVersion", "projectVersion")].get("iniValue") and not report.get("failures")
    return False


def _validate_automated_report_gates(
    gates: list[dict[str, Any]], smoke_cases: list[dict[str, Any]], record: dict[str, Any],
    base_dir: str, issues: list[ValidationIssue],
) -> None:
    by_id = {gate.get("id"): gate for gate in gates if _non_empty(gate.get("id"))}
    for gate_id in REQUIRED_AUTOMATED_GATE_IDS:
        if gate_id not in by_id:
            _issue(issues, "gates", "missing_automated_gate", f"required automated gate is missing: {gate_id}")
    for gate_id, report_type in AUTOMATED_REPORT_GATES.items():
        gate = by_id.get(gate_id)
        if gate is None or gate.get("status") != "pass":
            continue
        report = _load_report_evidence(gate.get("evidencePath"), base_dir)
        if report is None:
            _issue(issues, f"gates[{gate_id}].evidencePath", "invalid_report", "passed automated gate requires a locatable JSON report")
            continue
        if (
            report.get("reportType") != report_type
            or report.get("executionMode") != "live"
            or report.get("status") != "pass"
            or report.get("readinessEligible") is not True
        ):
            _issue(issues, f"gates[{gate_id}]", "fabricated_pass", "only a live readiness-eligible report of the expected type may pass this gate")
            continue
        if not _automated_report_semantics(report_type, report, base_dir):
            _issue(issues, f"gates[{gate_id}]", "incomplete_report", "report semantics or referenced evidence do not prove this gate")
        if report_type == "package_launch":
            launch_case = next((case for case in smoke_cases if case.get("id") == "package.launch"), None)
            if launch_case is None or launch_case.get("status") != "pass" or launch_case.get("evidencePath") != gate.get("evidencePath"):
                _issue(issues, "smokeMatrix", "missing_launch_case", "package launch gate pass requires matching package.launch smoke evidence")
        elif report_type == "version_consistency" and str(report.get("projectVersion", "")) != str(record.get("packageVersion", "")):
            _issue(issues, "packageVersion", "version_mismatch", "record packageVersion must equal the live version consistency report")


def _validate_smoke_matrix(matrix: Any, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    if not isinstance(matrix, dict):
        _issue(issues, "smokeMatrix", "type", "must be an object")
        return []
    cases = matrix.get("cases")
    if not isinstance(cases, list) or not cases:
        _issue(issues, "smokeMatrix.cases", "missing_or_empty", "must contain at least one case")
        return []
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        path = f"smokeMatrix.cases[{index}]"
        if not isinstance(case, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        case_id = case.get("id")
        if not _non_empty(case_id):
            _issue(issues, f"{path}.id", "missing_or_empty", "must be a non-empty string")
        elif case_id in seen:
            _issue(issues, f"{path}.id", "duplicate", f"duplicate smoke case id: {case_id}")
        else:
            seen.add(case_id)
        status = case.get("status")
        if status not in VALID_STATUS:
            _issue(issues, f"{path}.status", "invalid_status", f"expected one of {sorted(VALID_STATUS)}")
        if "evidencePath" in case and case["evidencePath"] is not None and not _non_empty(case["evidencePath"]):
            _issue(issues, f"{path}.evidencePath", "empty", "must be null or a non-empty path")
        valid.append(case)
    return valid


def _validate_hardware_evidence(value: Any, base_dir: str, issues: list[ValidationIssue]) -> None:
    """Validate PCVR evidence and reject fabricated hardware passes."""
    if value is None:
        return
    if not isinstance(value, dict):
        _issue(issues, "hardwareEvidence", "type", "must be an object")
        return
    runs = value.get("runs")
    if not isinstance(runs, list) or not runs:
        _issue(issues, "hardwareEvidence.runs", "missing_or_empty", "must contain at least the Quest Link run")
        return
    seen_adapters: set[str] = set()
    adapters: set[str] = set()
    for index, run in enumerate(runs):
        path = f"hardwareEvidence.runs[{index}]"
        if not isinstance(run, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        adapter = run.get("adapter")
        if adapter not in {"quest_link", "steamvr"}:
            _issue(issues, f"{path}.adapter", "invalid_adapter", "adapter must be quest_link or steamvr")
        else:
            adapters.add(adapter)
            if adapter in seen_adapters:
                _issue(issues, f"{path}.adapter", "duplicate", f"duplicate hardware adapter: {adapter}")
            seen_adapters.add(adapter)
        for key in ("id", "executionMode", "status", "timestamp", "buildVersion", "sourceRevision", "hmd", "runtime"):
            _require_string(run, key, f"{path}.{key}", issues)
        if run.get("executionMode") not in {"live", "fixture"}:
            _issue(issues, f"{path}.executionMode", "invalid", "must be live or fixture")
        if run.get("status") not in VALID_STATUS:
            _issue(issues, f"{path}.status", "invalid_status", "invalid hardware status")
        if not isinstance(run.get("hardwarePresent"), bool):
            _issue(issues, f"{path}.hardwarePresent", "type", "must be boolean")
        machine = run.get("machine")
        if not isinstance(machine, dict):
            _issue(issues, f"{path}.machine", "type", "machine profile is required")
        else:
            for key in ("os", "cpu", "gpu", "ram"):
                _require_string(machine, key, f"{path}.machine.{key}", issues)
        mode = run.get("modeSelection")
        if not isinstance(mode, dict):
            _issue(issues, f"{path}.modeSelection", "type", "mode selection is required")
        else:
            _require_string(mode, "selectedMode", f"{path}.modeSelection.selectedMode", issues)
        cases = run.get("cases")
        if not isinstance(cases, list):
            _issue(issues, f"{path}.cases", "missing_or_empty", "must contain menu, possession, summon, heavy attack and return cases")
            continue
        by_id = {case.get("id"): case for case in cases if isinstance(case, dict)}
        if set(by_id) != {"menu", "possession", "summon", "heavy_attack", "return_to_spirit"}:
            _issue(issues, f"{path}.cases", "incomplete", "must contain exactly the five PCVR smoke cases")
        for case_id in ("menu", "possession", "summon", "heavy_attack", "return_to_spirit"):
            case = by_id.get(case_id)
            if case is None:
                continue
            case_path = f"{path}.cases[{case_id}]"
            if case.get("status") not in VALID_STATUS:
                _issue(issues, f"{case_path}.status", "invalid_status", "invalid case status")
            if case.get("status") == "pass":
                paths = [case.get(field) for field in ("screenshotPath", "logPath", "videoPath")]
                if not any(_locate(item, base_dir) for item in paths):
                    _issue(issues, f"{case_path}", "unlocatable", "passed PCVR case needs locatable screenshot, log or video evidence")
        if run.get("status") == "pass":
            if run.get("executionMode") != "live":
                _issue(issues, f"{path}.status", "fabricated_pass", "fixture evidence cannot pass PCVR hardware")
            if run.get("hardwarePresent") is not True:
                _issue(issues, f"{path}.hardwarePresent", "missing_hardware", "hardware pass requires detected HMD/runtime")
            if run.get("hmd") == "not-recorded" or run.get("runtime") == "not-recorded":
                _issue(issues, f"{path}", "missing_hardware_profile", "hardware pass requires HMD and runtime")
            if not isinstance(mode, dict) or mode.get("selectedMode") != "PCVR_Mode":
                _issue(issues, f"{path}.modeSelection.selectedMode", "wrong_mode", "hardware pass requires PCVR_Mode")
            if not isinstance(machine, dict) or any(not _non_empty(machine.get(key)) or machine.get(key) == "not-recorded" for key in ("os", "cpu", "gpu", "ram")):
                _issue(issues, f"{path}.machine", "hardware_not_recorded", "hardware pass requires OS/CPU/GPU/RAM")
            if any(by_id.get(case_id, {}).get("status") != "pass" for case_id in ("menu", "possession", "summon", "heavy_attack", "return_to_spirit")):
                _issue(issues, f"{path}.cases", "incomplete", "hardware pass requires all five PCVR cases")
    if "quest_link" not in adapters:
        _issue(issues, "hardwareEvidence.runs", "missing_quest_link", "Quest Link must always have a recorded run")
def _validate_gates(gates: Any, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    if not isinstance(gates, list) or not gates:
        _issue(issues, "gates", "missing_or_empty", "must contain at least one gate")
        return []
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for index, gate in enumerate(gates):
        path = f"gates[{index}]"
        if not isinstance(gate, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        gate_id = gate.get("id")
        if not _non_empty(gate_id):
            _issue(issues, f"{path}.id", "missing_or_empty", "must be a non-empty string")
        elif gate_id in seen:
            _issue(issues, f"{path}.id", "duplicate", f"duplicate gate id: {gate_id}")
        else:
            seen.add(gate_id)
        for key in ("owner", "evidencePath", "timestamp"):
            _require_string(gate, key, f"{path}.{key}", issues)
        status = gate.get("status")
        if status not in VALID_STATUS:
            _issue(issues, f"{path}.status", "invalid_status", f"expected one of {sorted(VALID_STATUS)}")
        elif status != "pass":
            _require_string(gate, "failureReason", f"{path}.failureReason", issues)
            if gate.get("resolutionStatus") not in VALID_RESOLUTION_STATUS:
                _issue(issues, f"{path}.resolutionStatus", "invalid_status", "failed gates require open, in_progress or resolved")
        elif "resolutionStatus" in gate and gate.get("resolutionStatus") not in VALID_RESOLUTION_STATUS:
            _issue(issues, f"{path}.resolutionStatus", "invalid_status", "expected open, in_progress or resolved")
        if "priority" in gate and gate["priority"] not in {"P0", "P1", "P2"}:
            _issue(issues, f"{path}.priority", "invalid_priority", "expected P0, P1 or P2")
        valid.append(gate)
    return valid


def _validate_evidence(evidence: Any, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    if not isinstance(evidence, list):
        _issue(issues, "evidence", "type", "must be an array")
        return []
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for index, item in enumerate(evidence):
        path = f"evidence[{index}]"
        if not isinstance(item, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        for key in ("id", "path"):
            _require_string(item, key, f"{path}.{key}", issues)
        item_id = item.get("id")
        if _non_empty(item_id) and item_id in seen:
            _issue(issues, f"{path}.id", "duplicate", f"duplicate evidence id: {item_id}")
        elif _non_empty(item_id):
            seen.add(item_id)
        valid.append(item)
    return valid


def _validate_issues(unresolved: Any, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    if not isinstance(unresolved, list):
        _issue(issues, "unresolvedIssues", "type", "must be an array")
        return []
    valid: list[dict[str, Any]] = []
    for index, item in enumerate(unresolved):
        path = f"unresolvedIssues[{index}]"
        if not isinstance(item, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        for key in ("id", "gateId", "reason", "evidencePath", "resolutionStatus"):
            _require_string(item, key, f"{path}.{key}", issues)
        if item.get("resolutionStatus") not in VALID_RESOLUTION_STATUS:
            _issue(issues, f"{path}.resolutionStatus", "invalid_status", "expected open, in_progress or resolved")
        valid.append(item)
    return valid


def _validate_asset_validation(value: Any, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    """Validate texture outcomes and return the records that block readiness."""
    if value is None:
        return []
    if not isinstance(value, list):
        _issue(issues, "assetValidation", "type", "must be an array")
        return []
    failed: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for index, item in enumerate(value):
        path = f"assetValidation[{index}]"
        if not isinstance(item, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        _require_string(item, "source", f"{path}.source", issues)
        _require_string(item, "hook", f"{path}.hook", issues)
        if item.get("hook") == "":
            _issue(issues, f"{path}.hook", "missing_or_empty", f"use {NO_HOOK_ASSIGNED} when no hook is assigned")
        source = item.get("source")
        if _non_empty(source) and source in seen_sources:
            _issue(issues, f"{path}.source", "duplicate", f"duplicate asset validation source: {source}")
        elif _non_empty(source):
            seen_sources.add(source)
        if not isinstance(item.get("runtimeReady"), bool):
            _issue(issues, f"{path}.runtimeReady", "type", "must be boolean")
            continue
        is_store_only = item.get("classification") == "store_only"
        if item.get("runtimeReady") is False and not is_store_only:
            failed.append(item)
            code = item.get("failureCode")
            if code not in ASSET_FAILURE_CODES:
                _issue(issues, f"{path}.failureCode", "invalid_failure_code", "failed assets require a stable Asset.* failure code")
            _require_string(item, "failureReason", f"{path}.failureReason", issues)
            if item.get("hook") in (None, ""):
                _issue(issues, f"{path}.hook", "missing_or_empty", f"failed assets require an affected hook or {NO_HOOK_ASSIGNED}")
        elif item.get("runtimeReady") is True and item.get("failureCode"):
            _issue(issues, f"{path}.failureCode", "contradictory", "runtime-ready assets cannot have a failure code")
    return failed


def _validate_skybox_exceptions(value: Any, base: str, issues: list[ValidationIssue]) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        _issue(issues, "skyboxExceptions", "type", "must be an array")
        return
    for index, item in enumerate(value):
        path = f"skyboxExceptions[{index}]"
        if not isinstance(item, dict):
            _issue(issues, path, "type", "must be an object")
            continue
        for key in ("exceptionId", "source", "evidencePath"):
            _require_string(item, key, f"{path}.{key}", issues)
        if item.get("documented") is not True:
            _issue(issues, f"{path}.documented", "not_documented", "skybox exception must be explicitly documented")
        if item.get("status") not in {"pass", "approved", "fail", "not_run", "blocked"}:
            _issue(issues, f"{path}.status", "invalid_status", "invalid skybox exception status")
        if item.get("status") in {"pass", "approved"} and not _locate(item.get("evidencePath"), base):
            _issue(issues, f"{path}.evidencePath", "unlocatable", "approved skybox exception needs locatable evidence")



def _validate_stability(stability: Any, issues: list[ValidationIssue]) -> dict[str, Any]:
    """Validate stability evidence and fail closed when measurements are absent."""
    if not isinstance(stability, dict):
        _issue(issues, "stability", "type", "must be an object")
        return {}
    status = stability.get("status")
    measurement_status = stability.get("measurementStatus")
    if status not in VALID_STATUS:
        _issue(issues, "stability.status", "invalid_status", "invalid stability status")
    if measurement_status not in VALID_STATUS:
        _issue(issues, "stability.measurementStatus", "invalid_status", "invalid measurement status")
    mode = stability.get("executionMode")
    if mode not in {"live", "fixture"}:
        _issue(issues, "stability.executionMode", "invalid", "must be live or fixture")
    if stability.get("queryTimeoutSeconds") != 5:
        _issue(issues, "stability.queryTimeoutSeconds", "invalid", "query timeout must be exactly 5 seconds")
    if stability.get("maxAllowedHangSeconds") != 10:
        _issue(issues, "stability.maxAllowedHangSeconds", "invalid", "maximum continuous hang must be 10 seconds")
    for key in ("startedAt", "endedAt", "evidenceSource"):
        _require_string(stability, key, f"stability.{key}", issues)
    reasons = stability.get("failureReasons")
    if not isinstance(reasons, list) or any(not _non_empty(item) for item in reasons):
        _issue(issues, "stability.failureReasons", "missing_or_empty", "must contain non-empty reasons")

    queries = stability.get("queries")
    if not isinstance(queries, list):
        _issue(issues, "stability.queries", "type", "must be an array")
    else:
        for index, query in enumerate(queries):
            path = f"stability.queries[{index}]"
            if not isinstance(query, dict):
                _issue(issues, path, "type", "must be an object")
                continue
            _require_string(query, "timestamp", f"{path}.timestamp", issues)
            latency = query.get("latencySeconds")
            if not isinstance(latency, (int, float)) or latency < 0 or latency > 5:
                _issue(issues, f"{path}.latencySeconds", "query_timeout", "each query must respond within 5 seconds")
            if query.get("responded") is not True:
                _issue(issues, f"{path}.responded", "unresponsive", "every input/state query must respond")

    memory = stability.get("memory")
    if not isinstance(memory, dict):
        _issue(issues, "stability.memory", "type", "must be an object")
    else:
        for key in ("atFiveMinutes", "atEnd"):
            reading = memory.get(key)
            path = f"stability.memory.{key}"
            if not isinstance(reading, dict):
                _issue(issues, path, "missing", "private working set reading is required")
                continue
            _require_string(reading, "timestamp", f"{path}.timestamp", issues)
            value = reading.get("privateWorkingSetBytes")
            if not isinstance(value, int) or value < 0:
                _issue(issues, f"{path}.privateWorkingSetBytes", "missing", "private working set bytes are required")
        if memory.get("maxGrowthRatio") != 0.2:
            _issue(issues, "stability.memory.maxGrowthRatio", "invalid", "memory growth threshold must be 20 percent")
        growth = memory.get("growthRatio")
        if growth is not None and not isinstance(growth, (int, float)):
            _issue(issues, "stability.memory.growthRatio", "invalid", "growth ratio must be numeric or null")

    machine = stability.get("machine")
    if not isinstance(machine, dict):
        _issue(issues, "stability.machine", "type", "actual machine profile is required")
    else:
        for key in ("os", "cpu", "gpu", "ram"):
            _require_string(machine, key, f"stability.machine.{key}", issues)

    if status == "pass":
        if mode != "live" or stability.get("readinessEligible") is not True:
            _issue(issues, "stability.status", "fabricated_pass", "only a live run with actual machine telemetry may pass")
        if stability.get("requestedDurationSeconds", 0) < 1800 or stability.get("observedDurationSeconds", 0) < 1800:
            _issue(issues, "stability.duration", "incomplete", "pass requires a complete 1800 second run")
        if stability.get("crashDetected") is not False or stability.get("hangDetected") is not False:
            _issue(issues, "stability.status", "runtime_failure", "crash or continuous hang prevents pass")
        if stability.get("maxConsecutiveHangSeconds", 0) > 10:
            _issue(issues, "stability.maxConsecutiveHangSeconds", "hang_timeout", "continuous hang exceeded 10 seconds")
        if not isinstance(memory, dict) or memory.get("withinThreshold") is not True or memory.get("growthRatio") is None:
            _issue(issues, "stability.memory", "threshold_not_proven", "5 minute and ending memory evidence must prove the 20 percent limit")
        if not isinstance(machine, dict) or any(not _non_empty(machine.get(key)) or machine.get(key) == "not-recorded" for key in ("os", "cpu", "gpu", "ram")):
            _issue(issues, "stability.machine", "hardware_not_recorded", "pass requires actual OS/CPU/GPU/RAM values")
    return stability


def validate_record(record: Any, base_dir: Optional[str] = None) -> list[ValidationIssue]:
    """Return all contract/invariant violations; an empty list means valid."""
    issues: list[ValidationIssue] = []
    base = os.path.abspath(base_dir or os.getcwd())
    if not isinstance(record, dict):
        return [ValidationIssue("$", "type", "record must be a JSON object")]

    for key in REQUIRED_FIELDS:
        if key not in record:
            _issue(issues, key, "missing", "required field is missing")
    if record.get("schemaVersion") != SCHEMA_VERSION:
        _issue(issues, "schemaVersion", "invalid", f"must equal {SCHEMA_VERSION}")
    if record.get("packageAcceptance") not in VALID_ACCEPTANCE:
        _issue(issues, "packageAcceptance", "invalid", f"expected one of {sorted(VALID_ACCEPTANCE)}")
    for key in ("packageVersion", "sourceRevision", "packagePath", "launchLog", "platform", "configuration"):
        _require_string(record, key, key, issues)
    if record.get("engineVersion") != "5.8":
        _issue(issues, "engineVersion", "invalid", "must be the locked UE 5.8 toolchain")
    if record.get("ioStore") is not True:
        _issue(issues, "ioStore", "disabled", "IoStore must be true for an accepted Shipping package")
    maps = record.get("cookMaps")
    if not isinstance(maps, list) or not maps or any(not _non_empty(item) for item in maps):
        _issue(issues, "cookMaps", "missing_or_empty", "must contain at least one non-empty map path")
    elif "/Game/Maps/DemoMap" not in maps:
        _issue(issues, "cookMaps", "missing_required_map", "must include /Game/Maps/DemoMap")
    machine = record.get("machine")
    if not isinstance(machine, dict):
        _issue(issues, "machine", "type", "must be an object")
    else:
        for key in ("os", "cpu", "gpu", "ram"):
            _require_string(machine, key, f"machine.{key}", issues)

    stability = _validate_stability(record.get("stability"), issues)
    smoke_cases = _validate_smoke_matrix(record.get("smokeMatrix"), issues)
    _validate_hardware_evidence(record.get("hardwareEvidence"), base, issues)
    gates = _validate_gates(record.get("gates"), issues)
    _validate_release_gates(gates, base, issues)
    _validate_automated_report_gates(gates, smoke_cases, record, base, issues)
    _validate_release_scope(record, base, issues)
    evidence = _validate_evidence(record.get("evidence"), issues)
    unresolved = _validate_issues(record.get("unresolvedIssues"), issues)
    failed_assets = _validate_asset_validation(record.get("assetValidation"), issues)
    _validate_skybox_exceptions(record.get("skyboxExceptions"), base, issues)

    earliest = record.get("earliestFailure")
    if earliest is not None:
        if not isinstance(earliest, dict):
            _issue(issues, "earliestFailure", "type", "must be null or an object")
        else:
            for key in ("step", "reason", "logPath"):
                _require_string(earliest, key, f"earliestFailure.{key}", issues)
            if _non_empty(earliest.get("logPath")) and not _locate(earliest["logPath"], base):
                _issue(issues, "earliestFailure.logPath", "unlocatable", "failure log path does not exist")

    gate_ids = {gate.get("id") for gate in gates if _non_empty(gate.get("id"))}
    failed_gates = [gate for gate in gates if gate.get("status") in {"fail", "blocked"}]
    failed_smoke = [case for case in smoke_cases if case.get("status") in {"fail", "blocked"}]
    failed_steps = failed_gates + failed_smoke + failed_assets
    if failed_assets and record.get("assetValidation") is not None and not isinstance(earliest, dict):
        _issue(issues, "earliestFailure", "missing", "failed asset validation requires earliest step, reason and logPath")
    if failed_steps and not isinstance(earliest, dict):
        _issue(issues, "earliestFailure", "missing", "failed validation requires earliest step, reason and logPath")
    for index, gate in enumerate(gates):
        evidence_path = gate.get("evidencePath")
        if _non_empty(evidence_path) and not _locate(evidence_path, base):
            _issue(issues, f"gates[{index}].evidencePath", "unlocatable", "gate evidence path does not exist")
    for index, item in enumerate(evidence):
        if _non_empty(item.get("path")) and not _locate(item["path"], base):
            _issue(issues, f"evidence[{index}].path", "unlocatable", "evidence path does not exist")
    for index, case in enumerate(smoke_cases):
        if case.get("status") == "pass" and not _locate(case.get("evidencePath"), base):
            _issue(issues, f"smokeMatrix.cases[{index}].evidencePath", "unlocatable", "passed smoke case needs locatable evidence")

    p0_ids = {gate.get("id") for gate in gates if gate.get("priority", "P0") == "P0" and gate.get("status") != "pass"}
    issue_gate_ids = {item.get("gateId") for item in unresolved}
    for gate_id in sorted(p0_ids - issue_gate_ids):
        _issue(issues, "unresolvedIssues", "missing_p0_issue", f"P0 gate {gate_id} needs an unresolved issue")
    if record.get("packageAcceptance") == "ready":
        if stability.get("status") != "pass":
            _issue(issues, "stability.status", "not_ready", "ready requires a passing live 30-minute stability run")
        if record.get("configuration") != "Shipping":
            _issue(issues, "configuration", "not_shipping", "ready requires Shipping configuration")
        if record.get("platform") != "Win64":
            _issue(issues, "platform", "unsupported", "ready requires Win64 platform")
        if not _locate(record.get("packagePath"), base):
            _issue(issues, "packagePath", "unlocatable", "ready requires a locatable package path")
        if not _locate(record.get("launchLog"), base):
            _issue(issues, "launchLog", "unlocatable", "ready requires a locatable launch log")
        if any(gate.get("status") != "pass" for gate in gates):
            _issue(issues, "gates", "not_all_pass", "ready requires every gate to pass")
        if not evidence:
            _issue(issues, "evidence", "missing_or_empty", "ready requires at least one evidence record")
        if any(case.get("status") != "pass" for case in smoke_cases):
            _issue(issues, "smokeMatrix", "not_all_pass", "ready requires every smoke case to pass")
        if failed_assets:
            _issue(issues, "assetValidation", "runtime_not_ready", "ready requires every runtime asset validation to pass")
        if any(not _locate(case.get("evidencePath"), base) for case in smoke_cases):
            _issue(issues, "smokeMatrix", "evidence_unlocatable", "ready requires locatable evidence for every smoke case")
        if unresolved:
            _issue(issues, "unresolvedIssues", "not_empty", "ready requires no unresolved issue")
        if earliest is not None:
            _issue(issues, "earliestFailure", "unexpected", "ready record cannot contain an earliest failure")
    return issues


def is_ready(record: Any, base_dir: Optional[str] = None) -> bool:
    return isinstance(record, dict) and record.get("packageAcceptance") == "ready" and not validate_record(record, base_dir)


def _infer_project_root(record_path: str) -> str:
    """Find the nearest ancestor containing a .uproject, or use the record directory."""
    record_dir = os.path.dirname(os.path.abspath(record_path))
    candidate = record_dir
    while True:
        try:
            if any(
                entry.lower().endswith(".uproject") and os.path.isfile(os.path.join(candidate, entry))
                for entry in os.listdir(candidate)
            ):
                return candidate
        except OSError:
            pass
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return record_dir
        candidate = parent


def load_and_validate(path: str, base_dir: Optional[str] = None) -> tuple[dict[str, Any], list[ValidationIssue]]:
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    evidence_base = os.path.abspath(base_dir) if base_dir else _infer_project_root(path)
    return record, validate_record(record, evidence_base)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Release_Readiness_Record")
    parser.add_argument("record", help="path to Release_Readiness_Record JSON")
    parser.add_argument("--base-dir", help="base directory for relative evidence paths")
    args = parser.parse_args()
    try:
        record, issues = load_and_validate(args.record, args.base_dir)
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "issues": [{"path": "$", "code": "load_error", "message": str(exc)}]}, ensure_ascii=False, indent=2))
        return 1
    ready = record.get("packageAcceptance") == "ready" and not issues
    print(json.dumps({"valid": not issues, "ready": ready, "issues": [item.as_dict() for item in issues]}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
