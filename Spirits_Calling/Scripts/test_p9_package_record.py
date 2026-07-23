#!/usr/bin/env python3
"""Generated P9 package-closure and readiness-record property fixtures.

These are fixture-oracle tests only. They do not build or launch a Shipping
package, connect to Steam, or claim PCVR/release readiness.
"""
from __future__ import annotations

import copy
import random
import tempfile
import unittest
from pathlib import Path
from typing import Any

try:
    from Scripts.asset_manifest_validator import MANIFEST_PATH, load_manifest
    from Scripts.package_closure_validator import validate_package_closure
    from Scripts.readiness_record_validator import REQUIRED_FIELDS, is_ready, validate_record
    from Scripts.test_readiness_record import ReadinessRecordFixtures
except ModuleNotFoundError:  # Direct execution: python Scripts/test_p9_package_record.py
    from asset_manifest_validator import MANIFEST_PATH, load_manifest
    from package_closure_validator import validate_package_closure
    from readiness_record_validator import REQUIRED_FIELDS, is_ready, validate_record
    from test_readiness_record import ReadinessRecordFixtures


class P9PackageRecordPropertyFixtures(unittest.TestCase):
    """Feature: spirits-calling-requirements, Property 9: package closure and acceptance-record invariant."""

    MUTATIONS = (
        "missing_reference",
        "duplicate_object",
        "editor_only_object",
        "store_only_object",
        "wrong_configuration",
        "disabled_iostore",
        "missing_map",
        "incomplete_record",
        "missing_evidence",
        "malformed_failure",
    )

    def _package_fixture(self) -> tuple[dict[str, Any], dict[str, Any]]:
        assets = load_manifest(MANIFEST_PATH)
        objects: list[dict[str, Any]] = [
            {
                "path": "/Game/Maps/DemoMap",
                "references": ["PCVRMenu", "AchievementFallback", "S_Ambient"],
            },
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
        objects.extend(
            {"path": entry["runtimePath"]}
            for entry in assets["entries"]
            if entry.get("cookClass") == "runtime"
        )
        package = {
            "configuration": "Shipping",
            "projectCodeBuild": True,
            "ioStore": True,
            "packagePath": "Builds/Windows/SpiritsCalling-fixture",
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

    @staticmethod
    def _record_fixture(root: str) -> dict[str, Any]:
        # Reuse the canonical complete fixture; its evidence files are created
        # inside the temporary directory and never represent real release data.
        return ReadinessRecordFixtures()._ready_record(root)

    def _mutate_package(self, package: dict[str, Any], assets: dict[str, Any], kind: str, rng: random.Random) -> None:
        if kind == "missing_reference":
            runtime_objects = {
                entry["runtimePath"]
                for entry in assets["entries"]
                if entry.get("cookClass") == "runtime"
            }
            candidates = [item for item in package["objects"] if item.get("path") in runtime_objects]
            package["objects"].remove(rng.choice(candidates))
        elif kind == "duplicate_object":
            package["objects"].append(copy.deepcopy(rng.choice(package["objects"])))
        elif kind == "editor_only_object":
            target = next(item for item in package["objects"] if item["path"] == "/Game/Maps/DemoMap")
            target["editorOnly"] = True
        elif kind == "store_only_object":
            package["objects"].append({
                "path": "RawAssets/AI/Store/Store_capsule_concept.png",
                "cookClass": "store_only",
            })
        elif kind == "wrong_configuration":
            package["configuration"] = rng.choice(("Development", "Test", "Debug"))
        elif kind == "disabled_iostore":
            package["ioStore"] = False
        elif kind == "missing_map":
            if rng.randrange(2):
                package["objects"] = [
                    item for item in package["objects"] if item.get("path") != "/Game/Maps/DemoMap"
                ]
            else:
                package["cookMaps"] = []
        elif kind not in {"incomplete_record", "malformed_failure"}:
            raise AssertionError(f"unsupported package mutation: {kind}")

    @staticmethod
    def _mutate_record(record: dict[str, Any], kind: str, rng: random.Random) -> None:
        if kind == "incomplete_record":
            record["packageAcceptance"] = "blocked"
            required = [field for field in REQUIRED_FIELDS if field != "packageAcceptance"]
            del record[rng.choice(required)]
        elif kind == "missing_evidence":
            record["packageAcceptance"] = "blocked"
            record["evidence"][0]["path"] = "evidence/missing/generated-counterexample.log"
            record["earliestFailure"] = {
                "step": "evidence lookup",
                "reason": "generated evidence is missing",
                "logPath": "evidence/missing/generated-counterexample.log",
            }
            record["unresolvedIssues"] = [{
                "id": "evidence.issue",
                "gateId": "package.acceptance",
                "reason": "generated evidence is missing",
                "evidencePath": "evidence/missing/generated-counterexample.log",
                "resolutionStatus": "open",
            }]
        elif kind == "malformed_failure":
            record["packageAcceptance"] = "blocked"
            gate = next(item for item in record["gates"] if item["id"] == "package.acceptance")
            gate["status"] = "fail"
            gate["failureReason"] = "cook failed in fixture"
            gate["resolutionStatus"] = "open"
            record["unresolvedIssues"] = [{
                "id": "package.acceptance.issue",
                "gateId": "package.acceptance",
                "reason": "cook failed in fixture",
                "evidencePath": "evidence/gate.log",
                "resolutionStatus": "open",
            }]
            record["earliestFailure"] = {
                "step": "cook",
                "reason": "cook failed in fixture",
                "logPath": "evidence/gate.log",
            }
            # Remove one required failure field. The resulting record must stay
            # blocked and the validator must report the malformed failure.
            del record["earliestFailure"][rng.choice(("step", "reason", "logPath"))]
        elif kind not in {
            "missing_reference", "duplicate_object", "editor_only_object",
            "store_only_object", "wrong_configuration", "disabled_iostore", "missing_map",
            "missing_evidence",
        }:
            raise AssertionError(f"unsupported record mutation: {kind}")

    def test_canonical_fixture_proves_both_map_styles_and_closed_runtime_graph(self) -> None:
        package, assets = self._package_fixture()
        self.assertEqual([], validate_package_closure(package, asset_manifest=assets))
        runtime_paths = {
            item["path"] for item in package["objects"] if isinstance(item, dict)
        }
        for style in ("Void", "Sands"):
            self.assertIn(f"/Game/Textures/Arenas/{style}/Arena_{style}_ground", runtime_paths)
            self.assertIn(f"/Game/Textures/Arenas/{style}/Arena_{style}_sky", runtime_paths)
        self.assertNotIn("RawAssets/AI/Store/Store_capsule_concept.png", runtime_paths)

    def test_generated_mutations_fail_closed_for_128_iterations(self) -> None:
        rng = random.Random(91010)
        seen: set[str] = set()
        with tempfile.TemporaryDirectory() as root:
            for iteration in range(128):
                kind = rng.choice(self.MUTATIONS)
                seen.add(kind)
                package, assets = self._package_fixture()
                record = self._record_fixture(root)

                if kind in {"incomplete_record", "missing_evidence", "malformed_failure"}:
                    self._mutate_record(record, kind, rng)
                    issues = validate_record(record, root)
                    self.assertTrue(
                        issues,
                        f"iteration={iteration} seed=91010 mutation={kind} unexpectedly accepted",
                    )
                    self.assertEqual("blocked", record.get("packageAcceptance"))
                    self.assertFalse(is_ready(record, root))
                else:
                    self._mutate_package(package, assets, kind, rng)
                    issues = validate_package_closure(package, asset_manifest=assets)
                    self.assertTrue(
                        issues,
                        f"iteration={iteration} seed=91010 mutation={kind} unexpectedly accepted",
                    )
                    if kind == "wrong_configuration":
                        self.assertNotEqual("Shipping", package["configuration"])

        self.assertEqual(set(self.MUTATIONS), seen)

    def test_well_formed_failure_preserves_earliest_step_reason_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._record_fixture(root)
            record["packageAcceptance"] = "blocked"
            gate = next(item for item in record["gates"] if item["id"] == "package.acceptance")
            gate.update({"status": "fail", "failureReason": "cook failed", "resolutionStatus": "open"})
            record["unresolvedIssues"] = [{
                "id": "package.acceptance.issue",
                "gateId": "package.acceptance",
                "reason": "cook failed",
                "evidencePath": "evidence/gate.log",
                "resolutionStatus": "open",
            }]
            record["earliestFailure"] = {
                "step": "cook",
                "reason": "cook failed",
                "logPath": "evidence/gate.log",
            }
            self.assertEqual([], validate_record(record, root))
            self.assertEqual("cook", record["earliestFailure"]["step"])
            self.assertEqual("cook failed", record["earliestFailure"]["reason"])
            self.assertEqual("evidence/gate.log", record["earliestFailure"]["logPath"])

    def test_ready_is_rejected_when_any_gate_evidence_or_issue_invariant_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._record_fixture(root)
            record["unresolvedIssues"] = [{
                "id": "release.issue",
                "gateId": "release.store.capsule_art",
                "reason": "evidence missing",
                "evidencePath": "evidence/missing/capsule.log",
                "resolutionStatus": "open",
            }]
            issues = validate_record(record, root)
            self.assertTrue(any(item.path == "unresolvedIssues" and item.code == "not_empty" for item in issues))
            self.assertFalse(record["unresolvedIssues"] == [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
