"""Canonical Generated_Asset manifest, import mapping, and texture validation.

The validation functions in this module are deliberately independent of Unreal.
Editor scripts may provide measured dimensions, while the external validator can
read PNG headers from the source tree.  A manifest entry is runtime-ready only
when its source, hook, dimensions, and cook classification are valid.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "RawAssets" / "AI" / "asset_manifest.json"
GAMEPLAY_TEXTURE_MAX_DIMENSION = 2048
NO_HOOK_ASSIGNED = "no-hook-assigned"
VALID_FAILURE_CODES = {
    "Asset.SourceMissing",
    "Asset.InvalidDimensions",
    "Asset.MissingHook",
    "Asset.DuplicateMapping",
    "Asset.InvalidMapping",
    "Asset.MissingCookReference",
    "Asset.StoreAssetInRuntime",
}

# The order is intentional: it is the stable import/report order.
REQUIRED_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "id": "civilization.east.pattern",
        "source": "RawAssets/AI/Civilizations/East/East_pattern.png",
        "category": "civilization_pattern",
        "runtimePath": "/Game/Textures/Civilizations/East_pattern",
        "destinationPath": "/Game/Textures/Civilizations",
        "destinationName": "East_pattern",
        "hook": "BodyMID.PatternTex|SoulShrine.PatternTex",
    },
    {
        "id": "civilization.norse.pattern",
        "source": "RawAssets/AI/Civilizations/Norse/Norse_pattern.png",
        "category": "civilization_pattern",
        "runtimePath": "/Game/Textures/Civilizations/Norse_pattern",
        "destinationPath": "/Game/Textures/Civilizations",
        "destinationName": "Norse_pattern",
        "hook": "BodyMID.PatternTex|SoulShrine.PatternTex",
    },
    {
        "id": "civilization.egypt.pattern",
        "source": "RawAssets/AI/Civilizations/Egypt/Egypt_pattern.png",
        "category": "civilization_pattern",
        "runtimePath": "/Game/Textures/Civilizations/Egypt_pattern",
        "destinationPath": "/Game/Textures/Civilizations",
        "destinationName": "Egypt_pattern",
        "hook": "BodyMID.PatternTex|SoulShrine.PatternTex",
    },
    {
        "id": "civilization.cyber.pattern",
        "source": "RawAssets/AI/Civilizations/Cyber/Cyber_pattern.png",
        "category": "civilization_pattern",
        "runtimePath": "/Game/Textures/Civilizations/Cyber_pattern",
        "destinationPath": "/Game/Textures/Civilizations",
        "destinationName": "Cyber_pattern",
        "hook": "BodyMID.PatternTex|SoulShrine.PatternTex",
    },
    {
        "id": "arena.void.ground",
        "source": "RawAssets/AI/Arenas/Void/Arena_Void_ground.png",
        "category": "arena_texture",
        "runtimePath": "/Game/Textures/Arenas/Void/Arena_Void_ground",
        "destinationPath": "/Game/Textures/Arenas/Void",
        "destinationName": "Arena_Void_ground",
        "hook": "ArenaMaterialHook.Void.Ground",
    },
    {
        "id": "arena.void.sky",
        "source": "RawAssets/AI/Arenas/Void/Arena_Void_sky.png",
        "category": "arena_texture",
        "runtimePath": "/Game/Textures/Arenas/Void/Arena_Void_sky",
        "destinationPath": "/Game/Textures/Arenas/Void",
        "destinationName": "Arena_Void_sky",
        "hook": "ArenaMaterialHook.Void.Sky",
    },
    {
        "id": "arena.sands.ground",
        "source": "RawAssets/AI/Arenas/Sands/Arena_Sands_ground.png",
        "category": "arena_texture",
        "runtimePath": "/Game/Textures/Arenas/Sands/Arena_Sands_ground",
        "destinationPath": "/Game/Textures/Arenas/Sands",
        "destinationName": "Arena_Sands_ground",
        "hook": "ArenaMaterialHook.Sands.Ground",
    },
    {
        "id": "arena.sands.sky",
        "source": "RawAssets/AI/Arenas/Sands/Arena_Sands_sky.png",
        "category": "arena_texture",
        "runtimePath": "/Game/Textures/Arenas/Sands/Arena_Sands_sky",
        "destinationPath": "/Game/Textures/Arenas/Sands",
        "destinationName": "Arena_Sands_sky",
        "hook": "ArenaMaterialHook.Sands.Sky",
    },
    {
        "id": "store.capsule.concept",
        "source": "RawAssets/AI/Store/Store_capsule_concept.png",
        "category": "store_draft",
        "runtimePath": None,
        "destinationPath": None,
        "destinationName": None,
        "hook": NO_HOOK_ASSIGNED,
    },
)


# Metadata is part of the canonical mapping, not an optional annotation.  Keeping
# it separate from REQUIRED_ASSETS preserves the compact destination mapping while
# allowing validators to reject cross-civilization and cross-arena mutations.
EXPECTED_METADATA: dict[str, dict[str, Any]] = {
    "civilization.east.pattern": {"civilization": "East", "mapStyle": None, "surface": None},
    "civilization.norse.pattern": {"civilization": "Norse", "mapStyle": None, "surface": None},
    "civilization.egypt.pattern": {"civilization": "Egypt", "mapStyle": None, "surface": None},
    "civilization.cyber.pattern": {"civilization": "Cyber", "mapStyle": None, "surface": None},
    "arena.void.ground": {"civilization": None, "mapStyle": "Void", "surface": "ground"},
    "arena.void.sky": {"civilization": None, "mapStyle": "Void", "surface": "sky"},
    "arena.sands.ground": {"civilization": None, "mapStyle": "Sands", "surface": "ground"},
    "arena.sands.sky": {"civilization": None, "mapStyle": "Sands", "surface": "sky"},
    "store.capsule.concept": {"civilization": None, "mapStyle": None, "surface": None},
}
MAPPING_FIELDS = ("source", "category", "runtimePath", "destinationPath", "destinationName", "hook", "cookClass", "civilization", "mapStyle", "surface")


def load_manifest(path: Path | str = MANIFEST_PATH) -> dict[str, Any]:
    """Load a manifest without changing its data or applying implicit defaults."""
    with Path(path).open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("manifest root must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_power_of_two(value: Any) -> bool:
    """Return true only for positive integer powers of two."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0 and (value & (value - 1)) == 0


def read_png_dimensions(path: Path | str) -> tuple[int, int]:
    """Read PNG width/height from its header without requiring Pillow or Unreal."""
    data = Path(path).read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("source is not a readable PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _exception_is_documented(exception: Any) -> bool:
    """Check the local exception marker; readiness evidence is checked separately."""
    if not isinstance(exception, Mapping) or exception.get("documented") is not True:
        return False
    return bool(str(exception.get("exceptionId", "")).strip()) and bool(str(exception.get("evidencePath", "")).strip())


def _readiness_exception_is_recorded(source: str, exception: Any, readiness_record: Mapping[str, Any] | None) -> bool:
    if not _exception_is_documented(exception) or not isinstance(readiness_record, Mapping):
        return False
    exception_id = exception.get("exceptionId")
    records = readiness_record.get("skyboxExceptions", [])
    if not isinstance(records, list):
        return False
    return any(
        isinstance(item, Mapping)
        and item.get("source") == source
        and item.get("exceptionId") == exception_id
        and item.get("documented") is True
        and item.get("status") in {"pass", "approved"}
        and bool(str(item.get("evidencePath", "")).strip())
        for item in records
    )


def validate_texture_dimensions(
    width: Any,
    height: Any,
    *,
    is_skybox: bool = False,
    skybox_exception: Mapping[str, Any] | None = None,
    readiness_recorded: bool = False,
    max_dimension: int = GAMEPLAY_TEXTURE_MAX_DIMENSION,
) -> dict[str, Any]:
    """Validate one texture and return a serializable result.

    Sky textures are not implicitly exempt.  A documented local exception and a
    corresponding readiness-record entry are both required for an over-limit
    skybox.  Callers that already resolved the readiness record may set
    ``readiness_recorded=True``.
    """
    result: dict[str, Any] = {
        "width": width,
        "height": height,
        "powerOfTwo": is_power_of_two(width) and is_power_of_two(height),
        "maxDimension": max_dimension,
        "skyboxExceptionDocumented": False,
        "valid": False,
        "failureCode": None,
        "failureReason": None,
    }
    if not isinstance(width, int) or isinstance(width, bool) or not isinstance(height, int) or isinstance(height, bool) or width <= 0 or height <= 0:
        result["failureCode"] = "Asset.InvalidDimensions"
        result["failureReason"] = "texture width and height must be positive integers"
        return result
    if not result["powerOfTwo"]:
        result["failureCode"] = "Asset.InvalidDimensions"
        result["failureReason"] = f"texture dimensions {width}x{height} are not both powers of two"
        return result
    exception_allowed = is_skybox and _exception_is_documented(skybox_exception) and readiness_recorded
    result["skyboxExceptionDocumented"] = exception_allowed
    if width > max_dimension or height > max_dimension:
        if not exception_allowed:
            result["failureCode"] = "Asset.InvalidDimensions"
            result["failureReason"] = f"texture dimensions {width}x{height} exceed {max_dimension}px without a recorded skybox exception"
            return result
    result["valid"] = True
    return result


def _expected_by_id() -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in REQUIRED_ASSETS}


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _dimensions_for_entry(entry: Mapping[str, Any], source_path: Path, dimensions: Mapping[str, Any] | None) -> tuple[Any, Any] | None:
    validation = entry.get("validation")
    if isinstance(validation, Mapping) and "width" in validation and "height" in validation:
        return validation["width"], validation["height"]
    if dimensions:
        value = dimensions.get(entry.get("source"))
        if value is None:
            value = dimensions.get(entry.get("id"))
        if isinstance(value, Mapping):
            return value.get("width"), value.get("height")
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return value[0], value[1]
    try:
        return read_png_dimensions(source_path)
    except (OSError, ValueError):
        return None


def _asset_validation_record(
    entry: Mapping[str, Any],
    *,
    source_path: Path,
    dimensions: Mapping[str, Any] | None,
    readiness_record: Mapping[str, Any] | None,
    check_sources: bool,
) -> dict[str, Any]:
    source = str(entry.get("source", ""))
    hook = str(entry.get("hook") or NO_HOOK_ASSIGNED)
    expected_entry = _expected_by_id().get(entry.get("id"))
    expected_values: dict[str, Any] = {}
    if expected_entry is not None:
        expected_values.update({field: expected_entry.get(field) for field in MAPPING_FIELDS if field in expected_entry})
        expected_values.update(EXPECTED_METADATA.get(str(entry.get("id")), {}))
        expected_values["cookClass"] = "store_only" if entry.get("id") == "store.capsule.concept" else "runtime"
    else:
        expected_values = {"id": "known canonical asset id"}
    mismatches = [
        field for field, expected_value in expected_values.items()
        if field == "id" or entry.get(field) != expected_value
    ]
    is_expected_store = expected_entry is not None and expected_entry.get("id") == "store.capsule.concept"
    record: dict[str, Any] = {
        "source": source,
        "id": entry.get("id"),
        "runtimePath": entry.get("runtimePath"),
        "hook": hook,
        "runtimeReady": False,
    }
    if "source" in mismatches and check_sources and not source_path.is_file():
        record.update({"failureCode": "Asset.SourceMissing", "failureReason": f"source file does not exist: {source}"})
        return record
    if mismatches:
        record.update({
            "failureCode": "Asset.InvalidMapping",
            "failureReason": "manifest entry does not match canonical mapping fields: " + ", ".join(mismatches),
            "hook": hook if hook.strip() else NO_HOOK_ASSIGNED,
        })
        return record
    if is_expected_store:
        record.update({"classification": "store_only", "runtimeReady": False})
        return record
    # --no-source-check is the mapping-only mode used by the import planner.
    # Do not invent a dimension failure when no measured dimensions were supplied.
    if not check_sources and not isinstance(entry.get("validation"), Mapping) and not dimensions:
        record["runtimeReady"] = True
        return record
    if not hook.strip() or hook == NO_HOOK_ASSIGNED:
        record.update({"failureCode": "Asset.MissingHook", "failureReason": "runtime asset has no affected hook", "hook": NO_HOOK_ASSIGNED})
        return record
    if check_sources and not source_path.is_file():
        record.update({"failureCode": "Asset.SourceMissing", "failureReason": f"source file does not exist: {source}"})
        return record
    measured = _dimensions_for_entry(entry, source_path, dimensions)
    if measured is None:
        record.update({"failureCode": "Asset.InvalidDimensions", "failureReason": "texture dimensions could not be read"})
        return record
    width, height = measured
    exception = entry.get("skyboxException") or entry.get("skybox_exception")
    recorded = _readiness_exception_is_recorded(source, exception, readiness_record)
    result = validate_texture_dimensions(
        width,
        height,
        is_skybox=entry.get("surface") == "sky" or str(entry.get("hook", "")).endswith(".Sky"),
        skybox_exception=exception,
        readiness_recorded=recorded,
    )
    record.update({"width": width, "height": height, "skyboxExceptionDocumented": result["skyboxExceptionDocumented"]})
    if not result["valid"]:
        record.update({"failureCode": result["failureCode"], "failureReason": result["failureReason"]})
        return record
    record["runtimeReady"] = True
    return record


def build_asset_validation_records(
    manifest: Mapping[str, Any],
    project_root: Path | str | None = None,
    *,
    check_sources: bool = True,
    dimensions: Mapping[str, Any] | None = None,
    readiness_record: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return one failure-safe validation record for every manifest entry."""
    root = Path(project_root) if project_root is not None else MANIFEST_PATH.parents[2]
    records = []
    for entry in manifest.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        source_path = root / Path(str(entry.get("source", "")))
        records.append(_asset_validation_record(
            entry,
            source_path=source_path,
            dimensions=dimensions,
            readiness_record=readiness_record,
            check_sources=check_sources,
        ))
    # A duplicated source/id/runtime path is ambiguous even when each copy is
    # individually well-formed.  Mark every affected runtime record not-ready so
    # mutation callers cannot accidentally use one of the duplicates as valid.
    for field in ("id", "source", "runtimePath"):
        values = [record.get(field) for record in records if record.get(field) not in (None, "")]
        duplicates = {value for value in values if values.count(value) > 1}
        for record in records:
            if record.get(field) in duplicates and record.get("classification") != "store_only":
                record.update({
                    "runtimeReady": False,
                    "failureCode": "Asset.DuplicateMapping",
                    "failureReason": f"duplicate manifest {field}: {record.get(field)}",
                })
    return records


def _validate_asset_records(records: Iterable[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        source = record.get("source", "<missing-source>")
        hook = record.get("hook") or NO_HOOK_ASSIGNED
        if not str(source).strip():
            errors.append("Asset.SourceMissing: exact source path is required")
        if not str(hook).strip():
            errors.append(f"Asset.MissingHook: {source} must use {NO_HOOK_ASSIGNED} when no hook is assigned")
        if record.get("runtimeReady") is not True and record.get("classification") != "store_only":
            code = record.get("failureCode")
            reason = record.get("failureReason")
            if code not in VALID_FAILURE_CODES:
                errors.append(f"Asset.ValidationFailureCode: {source} has invalid failure code {code!r}")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"Asset.ValidationFailureReason: {source} requires a non-empty failure reason")
    return errors


def validate_manifest(
    manifest: Mapping[str, Any],
    project_root: Path | str | None = None,
    *,
    check_sources: bool = True,
    dimensions: Mapping[str, Any] | None = None,
    readiness_record: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return stable validation errors; an empty list means canonical and valid."""
    errors: list[str] = []
    expected = _expected_by_id()
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(f"Manifest.SchemaVersion: expected {SCHEMA_VERSION}")
    if manifest.get("manifestId") != "spirits-calling.generated-assets":
        errors.append("Manifest.ManifestId: unexpected manifest id")
    if manifest.get("manifestVersion") != "1.0.0":
        errors.append("Manifest.ManifestVersion: expected 1.0.0")
    if manifest.get("sourceRoot") != "RawAssets/AI":
        errors.append("Manifest.SourceRoot: expected RawAssets/AI")

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return errors + ["Manifest.Entries: expected a list"]
    ids = [entry.get("id") for entry in entries if isinstance(entry, Mapping)]
    sources = [entry.get("source") for entry in entries if isinstance(entry, Mapping)]
    runtime_paths = [entry.get("runtimePath") for entry in entries if isinstance(entry, Mapping) and entry.get("runtimePath") is not None]
    for label, values in (("id", ids), ("source", sources), ("runtimePath", runtime_paths)):
        for value in sorted({value for value in values if values.count(value) > 1}):
            errors.append(f"Manifest.Duplicate{label.title()}: {value}")
    actual_ids = set(ids)
    for missing in sorted(set(expected) - actual_ids):
        errors.append(f"Manifest.MissingEntry: {missing}")
    for unexpected in sorted(actual_ids - set(expected)):
        errors.append(f"Manifest.UnexpectedEntry: {unexpected}")

    root = Path(project_root) if project_root is not None else MANIFEST_PATH.parents[2]
    for entry in entries:
        if not isinstance(entry, Mapping):
            errors.append("Manifest.Entry: expected an object")
            continue
        asset_id = entry.get("id", "<missing-id>")
        expected_entry = expected.get(asset_id)
        if expected_entry is None:
            continue
        for field in ("source", "category", "runtimePath", "destinationPath", "destinationName", "hook"):
            if entry.get(field) != expected_entry[field]:
                errors.append(f"Manifest.Mapping.{asset_id}.{field}: expected {expected_entry[field]!r}, got {entry.get(field)!r}")
        for field, expected_value in EXPECTED_METADATA.get(str(asset_id), {}).items():
            if entry.get(field) != expected_value:
                errors.append(f"Manifest.Metadata.{asset_id}.{field}: expected {expected_value!r}, got {entry.get(field)!r}")
        is_store = asset_id == "store.capsule.concept"
        expected_cook_class = "store_only" if is_store else "runtime"
        if entry.get("cookClass") != expected_cook_class:
            errors.append(f"Manifest.CookClass.{asset_id}: expected {expected_cook_class}")
        import_data = entry.get("import")
        if not isinstance(import_data, Mapping):
            errors.append(f"Manifest.ImportMetadata.{asset_id}: expected an object")
            continue
        if import_data.get("replaceExisting") != (not is_store):
            errors.append(f"Manifest.ReplaceExisting.{asset_id}: invalid idempotent import policy")
        source_hash = import_data.get("sourceHash")
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            errors.append(f"Manifest.SourceHash.{asset_id}: expected SHA-256 hex digest")
        elif any(character not in "0123456789abcdef" for character in source_hash):
            errors.append(f"Manifest.SourceHash.{asset_id}: expected lowercase SHA-256 hex digest")
        if not _is_utc_timestamp(import_data.get("timestampUtc")):
            errors.append(f"Manifest.Timestamp.{asset_id}: expected UTC ISO-8601 timestamp")
        result = import_data.get("result")
        if is_store:
            if result != "store_only_excluded":
                errors.append(f"Manifest.ImportResult.{asset_id}: store asset must be excluded")
        elif result not in {"source_verified", "imported", "reimported", "failed"}:
            errors.append(f"Manifest.ImportResult.{asset_id}: invalid import result")
        if check_sources:
            source_path = root / Path(str(entry.get("source", "")))
            if not source_path.is_file():
                errors.append(f"Asset.SourceMissing: {entry.get('source')}")
            elif isinstance(source_hash, str) and len(source_hash) == 64:
                actual_hash = sha256_file(source_path)
                if actual_hash != source_hash:
                    errors.append(f"Asset.SourceHashMismatch: {entry.get('source')} expected {source_hash}, got {actual_hash}")

    records = build_asset_validation_records(
        manifest,
        root,
        check_sources=check_sources,
        dimensions=dimensions,
        readiness_record=readiness_record,
    )
    errors.extend(_validate_asset_records(records))
    for record in records:
        if record.get("runtimeReady") is False and record.get("classification") != "store_only":
            errors.append(f"{record.get('failureCode')}: {record.get('source')} — {record.get('failureReason')}")
        declared = next((entry for entry in entries if isinstance(entry, Mapping) and entry.get("id") == record.get("id")), None)
        if isinstance(declared, Mapping) and "runtimeReady" in declared and declared.get("runtimeReady") != record.get("runtimeReady"):
            errors.append(f"Asset.RuntimeReadyMismatch: {record.get('source')}")
    return errors


def runtime_entries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return Imported_Asset entries that must be present in a runtime cook.

    Package closure validation uses this seam instead of duplicating the
    manifest's store/runtime classification rules.  Returned entries are
    copies so callers cannot mutate the canonical manifest accidentally.
    """
    return [
        copy.deepcopy(dict(entry))
        for entry in manifest.get("entries", [])
        if isinstance(entry, Mapping)
        and entry.get("cookClass") == "runtime"
        and entry.get("category") != "store_draft"
    ]


def store_only_entries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return assets that must never be added to a runtime cook set."""
    return [
        copy.deepcopy(dict(entry))
        for entry in manifest.get("entries", [])
        if isinstance(entry, Mapping)
        and (entry.get("cookClass") == "store_only" or entry.get("category") == "store_draft")
    ]


def build_import_plan(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    errors = validate_manifest(manifest, check_sources=False)
    if errors:
        raise ValueError("cannot build import plan from invalid manifest: " + "; ".join(errors))
    plan: list[dict[str, Any]] = []
    for entry in manifest["entries"]:
        import_data = entry["import"]
        plan.append({
            "id": entry["id"], "source": entry["source"], "category": entry["category"],
            "runtimePath": entry["runtimePath"], "destinationPath": entry["destinationPath"],
            "destinationName": entry["destinationName"], "hook": entry["hook"],
            "cookClass": entry["cookClass"], "storeOnly": entry["cookClass"] == "store_only",
            "replaceExisting": import_data["replaceExisting"],
        })
    return plan


def mapping_for_source(manifest: Mapping[str, Any], source: str) -> dict[str, Any]:
    matches = [entry for entry in manifest.get("entries", []) if entry.get("source") == source]
    if len(matches) != 1:
        raise KeyError(f"source must resolve to exactly one manifest entry: {source}")
    entry = matches[0]
    return copy.deepcopy({
        "id": entry["id"], "source": entry["source"], "category": entry["category"],
        "runtimePath": entry["runtimePath"], "destinationPath": entry["destinationPath"],
        "destinationName": entry["destinationName"], "hook": entry["hook"],
        "cookClass": entry["cookClass"], "storeOnly": entry["cookClass"] == "store_only",
        "replaceExisting": entry["import"]["replaceExisting"],
    })


def update_import_result(
    manifest: Mapping[str, Any], asset_id: str, result: str, *,
    timestamp_utc: str | None = None, source_hash: str | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(manifest))
    matches = [entry for entry in updated.get("entries", []) if entry.get("id") == asset_id]
    if len(matches) != 1:
        raise KeyError(f"asset id must resolve to exactly one manifest entry: {asset_id}")
    metadata = matches[0]["import"]
    metadata["result"] = result
    metadata["timestampUtc"] = timestamp_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if source_hash is not None:
        metadata["sourceHash"] = source_hash
    return updated


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--no-source-check", action="store_true")
    parser.add_argument("--plan", action="store_true", help="print deterministic import plan as JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        manifest = load_manifest(args.manifest)
        errors = validate_manifest(manifest, project_root=args.project_root, check_sources=not args.no_source_check)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if args.plan:
            print(json.dumps(build_import_plan(manifest), ensure_ascii=False, indent=2))
        else:
            print(f"VALID: {args.manifest} ({len(manifest['entries'])} entries)")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Manifest.Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
