#!/usr/bin/env python3
"""Static cooked-package closure and runtime/store classification validator.

The validator deliberately consumes exported/staged data instead of attempting
 to inspect Unreal's binary containers itself.  BuildCookRun may export a JSON
 staged manifest, while the IoStore seam accepts either that JSON or a text
 package listing.  No result is inferred from source-code or editor assets:
 required runtime objects must be present in the staged/cooked set.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .asset_manifest_validator import MANIFEST_PATH, load_manifest, runtime_entries, store_only_entries
except ImportError:  # direct execution: python Scripts/package_closure_validator.py
    from asset_manifest_validator import MANIFEST_PATH, load_manifest, runtime_entries, store_only_entries

DEMO_MAP = "/Game/Maps/DemoMap"
RUNTIME_OUTPUT_PREFIX = "Builds/Windows"
REQUIRED_CLASSES = (
    "SpiritsGameMode",
    "SpiritsGameState",
    "SpiritsPlayerController",
    "SpiritPawn",
    "SpiritVRPawn",
)
# These are logical roots.  A package exporter can replace them with concrete
# object paths through requiredRoots/requiredClasses without changing this tool.
DEFAULT_ROOTS = (
    {"path": DEMO_MAP, "kind": "map"},
    {"path": "PCVRMenu", "kind": "asset"},
    {"path": "AchievementFallback", "kind": "asset"},
)
AUDIO_RUNTIME_PATHS = tuple(
    f"/Game/Audio/{name}"
    for name in (
        "S_Alarm", "S_Ambient", "S_Attack", "S_Click", "S_Death",
        "S_Defeat", "S_Hit", "S_Summon", "S_Victory",
    )
)
MISSING_CODES = {"map": "Package.MissingMap", "class": "Package.MissingClass", "asset": "Package.MissingAsset"}


@dataclass(frozen=True)
class ClosureIssue:
    """A stable, serializable validation finding."""

    path: str
    code: str
    message: str
    reference: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"path": self.path, "code": self.code, "message": self.message}
        if self.reference is not None:
            result["reference"] = self.reference
        return result

    def __str__(self) -> str:
        return f"{self.code}: {self.path} — {self.message}"


def _issue(issues: list[ClosureIssue], path: str, code: str, message: str, reference: str | None = None) -> None:
    issues.append(ClosureIssue(path, code, message, reference))


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _path_variants(value: Any) -> set[str]:
    """Return exact and normalized spellings used by package exporters."""
    if not isinstance(value, str) or not value.strip():
        return set()
    raw = value.strip().replace("\\", "/")
    variants = {raw, raw.rstrip("/")}
    # UAT exports may use either a package extension or the generated
    # ``/Package/Asset.Asset`` spelling for the same cooked object.
    if raw.endswith((".uasset", ".umap")):
        variants.add(raw.rsplit(".", 1)[0])
    if "/" in raw and raw.rsplit("/", 1)[-1].count(".") == 1:
        package, object_name = raw.rsplit("/", 1)[-1].split(".", 1)
        if package == object_name:
            variants.add(raw.rsplit(".", 1)[0])
    if raw.startswith("/Game/"):
        variants.add(raw[6:])
    elif not raw.startswith("/Script/"):
        variants.add("/Game/" + raw.lstrip("/"))
    return {item for item in variants if item}


def _matches(reference: str, candidate: str) -> bool:
    ref = reference.rstrip("/")
    cand = candidate.rstrip("/")
    if ref == cand or ref in _path_variants(cand) or cand in _path_variants(ref):
        return True
    # Class and explicitly logical roots are often exported without the
    # generated package prefix.  Never apply this fallback to a concrete
    # /Game path, otherwise /Game/Maps/DemoMap could match an unrelated map.
    if "/" in ref:
        return False
    token = ref.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    candidate_token = cand.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    return bool(token and token == candidate_token)


def _field(item: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


def _object_path(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, Mapping):
        value = _field(item, "path", "objectPath", "runtimePath", "package", "name", "object", "classPath", "class")
        return _text(value)
    return ""


def _object_refs(item: Any) -> list[str]:
    if not isinstance(item, Mapping):
        return []
    value = _field(item, "references", "dependencies", "imports", "requiredReferences", "refs")
    result: list[str] = []
    for ref in _as_list(value):
        path = _object_path(ref) if isinstance(ref, Mapping) else _text(ref)
        if path:
            result.append(path)
    return result


def _is_store_only(item: Any) -> bool:
    if isinstance(item, Mapping):
        classification = str(_field(item, "classification", "cookClass", "cook_class") or "").casefold().replace("-", "_")
        category = str(_field(item, "category") or "").casefold().replace("-", "_")
        return (
            classification in {"store_only", "store", "store_draft"}
            or bool(_field(item, "storeOnly", "store_only"))
            or category == "store_draft"
        )
    text = _text(item).casefold()
    return "store_capsule_concept" in text or "/store/" in text


def _is_editor_only(item: Any) -> bool:
    if isinstance(item, Mapping):
        classification = str(_field(item, "classification", "cookClass", "cook_class") or "").casefold()
        return (
            bool(_field(item, "editorOnly", "editor_only", "editorOnlyObject"))
            or classification in {"editor_only", "editor-only", "editor"}
            or _field(item, "runtimeReady") is False and classification != "store_only"
        )
    return "/developers/" in _text(item).casefold() or "/editor/" in _text(item).casefold()


def _collect_objects(manifest: Mapping[str, Any]) -> list[Any]:
    """Merge exporter sections without counting the same object twice.

    Some UAT exports include both a rich ``objects`` graph and a flat
    ``cookedObjects`` index.  The graph is authoritative when present; flat
    sections only contribute paths not already represented there.
    """
    result: list[Any] = []
    known: set[str] = set()
    for key in ("objects", "cookedObjects", "stagedObjects", "runtimeObjects", "cooked", "runtimeCookedObjects", "cookedPackages", "packages"):
        value = manifest.get(key)
        candidates: list[Any] = []
        if isinstance(value, Mapping):
            for path, details in value.items():
                if isinstance(details, Mapping):
                    item = dict(details)
                    item.setdefault("path", path)
                else:
                    item = {"path": path, "references": details}
                candidates.append(item)
        else:
            candidates.extend(_as_list(value))
        for item in candidates:
            path = _object_path(item)
            if path and path in known:
                continue
            result.append(item)
            if path:
                known.add(path)
    return result


def _duplicate_export_paths(manifest: Mapping[str, Any]) -> list[str]:
    duplicates: list[str] = []
    for key in ("objects", "cookedObjects", "stagedObjects", "runtimeObjects", "cooked", "runtimeCookedObjects", "cookedPackages", "packages"):
        value = manifest.get(key)
        if isinstance(value, Mapping):
            paths = [str(path) for path in value]
        else:
            paths = [_object_path(item) for item in _as_list(value)]
        counts: dict[str, int] = {}
        for path in paths:
            if path:
                counts[path.rstrip("/")] = counts.get(path.rstrip("/"), 0) + 1
        duplicates.extend(path for path, count in sorted(counts.items()) if count > 1)
    return duplicates


def _collect_paths(value: Any) -> list[str]:
    result: list[str] = []
    for item in _as_list(value):
        path = _object_path(item)
        if path:
            result.append(path)
    return result


def _cooked_entries(manifest: Mapping[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in ("cookedObjects", "stagedObjects", "runtimeObjects", "cookedPackages", "packages"):
        if key in manifest:
            values.extend(_as_list(manifest.get(key)))
    return values


def read_staged_manifest(path: Path | str) -> dict[str, Any]:
    """Read a BuildCookRun export or a directory containing one.

    Supported JSON names are intentionally deterministic.  A text fallback is
    useful for an IoStore `*.list`/`*.txt` export and treats one package/object
    path per non-comment line as cooked runtime content.
    """
    candidate = Path(path)
    if candidate.is_dir():
        for name in ("PackageManifest.json", "package_manifest.json", "IoStoreManifest.json", "manifest.json"):
            possible = candidate / name
            if possible.is_file():
                candidate = possible
                break
        else:
            json_files = sorted(candidate.glob("*.json"))
            if json_files:
                candidate = json_files[0]
            else:
                text_files = sorted(candidate.glob("*.list")) + sorted(candidate.glob("*.txt"))
                if text_files:
                    candidate = text_files[0]
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    raw = candidate.read_text(encoding="utf-8", errors="replace")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        paths = [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        return {"format": "text-package-list", "cookedObjects": paths, "ioStoreManifest": str(candidate)}
    if isinstance(value, list):
        return {"format": "json-object-list", "cookedObjects": value, "ioStoreManifest": str(candidate)}
    if not isinstance(value, dict):
        raise ValueError("staged manifest root must be an object, array, or package listing")
    result = dict(value)
    result.setdefault("ioStoreManifest", str(candidate))
    return result


def read_iostore_manifest(path: Path | str) -> dict[str, Any]:
    """Read the portable IoStore listing seam.

    Binary `.utoc` files are not parsed heuristically; callers must provide the
    UAT/IoStore exported listing so a missing listing cannot become a false pass.
    """
    candidate = Path(path)
    if candidate.suffix.casefold() in {".utoc", ".ucas"}:
        raise ValueError("binary IoStore containers require an exported package listing")
    return read_staged_manifest(candidate)


def _asset_entries(asset_manifest: Mapping[str, Any] | None) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    if not isinstance(asset_manifest, Mapping):
        return [], []
    return runtime_entries(asset_manifest), store_only_entries(asset_manifest)


def _reference_items(value: Any) -> list[Any]:
    """Normalize list exports and path-keyed reference maps."""
    if isinstance(value, Mapping):
        result: list[Any] = []
        for path, details in value.items():
            if isinstance(details, Mapping):
                item = dict(details)
                item.setdefault("path", path)
                result.append(item)
            else:
                result.append({"path": path, "kind": details} if details else path)
        return result
    return _as_list(value)


def _required_references(manifest: Mapping[str, Any], asset_manifest: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    explicit = manifest.get("requiredReferences")
    if explicit is None:
        explicit = manifest.get("runtimeReferences")
    if explicit is None:
        explicit = manifest.get("references")
    refs: list[tuple[str, str]] = [
        (item["path"], item.get("kind", "asset")) for item in DEFAULT_ROOTS
    ]
    if explicit is not None:
        for item in _reference_items(explicit):
            if isinstance(item, Mapping):
                path = _object_path(item)
                kind = _text(_field(item, "kind", "type")) or "asset"
            else:
                path, kind = _text(item), "asset"
            if path:
                refs.append((path, kind))
    for item in _reference_items(manifest.get("requiredRoots")):
        if isinstance(item, Mapping):
            path = _object_path(item)
            kind = _text(_field(item, "kind", "type")) or "asset"
        else:
            path, kind = _text(item), "asset"
        if path:
            refs.append((path, kind))
    # Audio is a canonical runtime closure, not an optional explicit-root set.
    # This prevents a package exporter from omitting eight sounds while naming
    # only S_Ambient in requiredReferences.
    refs.extend((path, "asset") for path in AUDIO_RUNTIME_PATHS)
    runtime_assets, _ = _asset_entries(asset_manifest)
    for item in runtime_assets:
        path = _text(item.get("runtimePath"))
        if path:
            refs.append((path, "asset"))
    # De-duplicate while preserving stable order.
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return result


def _class_references(manifest: Mapping[str, Any]) -> list[str]:
    result = list(REQUIRED_CLASSES)
    explicit = manifest.get("requiredClasses")
    if explicit is not None:
        result.extend(path for path in (_object_path(item) for item in _reference_items(explicit)) if path)
    return list(dict.fromkeys(result))


def _cooked_map_present(manifest: Mapping[str, Any], reference: str) -> bool:
    for item in _as_list(manifest.get("cookMaps", manifest.get("cookedMaps"))):
        candidate = _object_path(item)
        if candidate and _matches(reference, candidate):
            return True
    return False


def _find_entry(reference: str, entries: Sequence[Any]) -> Any | None:
    for item in entries:
        candidate = _object_path(item)
        if candidate and _matches(reference, candidate):
            return item
    return None


def validate_package_closure(
    package_manifest: Mapping[str, Any],
    *,
    asset_manifest: Mapping[str, Any] | None = None,
    staged_manifest: Mapping[str, Any] | None = None,
    project_root: Path | str | None = None,
) -> list[ClosureIssue]:
    """Return all closure/classification issues; an empty list means valid.

    ``staged_manifest`` can be supplied separately from package metadata.  If
    omitted, package_manifest is treated as the staged export itself.
    """
    issues: list[ClosureIssue] = []
    if not isinstance(package_manifest, Mapping):
        return [ClosureIssue("$", "Package.InvalidManifest", "package manifest must be an object")]
    if asset_manifest is None and project_root is not None:
        candidate_manifest = Path(project_root) / "RawAssets" / "AI" / "asset_manifest.json"
        if candidate_manifest.is_file():
            asset_manifest = load_manifest(candidate_manifest)
    staged = staged_manifest if isinstance(staged_manifest, Mapping) else package_manifest
    objects = _collect_objects(staged)
    cooked = _cooked_entries(staged)
    if not objects and not cooked:
        _issue(issues, "stagedManifest", "Package.IoStoreManifestUnavailable", "no cooked/staged object listing was supplied")
    object_entries = objects or cooked
    cooked_paths = [path for path in (_object_path(item) for item in object_entries) if path]

    config = str(package_manifest.get("configuration", package_manifest.get("buildConfiguration", "")))
    if config.casefold() not in {"shipping", "ppbc_shipping"}:
        _issue(issues, "configuration", "Package.InvalidConfiguration", "accepted package must use Shipping configuration")
    if package_manifest.get("projectCodeBuild") is not True and package_manifest.get("build") is not True:
        _issue(issues, "projectCodeBuild", "Package.ProjectCodeBuildDisabled", "package must include a project code build")
    if package_manifest.get("ioStore") is not True and package_manifest.get("iostore") is not True:
        _issue(issues, "ioStore", "Package.IoStoreDisabled", "package must include an IoStore manifest/container")
    cook_maps = package_manifest.get("cookMaps", package_manifest.get("cookedMaps"))
    if not isinstance(cook_maps, (list, tuple, set)) or not any(
        _matches(DEMO_MAP, _object_path(item)) for item in cook_maps
    ):
        _issue(
            issues,
            "cookMaps",
            "Package.MissingMap",
            f"package must cook {DEMO_MAP}",
            DEMO_MAP,
        )

    output = _text(package_manifest.get("packagePath", package_manifest.get("outputPath", package_manifest.get("archiveDirectory"))))
    normalized_output = output.replace("\\", "/").rstrip("/")
    output_root = RUNTIME_OUTPUT_PREFIX.rstrip("/")
    output_lower = normalized_output.casefold()
    root_lower = output_root.casefold()
    is_under_output_root = (
        output_lower == root_lower
        or output_lower.startswith(root_lower + "/")
        or output_lower.endswith("/" + root_lower)
        or ("/" + root_lower + "/") in output_lower
    )
    if not normalized_output or not is_under_output_root:
        _issue(issues, "packagePath", "Package.InvalidOutputPath", f"package output must be under {RUNTIME_OUTPUT_PREFIX}")

    for ref, kind in _required_references(package_manifest, asset_manifest):
        entry = _find_entry(ref, object_entries)
        # cookMaps is metadata, not proof that the corresponding cooked object
        # exists.  A map must resolve in the staged object listing as well.
        if entry is None:
            _issue(issues, ref, MISSING_CODES.get(kind, "Package.MissingAsset"), "required runtime reference is absent from cooked/staged objects", ref)
            continue
        if _is_store_only(entry):
            _issue(issues, ref, "Asset.StoreAssetInRuntime", "store-only object is present in the runtime cook set", ref)
        elif _is_editor_only(entry):
            _issue(issues, ref, "Package.EditorOnlyObject", "editor-only object is present in the runtime closure", ref)

    for class_name in _class_references(package_manifest):
        entry = _find_entry(class_name, object_entries)
        if entry is None:
            _issue(issues, class_name, "Package.MissingClass", "required runtime class is absent from cooked/staged objects", class_name)
        elif _is_store_only(entry):
            _issue(issues, class_name, "Asset.StoreAssetInRuntime", "store-only object cannot satisfy a runtime class reference", class_name)
        elif _is_editor_only(entry):
            _issue(issues, class_name, "Package.EditorOnlyObject", "editor-only object cannot satisfy a runtime class reference", class_name)

    runtime_assets, store_assets = _asset_entries(asset_manifest)
    runtime_paths: dict[str, list[Mapping[str, Any]]] = {}
    for item in runtime_assets:
        runtime_path = _text(item.get("runtimePath"))
        if runtime_path:
            runtime_paths.setdefault(runtime_path.rstrip("/"), []).append(item)
        if item.get("runtimeReady") is False:
            _issue(
                issues,
                runtime_path or str(item.get("id", "asset")),
                "Asset.MissingCookReference",
                "runtime asset is explicitly marked not runtime-ready",
                runtime_path or None,
            )
    for runtime_path, entries_for_path in sorted(runtime_paths.items()):
        if len(entries_for_path) > 1:
            _issue(issues, runtime_path, "Asset.DuplicateMapping", "multiple runtime manifest entries resolve to the same path", runtime_path)
    for item in runtime_assets:
        runtime_path = _text(item.get("runtimePath"))
        if not runtime_path:
            _issue(issues, str(item.get("id", "asset")), "Package.MissingAsset", "runtime asset has no runtimePath")
            continue
        entry = _find_entry(runtime_path, object_entries)
        if entry is None:
            _issue(issues, runtime_path, "Package.MissingAsset", "Imported_Asset is not present in the cooked runtime set", runtime_path)
        elif _is_store_only(entry):
            _issue(issues, runtime_path, "Asset.StoreAssetInRuntime", "runtime asset resolves to a store-only object", runtime_path)
        elif _is_editor_only(entry):
            _issue(issues, runtime_path, "Package.EditorOnlyObject", "runtime asset resolves to an editor-only object", runtime_path)
    store_paths = {path for item in store_assets for path in (_text(item.get("source")), _text(item.get("runtimePath")))}
    store_paths.update({"Store_capsule_concept", "store.capsule.concept"})
    for item in object_entries:
        path = _object_path(item)
        if _is_store_only(item) or any(_matches(store_path, path) for store_path in store_paths if store_path and path):
            _issue(issues, path or "<unnamed>", "Asset.StoreAssetInRuntime", "store-only object is present in the runtime cook set", path or None)

    # Traverse the exported dependency graph from roots.  This catches an
    # indirect missing/editor/store object even when the object list itself is
    # otherwise complete.
    by_path = {path: item for item in object_entries for path in [_object_path(item)] if path}
    queue = [ref for ref, _ in _required_references(package_manifest, asset_manifest)] + _class_references(package_manifest)
    visited: set[str] = set()
    while queue:
        reference = queue.pop(0)
        if reference in visited:
            continue
        visited.add(reference)
        entry = _find_entry(reference, object_entries)
        if entry is None:
            continue  # direct missing errors above are more precise
        if _is_store_only(entry) or _is_editor_only(entry):
            continue
        for dependency in _object_refs(entry):
            dep_entry = _find_entry(dependency, object_entries)
            if dep_entry is None:
                _issue(issues, dependency, "Package.MissingAsset", "reachable dependency is absent from cooked/staged objects", dependency)
            elif _is_store_only(dep_entry):
                _issue(issues, dependency, "Asset.StoreAssetInRuntime", "reachable dependency is store-only", dependency)
            elif _is_editor_only(dep_entry):
                _issue(issues, dependency, "Package.EditorOnlyObject", "reachable dependency is editor-only", dependency)
            else:
                queue.append(dependency)

    # Exact duplicate paths make closure ambiguous and must not be accepted.
    for path in _duplicate_export_paths(staged):
        _issue(issues, path, "Package.DuplicateObject", "cooked/staged object appears more than once in one export section", path)

    # Preserve first occurrence order but avoid noisy duplicate reports caused
    # by the same object being listed in both `objects` and `cookedObjects`.
    unique: list[ClosureIssue] = []
    seen_issue: set[tuple[str, str, str]] = set()
    for issue in issues:
        key = (issue.path, issue.code, issue.message)
        if key not in seen_issue:
            seen_issue.add(key)
            unique.append(issue)
    return unique


def read_iostore_container(path: Path | str) -> dict[str, Any]:
    """Explicit seam name for BuildCookRun/IoStore integrations."""
    return read_iostore_manifest(path)


class PackageClosureValidator:
    """Reusable state-free facade for preflight and release tooling."""

    def __init__(self, asset_manifest: Mapping[str, Any] | None = None, project_root: Path | str | None = None):
        self.asset_manifest = asset_manifest
        self.project_root = project_root

    def validate(self, package_manifest: Mapping[str, Any], *, staged_manifest: Mapping[str, Any] | None = None) -> list[ClosureIssue]:
        return validate_package_closure(
            package_manifest,
            asset_manifest=self.asset_manifest,
            staged_manifest=staged_manifest,
            project_root=self.project_root,
        )

    def report(self, package_manifest: Mapping[str, Any], *, staged_manifest: Mapping[str, Any] | None = None, execution_mode: str = "fixture") -> dict[str, Any]:
        return build_closure_report(
            self.validate(package_manifest, staged_manifest=staged_manifest),
            manifest=package_manifest,
            execution_mode=execution_mode,
        )


def validate_package_manifest(package_manifest: Mapping[str, Any], **kwargs: Any) -> list[ClosureIssue]:
    """Compatibility alias used by packaging/preflight callers."""
    return validate_package_closure(package_manifest, **kwargs)


CLOSURE_REPORT_SCHEMA_VERSION = "1.0"


def build_closure_report(
    issues: Iterable[ClosureIssue],
    *,
    manifest: Mapping[str, Any] | None = None,
    execution_mode: str = "fixture",
) -> dict[str, Any]:
    """Create the stable machine-readable report consumed by readiness tooling."""
    findings = list(issues)
    mode = execution_mode if execution_mode in {"live", "fixture"} else "fixture"
    serialized = [item.as_dict() if isinstance(item, ClosureIssue) else {"path": "$", "code": "Package.UnknownIssue", "message": str(item)} for item in findings]
    evidence_paths = [str(manifest.get("ioStoreManifest"))] if isinstance(manifest, Mapping) and manifest.get("ioStoreManifest") else []
    package_path = str(manifest.get("packagePath")) if isinstance(manifest, Mapping) and manifest.get("packagePath") else ""
    evidence_locatable = bool(evidence_paths) and all(Path(path).is_file() for path in evidence_paths)
    package_candidate = Path(package_path) if package_path else None
    package_locatable = bool(
        package_candidate and package_candidate.is_dir()
        and ((package_candidate / "Content" / "Paks").is_dir() or any(package_candidate.glob("*/Content/Paks")))
    )
    eligible = mode == "live" and not findings and evidence_locatable and package_locatable
    return {
        "schemaVersion": CLOSURE_REPORT_SCHEMA_VERSION,
        "reportType": "package_closure",
        "executionMode": mode,
        "status": "pass" if eligible else "fail" if findings else "blocked" if mode == "live" else "not_run",
        "readinessEligible": eligible,
        "valid": not findings,
        "packageAcceptance": "ready" if eligible else "blocked",
        "errorCount": len(findings),
        "errorCodes": sorted({item["code"] for item in serialized}),
        "errors": serialized,
        "manifest": manifest.get("packagePath") if isinstance(manifest, Mapping) else None,
        "packagePath": manifest.get("packagePath") if isinstance(manifest, Mapping) else None,
        "ioStoreManifestPath": evidence_paths[0] if evidence_paths else None,
        "evidencePaths": evidence_paths,
    }


def check_package_closure(package_manifest: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    issues = validate_package_closure(package_manifest, **kwargs)
    return build_closure_report(issues, manifest=package_manifest)


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="package/staged JSON manifest or IoStore text listing")
    parser.add_argument("--asset-manifest", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON report")
    parser.add_argument("--execution-mode", choices=("live", "fixture"), default="live")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        package = read_staged_manifest(args.manifest)
        assets = load_manifest(args.asset_manifest) if args.asset_manifest else None
        issues = validate_package_closure(package, asset_manifest=assets, project_root=args.project_root)
        report = build_closure_report(issues, manifest=package, execution_mode=args.execution_mode)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            if issues:
                for issue in issues:
                    print(issue, file=sys.stderr)
            else:
                print(f"VALID: {args.manifest}")
        return 0 if not issues else 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report = {"valid": False, "packageAcceptance": "blocked", "errorCount": 1, "errors": [{"path": "$", "code": "Package.ManifestLoadError", "message": str(error)}]}
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Package.ManifestLoadError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
