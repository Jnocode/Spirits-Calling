#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate canonical WAV inventory, imported assets, cook and ambient evidence."""
from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "audio_validation"
AUDIO_NAMES = (
    "S_Alarm", "S_Ambient", "S_Attack", "S_Click", "S_Death",
    "S_Defeat", "S_Hit", "S_Summon", "S_Victory",
)
AMBIENT_OBJECT = "/Game/Audio/S_Ambient"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _wav_metadata(path: Path) -> tuple[Optional[dict[str, int]], Optional[str]]:
    try:
        with wave.open(str(path), "rb") as handle:
            return {
                "channels": handle.getnchannels(),
                "sampleRate": handle.getframerate(),
                "sampleWidthBytes": handle.getsampwidth(),
                "frameCount": handle.getnframes(),
            }, None
    except (OSError, EOFError, wave.Error) as exc:
        return None, str(exc)


def _valid_uasset(path: Path) -> bool:
    """Check Unreal's package tag so arbitrary non-empty bytes cannot prove import."""
    try:
        return path.is_file() and path.read_bytes()[:4] == b"\xc1\x83\x2a\x9e"
    except OSError:
        return False


def _manifest_paths(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        values: list[Any] = []
        for key in ("objects", "cookedObjects", "stagedObjects", "runtimeObjects", "packages", "cookedPackages"):
            section = value.get(key)
            if isinstance(section, Mapping):
                values.extend(section.keys())
            elif isinstance(section, list):
                values.extend(section)
    elif isinstance(value, list):
        values = value
    else:
        values = []
    result: set[str] = set()
    for item in values:
        path = item.get("path", item.get("objectPath", "")) if isinstance(item, Mapping) else item
        if isinstance(path, str) and path.strip():
            normalized = path.strip().replace("\\", "/").removesuffix(".uasset")
            leaf = normalized.rsplit("/", 1)[-1]
            if "." in leaf:
                package_name, object_name = leaf.split(".", 1)
                if package_name == object_name:
                    normalized = normalized.rsplit(".", 1)[0]
            result.add(normalized)
    return result


def _load_json(path: Optional[Path]) -> tuple[Any, Optional[str]]:
    if path is None:
        return None, "evidence not supplied"
    if not path.is_file():
        return None, f"evidence does not exist: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def build_audio_report(
    project_root: Path | str,
    *,
    cooked_manifest: Path | str | None = None,
    ambient_evidence: Path | str | None = None,
    execution_mode: str = "live",
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    mode = execution_mode if execution_mode in {"live", "fixture"} else "fixture"
    cooked_path = Path(cooked_manifest).resolve() if cooked_manifest else None
    ambient_path = Path(ambient_evidence).resolve() if ambient_evidence else None
    cooked_raw, cooked_error = _load_json(cooked_path)
    cooked_objects = _manifest_paths(cooked_raw)
    ambient_raw, ambient_error = _load_json(ambient_path)

    rows: list[dict[str, Any]] = []
    for name in AUDIO_NAMES:
        raw = root / "RawAssets" / "Audio" / f"{name}.wav"
        imported = root / "Content" / "Audio" / f"{name}.uasset"
        metadata, metadata_error = _wav_metadata(raw) if raw.is_file() else (None, "source WAV is missing")
        raw_ok = raw.is_file() and metadata is not None
        imported_ok = _valid_uasset(imported)
        runtime_object = f"/Game/Audio/{name}"
        cooked_ok = runtime_object in cooked_objects
        failures = []
        if not raw_ok:
            failures.append(metadata_error or "source WAV is missing or malformed")
        if not imported_ok:
            failures.append("imported Content/Audio asset is missing or lacks the Unreal package header")
        if not cooked_ok:
            failures.append("runtime audio object is absent from cooked manifest evidence")
        rows.append({
            "id": f"audio.import.{name}",
            "name": name,
            "source": _relative(raw, root),
            "importedAsset": _relative(imported, root),
            "runtimeObject": runtime_object,
            "inventoryStatus": "pass" if raw_ok else "fail",
            "importStatus": "pass" if imported_ok else "blocked",
            "cookStatus": "pass" if cooked_ok else "blocked",
            "status": "pass" if raw_ok and imported_ok and cooked_ok else "blocked",
            "wavMetadata": metadata,
            "failureReasons": failures,
        })

    ambient_live = isinstance(ambient_raw, Mapping) and str(ambient_raw.get("executionMode", "")).lower() == "live"
    ambient_pass = isinstance(ambient_raw, Mapping) and str(ambient_raw.get("status", "")).lower() == "pass"
    ambient_asset = isinstance(ambient_raw, Mapping) and ambient_raw.get("assetPath") in {AMBIENT_OBJECT, AMBIENT_OBJECT + ".S_Ambient"}
    loop_or_fallback = isinstance(ambient_raw, Mapping) and (
        ambient_raw.get("loopEnabled") is True
        or (ambient_raw.get("fallbackDocumented") is True and isinstance(ambient_raw.get("fallbackEvidencePath"), str))
    )
    fallback_locatable = True
    if isinstance(ambient_raw, Mapping) and ambient_raw.get("fallbackDocumented") is True:
        fallback = Path(str(ambient_raw.get("fallbackEvidencePath", "")))
        if not fallback.is_absolute():
            fallback = root / fallback
        fallback_locatable = fallback.is_file()
    ambient_ok = (
        mode == "live" and AMBIENT_OBJECT in cooked_objects and ambient_live and ambient_pass
        and ambient_asset and loop_or_fallback and fallback_locatable and ambient_path is not None and ambient_path.is_file()
    )
    ambient_reasons = []
    if AMBIENT_OBJECT not in cooked_objects:
        ambient_reasons.append("S_Ambient is absent from cooked manifest evidence")
    if ambient_error:
        ambient_reasons.append(f"ambient evidence unavailable or malformed: {ambient_error}")
    elif not ambient_live:
        ambient_reasons.append("ambient evidence is not a live run")
    elif not ambient_pass or not ambient_asset or not loop_or_fallback or not fallback_locatable:
        ambient_reasons.append("ambient evidence does not prove imported S_Ambient loop or locatable documented fallback")

    all_rows_pass = all(row["status"] == "pass" for row in rows)
    status = "pass" if mode == "live" and all_rows_pass and ambient_ok else "blocked"
    evidence_paths = [str(path) for path in (cooked_path, ambient_path) if path is not None and path.is_file()]
    evidence_paths.extend(
        str(root / row[field])
        for row in rows
        for field in ("source", "importedAsset")
        if (root / row[field]).is_file()
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "reportType": REPORT_TYPE,
        "executionMode": mode,
        "status": status,
        "readinessEligible": status == "pass",
        "projectRoot": str(root),
        "checks": rows,
        "ambient": {
            "id": "audio.ambient.loop_or_fallback",
            "assetPath": AMBIENT_OBJECT,
            "status": "pass" if ambient_ok else "blocked",
            "evidencePath": str(ambient_path) if ambient_path else None,
            "failureReasons": ambient_reasons,
        },
        "cookedManifestPath": str(cooked_path) if cooked_path else None,
        "evidencePaths": evidence_paths,
        "failureReasons": [reason for row in rows for reason in row["failureReasons"]] + ambient_reasons,
        "diagnostics": {"cookedManifestError": cooked_error},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cooked-manifest", type=Path)
    parser.add_argument("--ambient-evidence", type=Path)
    parser.add_argument("--execution-mode", choices=("live", "fixture"), default="live")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_audio_report(
        args.project_root, cooked_manifest=args.cooked_manifest,
        ambient_evidence=args.ambient_evidence, execution_mode=args.execution_mode,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output), "checks": len(report["checks"])}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
