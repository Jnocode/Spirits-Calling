#!/usr/bin/env python3
"""P9 package closure and runtime/store mutation fixtures."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

try:
    from Scripts.asset_manifest_validator import MANIFEST_PATH, load_manifest
    from Scripts.package_closure_validator import (
        build_closure_report,
        read_iostore_manifest,
        read_staged_manifest,
        validate_package_closure,
    )
except ModuleNotFoundError:  # Direct execution: python Scripts/test_package_closure.py
    from asset_manifest_validator import MANIFEST_PATH, load_manifest
    from package_closure_validator import (
        build_closure_report,
        read_iostore_manifest,
        read_staged_manifest,
        validate_package_closure,
    )


class PackageClosureFixtures(unittest.TestCase):
    """**Validates: Requirements 5.3, 5.11, 5.12, 6.8, 6.9**"""

    def _fixture(self) -> tuple[dict, dict]:
        assets = load_manifest(MANIFEST_PATH)
        objects = [
            {"path": "/Game/Maps/DemoMap", "references": ["PCVRMenu", "AchievementFallback", "S_Ambient"]},
            {"path": "/Script/SpiritsCalling.SpiritsGameMode"},
            {"path": "/Script/SpiritsCalling.SpiritsGameState"},
            {"path": "/Script/SpiritsCalling.SpiritsPlayerController"},
            {"path": "/Script/SpiritsCalling.SpiritPawn"},
            {"path": "/Script/SpiritsCalling.SpiritVRPawn"},
            {"path": "/Game/UI/PCVRMenu"},
            {"path": "/Game/Systems/AchievementFallback"},
            {"path": "/Game/Audio/S_Ambient", "references": ["/Game/Audio/S_Ambient.uasset"]},
            {"path": "/Game/Audio/S_Ambient.uasset"},
        ]
        objects.extend(
            {"path": f"/Game/Audio/{name}"}
            for name in ("S_Alarm", "S_Attack", "S_Click", "S_Death", "S_Defeat", "S_Hit", "S_Summon", "S_Victory")
        )
        objects.extend({"path": entry["runtimePath"]} for entry in assets["entries"] if entry.get("cookClass") == "runtime")
        package = {
            "configuration": "Shipping",
            "projectCodeBuild": True,
            "ioStore": True,
            "packagePath": "Builds/Windows",
            "cookMaps": ["/Game/Maps/DemoMap"],
            "requiredReferences": [
                {"path": "/Game/Maps/DemoMap", "kind": "map"},
                {"path": "PCVRMenu", "kind": "asset"},
                {"path": "AchievementFallback", "kind": "asset"},
                {"path": "S_Ambient", "kind": "asset"},
            ],
            "objects": objects,
        }
        return package, assets

    def test_canonical_fixture_closes_all_runtime_references(self) -> None:
        package, assets = self._fixture()
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertEqual([], issues, [str(issue) for issue in issues])
        report = build_closure_report(issues, manifest=package)
        self.assertTrue(report["valid"])
        self.assertEqual("blocked", report["packageAcceptance"])
        self.assertEqual("not_run", report["status"])
        self.assertFalse(report["readinessEligible"])
        self.assertEqual("1.0", report["schemaVersion"])
        self.assertEqual([], report["errors"])
        self.assertEqual([], report["errorCodes"])

    def test_missing_reference_has_stable_code_and_location(self) -> None:
        package, assets = self._fixture()
        package["objects"] = [item for item in package["objects"] if item["path"] != "/Game/Textures/Arenas/Sands/Arena_Sands_sky"]
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.MissingAsset" and "Sands_sky" in item.path for item in issues))

    def test_editor_only_runtime_object_fails_closed(self) -> None:
        package, assets = self._fixture()
        target = next(item for item in package["objects"] if item["path"] == "/Game/Maps/DemoMap")
        target["editorOnly"] = True
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.EditorOnlyObject" and item.reference == "/Game/Maps/DemoMap" for item in issues))

    def test_store_capsule_is_never_accepted_in_runtime_objects(self) -> None:
        package, assets = self._fixture()
        package["objects"].append({"path": "RawAssets/AI/Store/Store_capsule_concept.png", "cookClass": "store_only"})
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Asset.StoreAssetInRuntime" for item in issues))

    def test_missing_class_is_reported_separately(self) -> None:
        package, assets = self._fixture()
        package["objects"] = [item for item in package["objects"] if not item["path"].endswith("SpiritVRPawn")]
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.MissingClass" and item.reference == "SpiritVRPawn" for item in issues))

    def test_staged_json_and_iostore_text_reader_are_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            json_path = root_path / "PackageManifest.json"
            json_path.write_text(json.dumps({"cookedObjects": ["/Game/Maps/DemoMap"]}), encoding="utf-8")
            text_path = root_path / "IoStore.list"
            text_path.write_text("# exported package paths\n/Game/Maps/DemoMap\n", encoding="utf-8")
            self.assertEqual("/Game/Maps/DemoMap", read_staged_manifest(json_path)["cookedObjects"][0])
            self.assertEqual("text-package-list", read_iostore_manifest(text_path)["format"])

    def test_package_output_accepts_archived_subdirectory_under_windows_root(self) -> None:
        package, assets = self._fixture()
        package["packagePath"] = "Builds/Windows/SpiritsCalling-0.9.0"
        self.assertEqual([], validate_package_closure(package, asset_manifest=assets))
        package["packagePath"] = "D:/BuildAgent/SpiritsCalling/Builds/Windows/SpiritsCalling-0.9.0"
        self.assertEqual([], validate_package_closure(package, asset_manifest=assets))

    def test_cook_maps_metadata_cannot_hide_missing_map_object(self) -> None:
        package, assets = self._fixture()
        package["cookMaps"] = ["/Game/Maps/DemoMap"]
        package["objects"] = [item for item in package["objects"] if item["path"] != "/Game/Maps/DemoMap"]
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.MissingMap" and item.reference == "/Game/Maps/DemoMap" for item in issues))

    def test_concrete_game_path_does_not_match_unrelated_same_name_object(self) -> None:
        package, assets = self._fixture()
        package["objects"] = [item for item in package["objects"] if item["path"] != "/Game/Maps/DemoMap"]
        package["objects"].append({"path": "/Game/Maps/Test/DemoMap"})
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.MissingMap" and item.reference == "/Game/Maps/DemoMap" for item in issues))

    def test_not_runtime_ready_asset_and_duplicate_mapping_fail_closed(self) -> None:
        package, assets = self._fixture()
        mutated = copy.deepcopy(assets)
        target = next(item for item in mutated["entries"] if item["id"] == "arena.void.ground")
        target["runtimeReady"] = False
        mutated["entries"].append(copy.deepcopy(target))
        issues = validate_package_closure(package, asset_manifest=mutated)
        codes = {item.code for item in issues}
        self.assertIn("Asset.MissingCookReference", codes)
        self.assertIn("Asset.DuplicateMapping", codes)

    def test_binary_iostore_container_is_rejected_without_exported_listing(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            container = Path(root) / "global.utoc"
            container.write_bytes(b"not a portable listing")
            with self.assertRaises(ValueError):
                read_iostore_manifest(container)

    def test_manifest_cannot_shrink_canonical_roots_or_classes(self) -> None:
        package, assets = self._fixture()
        package["requiredReferences"] = []
        package["requiredClasses"] = []
        package["objects"] = [
            item for item in package["objects"]
            if item["path"] not in {"/Game/UI/PCVRMenu", "/Game/Systems/AchievementFallback"}
            and "SpiritsGameMode" not in item["path"]
        ]
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.reference == "PCVRMenu" for item in issues))
        self.assertTrue(any(item.reference == "AchievementFallback" for item in issues))
        self.assertTrue(any(item.reference == "SpiritsGameMode" for item in issues))

    def test_missing_canonical_audio_object_fails_even_when_raw_inventory_is_outside_closure(self) -> None:
        package, assets = self._fixture()
        package["objects"] = [item for item in package["objects"] if item["path"] != "/Game/Audio/S_Victory"]
        issues = validate_package_closure(package, asset_manifest=assets)
        self.assertTrue(any(item.code == "Package.MissingAsset" and item.reference == "/Game/Audio/S_Victory" for item in issues))

    def test_wrong_configuration_and_disabled_iostore_are_machine_readable(self) -> None:
        package, assets = self._fixture()
        package["configuration"] = "Development"
        package["ioStore"] = False
        issues = validate_package_closure(package, asset_manifest=assets)
        codes = {item.code for item in issues}
        self.assertIn("Package.InvalidConfiguration", codes)
        self.assertIn("Package.IoStoreDisabled", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
