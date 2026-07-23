"""Texture audit shared by Unreal Editor and external validation.

The old audit used a 4096px advisory limit.  Release validation is stricter:
all runtime gameplay textures must be power-of-two in both dimensions and no
larger than 2048px.  Sky textures are not automatically exempt; an exception
must be documented in the release record before it can be accepted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

try:
    from .asset_manifest_validator import (
        GAMEPLAY_TEXTURE_MAX_DIMENSION,
        build_asset_validation_records,
        load_manifest,
        read_png_dimensions,
        validate_texture_dimensions,
    )
except ImportError:  # Direct execution from Scripts/ or Unreal's Python console.
    from asset_manifest_validator import (
        GAMEPLAY_TEXTURE_MAX_DIMENSION,
        build_asset_validation_records,
        load_manifest,
        read_png_dimensions,
        validate_texture_dimensions,
    )

# Kept as a named constant for existing callers and for static configuration checks.
MAX_SIZE = GAMEPLAY_TEXTURE_MAX_DIMENSION


def audit_texture_dimensions(
    width: Any,
    height: Any,
    *,
    is_skybox: bool = False,
    skybox_exception: Mapping[str, Any] | None = None,
    readiness_recorded: bool = False,
) -> dict[str, Any]:
    """Apply the release texture profile without requiring Unreal."""
    return validate_texture_dimensions(
        width,
        height,
        is_skybox=is_skybox,
        skybox_exception=skybox_exception,
        readiness_recorded=readiness_recorded,
        max_dimension=GAMEPLAY_TEXTURE_MAX_DIMENSION,
    )


def audit_manifest(
    manifest_path: str | Path,
    project_root: str | Path | None = None,
    *,
    readiness_record: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return one validation/failure record per manifest entry."""
    manifest = load_manifest(manifest_path)
    return build_asset_validation_records(
        manifest,
        project_root or Path(manifest_path).resolve().parents[2],
        check_sources=True,
        readiness_record=readiness_record,
    )


def check_vr_textures() -> None:
    """Run the canonical audit in Unreal Editor and log every failure."""
    try:
        import unreal
    except ImportError as error:  # pragma: no cover - exercised only in UE.
        raise RuntimeError("check_vr_textures must run inside Unreal Editor Python") from error

    manifest_path = Path(__file__).resolve().parents[1] / "RawAssets" / "AI" / "asset_manifest.json"
    records = audit_manifest(manifest_path, Path(__file__).resolve().parents[1])
    unreal.log("--- Gameplay Texture Validation Report (max 2048px) ---")
    failures = [record for record in records if record.get("failureCode")]
    for record in failures:
        unreal.log_warning(
            "%s %s — %s (hook: %s)"
            % (
                record.get("failureCode"),
                record.get("source"),
                record.get("failureReason"),
                record.get("hook", "no-hook-assigned"),
            )
        )
    if not failures:
        unreal.log("All runtime gameplay textures satisfy the 2048px power-of-two profile.")


if __name__ == "__main__":
    check_vr_textures()
