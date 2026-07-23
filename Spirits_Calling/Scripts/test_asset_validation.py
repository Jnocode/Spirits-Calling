#!/usr/bin/env python3
"""Unit and mutation fixtures for task 6.2 texture validation."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from Scripts.CheckTextureSettings import audit_texture_dimensions
from Scripts.asset_manifest_validator import (
    MANIFEST_PATH,
    build_asset_validation_records,
    load_manifest,
    validate_manifest,
    validate_texture_dimensions,
)
from Scripts.readiness_record_validator import validate_record
from Scripts.readiness_record_writer import attach_asset_validation


class TextureValidationFixtures(unittest.TestCase):
    def test_power_of_two_dimensions_at_2048_are_valid(self) -> None:
        result = audit_texture_dimensions(2048, 1024)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["failureCode"])

    def test_non_power_of_two_and_over_limit_are_rejected(self) -> None:
        self.assertEqual("Asset.InvalidDimensions", validate_texture_dimensions(1024, 1000)["failureCode"])
        result = validate_texture_dimensions(4096, 2048)
        self.assertFalse(result["valid"])
        self.assertIn("2048", result["failureReason"])

    def test_skybox_is_not_implicitly_exempt(self) -> None:
        result = validate_texture_dimensions(4096, 2048, is_skybox=True)
        self.assertFalse(result["valid"])
        self.assertFalse(result["skyboxExceptionDocumented"])

    def test_documented_skybox_requires_readiness_record(self) -> None:
        exception = {"documented": True, "exceptionId": "sky-1", "evidencePath": "evidence/sky.log"}
        self.assertFalse(validate_texture_dimensions(4096, 2048, is_skybox=True, skybox_exception=exception)["valid"])
        result = validate_texture_dimensions(
            4096, 2048, is_skybox=True, skybox_exception=exception, readiness_recorded=True
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["skyboxExceptionDocumented"])

    def test_canonical_manifest_records_runtime_ready_assets(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        records = build_asset_validation_records(manifest, MANIFEST_PATH.parents[2])
        self.assertEqual(9, len(records))
        self.assertTrue(all(item["runtimeReady"] for item in records if item.get("classification") != "store_only"))
        store = next(item for item in records if item["source"].endswith("Store_capsule_concept.png"))
        self.assertFalse(store["runtimeReady"])
        self.assertEqual("store_only", store["classification"])

    def test_mutation_over_limit_is_runtime_not_ready_with_reason_and_hook(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        mutated = copy.deepcopy(manifest)
        entry = next(item for item in mutated["entries"] if item["id"] == "arena.void.sky")
        entry["validation"] = {"width": 4096, "height": 2048}
        records = build_asset_validation_records(mutated, MANIFEST_PATH.parents[2])
        failure = next(item for item in records if item["id"] == "arena.void.sky")
        self.assertFalse(failure["runtimeReady"])
        self.assertEqual("Asset.InvalidDimensions", failure["failureCode"])
        self.assertTrue(failure["failureReason"])
        self.assertEqual("ArenaMaterialHook.Void.Sky", failure["hook"])

    def test_mutation_missing_source_is_recorded_exactly(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        mutated = copy.deepcopy(manifest)
        entry = mutated["entries"][0]
        entry["source"] = "RawAssets/AI/Civilizations/East/missing.png"
        records = build_asset_validation_records(mutated, MANIFEST_PATH.parents[2])
        failure = records[0]
        self.assertEqual(entry["source"], failure["source"])
        self.assertEqual("Asset.SourceMissing", failure["failureCode"])
        self.assertFalse(failure["runtimeReady"])
        self.assertTrue(failure["failureReason"])

    def test_manifest_rejects_invalid_texture_and_never_accepts_runtime_ready(self) -> None:
        manifest = load_manifest(MANIFEST_PATH)
        mutated = copy.deepcopy(manifest)
        entry = next(item for item in mutated["entries"] if item["id"] == "civilization.east.pattern")
        entry["validation"] = {"width": 1000, "height": 1024}
        entry["runtimeReady"] = True
        errors = validate_manifest(mutated, MANIFEST_PATH.parents[2])
        self.assertTrue(any("Asset.InvalidDimensions" in error for error in errors))
        self.assertTrue(any("Asset.RuntimeReadyMismatch" in error for error in errors))

    def test_readiness_record_rejects_failed_asset_without_complete_failure_record(self) -> None:
        record = {
            "assetValidation": [{
                "source": "RawAssets/AI/Arenas/Void/Arena_Void_sky.png",
                "hook": "ArenaMaterialHook.Void.Sky",
                "runtimeReady": False,
            }]
        }
        issues = validate_record(record, tempfile.gettempdir())
        self.assertTrue(any(item.path == "assetValidation[0].failureCode" for item in issues))
        self.assertTrue(any(item.path == "assetValidation[0].failureReason" for item in issues))

    def test_readiness_writer_blocks_failed_asset_and_preserves_failure_details(self) -> None:
        record = {"packageAcceptance": "ready", "gates": [], "unresolvedIssues": [], "earliestFailure": None}
        failed = [{
            "source": "RawAssets/AI/Arenas/Void/Arena_Void_sky.png",
            "hook": "ArenaMaterialHook.Void.Sky",
            "runtimeReady": False,
            "failureCode": "Asset.InvalidDimensions",
            "failureReason": "texture exceeds 2048px without a recorded exception",
        }]
        updated = attach_asset_validation(record, failed)
        self.assertEqual("blocked", updated["packageAcceptance"])
        self.assertEqual(failed[0]["source"], updated["assetValidation"][0]["source"])
        self.assertEqual("Asset.InvalidDimensions", updated["assetValidation"][0]["failureCode"])
        self.assertTrue(updated["unresolvedIssues"])
        self.assertEqual("asset.texture_validation", updated["unresolvedIssues"][0]["gateId"])

    def test_schema_declares_asset_validation_and_skybox_exception_contracts(self) -> None:
        schema_path = MANIFEST_PATH.parents[2] / "Docs" / "Release" / "Release_Readiness_Record.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn("assetValidation", schema["properties"])
        self.assertIn("skyboxExceptions", schema["properties"])
        self.assertIn("assetValidation", schema["$defs"])
        self.assertIn("skyboxException", schema["$defs"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
