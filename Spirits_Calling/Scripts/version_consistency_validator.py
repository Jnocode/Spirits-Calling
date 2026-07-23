#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare DefaultGame.ini metadata with Config/SpiritsVersion.json."""
from __future__ import annotations

import argparse
import configparser
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "version_consistency"
SECTION = "/Script/EngineSettings.GeneralProjectSettings"
FIELD_MAP = {
    "ProjectVersion": "projectVersion",
    "ProjectName": "projectName",
    "CompanyName": "companyName",
}


def build_version_report(project_root: Path | str, *, execution_mode: str = "live") -> dict[str, Any]:
    root = Path(project_root).resolve()
    ini_path = root / "Config" / "DefaultGame.ini"
    json_path = root / "Config" / "SpiritsVersion.json"
    mode = execution_mode if execution_mode in {"live", "fixture"} else "fixture"
    failures: list[dict[str, str]] = []
    ini_values: dict[str, str] = {}
    metadata: dict[str, Any] = {}

    # strict=False so Unreal's repeated array syntax (e.g. several
    # +DirectoriesToAlwaysCook= lines) does not abort the whole parse with a
    # DuplicateOptionError. The version fields we read occur once, so keeping the
    # last value for any duplicated key does not change their result.
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with ini_path.open(encoding="utf-8-sig") as handle:
            parser.read_file(handle)
        if not parser.has_section(SECTION):
            failures.append({"code": "Version.MissingSection", "message": SECTION})
        else:
            ini_values = dict(parser.items(SECTION))
    except (OSError, configparser.Error) as exc:
        failures.append({"code": "Version.IniLoadError", "message": str(exc)})
    try:
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("version metadata root must be an object")
        metadata = loaded
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        failures.append({"code": "Version.MetadataLoadError", "message": str(exc)})

    comparisons: list[dict[str, Any]] = []
    for ini_key, json_key in FIELD_MAP.items():
        ini_value = str(ini_values.get(ini_key, "")).strip()
        json_value = str(metadata.get(json_key, "")).strip()
        matches = bool(ini_value and json_value and ini_value == json_value)
        comparisons.append({"iniField": ini_key, "metadataField": json_key, "iniValue": ini_value, "metadataValue": json_value, "matches": matches})
        if not matches:
            code = "Version.Mismatch" if ini_value and json_value else "Version.MissingValue"
            failures.append({"code": code, "message": f"{ini_key}={ini_value!r} differs from {json_key}={json_value!r}"})
    display_expected = f"v{metadata.get('projectVersion', '')}" if metadata.get("projectVersion") else ""
    display_actual = str(metadata.get("displayVersion", "")).strip()
    if not display_expected or display_actual != display_expected:
        failures.append({"code": "Version.DisplayMismatch", "message": f"displayVersion={display_actual!r}, expected {display_expected!r}"})
    if str(metadata.get("engineVersion", "")).strip() != "5.8":
        failures.append({"code": "Version.EngineMismatch", "message": "engineVersion must equal 5.8"})

    status = "pass" if mode == "live" and not failures else "blocked" if mode != "live" else "fail"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "reportType": REPORT_TYPE,
        "executionMode": mode,
        "status": status,
        "readinessEligible": status == "pass",
        "projectVersion": str(metadata.get("projectVersion", "")),
        "displayVersion": display_actual,
        "comparisons": comparisons,
        "failures": failures,
        "evidencePaths": [str(ini_path), str(json_path)] if ini_path.is_file() and json_path.is_file() else [str(path) for path in (ini_path, json_path) if path.is_file()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--execution-mode", choices=("live", "fixture"), default="live")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_version_report(args.project_root, execution_mode=args.execution_mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output), "failures": len(report["failures"])}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
