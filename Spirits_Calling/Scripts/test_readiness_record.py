#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixture tests for the Release_Readiness_Record schema and invariants."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

try:
    from Scripts.readiness_record_validator import (
        AUDIO_SOURCE_PATHS,
        REQUIRED_RELEASE_GATE_IDS,
        load_and_validate,
        validate_record,
        validate_scope_text,
    )
    from Scripts.readiness_record_writer import attach_validation_reports, build_record, write_record
except ModuleNotFoundError:  # Direct execution: python Scripts/test_readiness_record.py
    from readiness_record_validator import (
        AUDIO_SOURCE_PATHS,
        REQUIRED_RELEASE_GATE_IDS,
        load_and_validate,
        validate_record,
        validate_scope_text,
    )
    from readiness_record_writer import attach_validation_reports, build_record, write_record


class ReadinessRecordFixtures(unittest.TestCase):
    def test_json_schema_declares_record_contract(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "Docs" / "Release" / "Release_Readiness_Record.schema.json"
        with schema_path.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        required = set(schema["required"])
        self.assertTrue({
            "packageVersion", "sourceRevision", "cookMaps", "launchLog", "smokeMatrix",
            "gates", "evidence", "unresolvedIssues", "earliestFailure", "releaseScope", "stability",
        }.issubset(required))
        self.assertEqual("5.8", schema["properties"]["engineVersion"]["const"])
        self.assertTrue(schema["properties"]["ioStore"]["const"])
        gate = schema["$defs"]["gate"]
        self.assertIn("allOf", gate)
        self.assertEqual(["failureReason", "resolutionStatus"], gate["allOf"][0]["else"]["required"])
        self.assertIn("checks", gate["properties"])
        self.assertEqual("object", schema["$defs"]["evidence"]["type"])
        self.assertIn("releaseScope", schema["$defs"])
        hardware = schema["$defs"]["hardwareRun"]
        self.assertTrue({
            "adapter", "executionMode", "hmd", "runtime", "hardwarePresent",
            "modeSelection", "machine", "cases", "evidencePaths", "failureReasons",
        }.issubset(set(hardware["required"])))
        self.assertEqual({"quest_link", "steamvr"}, set(hardware["properties"]["adapter"]["enum"]))
        self.assertIn("unresolvedIssue", schema["$defs"])

    def test_scope_validator_requires_supported_modes_and_excludes_unshipped_claims(self) -> None:
        valid = "PC single-player; LAN/friend connection; PCVR. public matchmaking is not shipped."
        self.assertEqual([], validate_scope_text(valid))
        invalid = "PC single-player and public matchmaking are shipped with dedicated servers."
        codes = {item.code for item in validate_scope_text(invalid)}
        self.assertIn("missing_scope", codes)
        self.assertIn("forbidden_shipped_claim", codes)

    def test_release_gate_set_is_explicit_and_audio_is_enumerated(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._ready_record(root)
            gate_ids = {gate["id"] for gate in record["gates"]}
            self.assertTrue(set(REQUIRED_RELEASE_GATE_IDS).issubset(gate_ids))
            audio = next(gate for gate in record["gates"] if gate["id"] == "release.audio.imports")
            self.assertEqual(set(AUDIO_SOURCE_PATHS), {item["source"] for item in audio["checks"][:-1]})
            self.assertEqual("audio.ambient.loop_or_fallback", audio["checks"][-1]["id"])
            self.assertEqual([], validate_record(record, root))

    def _ready_record(self, root: str) -> dict:
        os.makedirs(os.path.join(root, "Builds", "Windows"), exist_ok=True)
        os.makedirs(os.path.join(root, "evidence"), exist_ok=True)
        Path(root, "Builds", "Windows", "Spirits_Calling.exe").write_bytes(b"fixture-exe")
        Path(root, "Builds", "Windows", "Content", "Paks").mkdir(parents=True, exist_ok=True)
        Path(root, "evidence", "package_manifest.json").write_text("{}", encoding="utf-8")
        for source in AUDIO_SOURCE_PATHS:
            raw = Path(root, source)
            imported = Path(root, "Content", "Audio", raw.stem + ".uasset")
            raw.parent.mkdir(parents=True, exist_ok=True)
            imported.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(b"fixture-wave")
            imported.write_bytes(b"\xc1\x83\x2a\x9e" + b"fixture-uasset")
        for name in ("launch.log", "easy.log", "gate.log", "stability.log"):
            with open(os.path.join(root, "evidence", name), "w", encoding="utf-8") as handle:
                handle.write("fixture\n")
        with open(os.path.join(root, "scope.md"), "w", encoding="utf-8") as handle:
            handle.write("PC single-player; LAN/friend connection; PCVR.\n"
                         "public matchmaking is not shipped. dedicated servers are not shipped. "
                         "Nakama authentication is not shipped. anti-cheat is not shipped.\n")
        report_base = {
            "schemaVersion": "1.0", "executionMode": "live", "status": "pass",
            "readinessEligible": True, "evidencePaths": ["evidence/gate.log"],
        }
        reports = {
            "package_closure.json": {
                **report_base, "reportType": "package_closure", "valid": True, "errorCount": 0, "errors": [],
                "packagePath": "Builds/Windows", "ioStoreManifestPath": "evidence/package_manifest.json",
                "evidencePaths": ["evidence/package_manifest.json"],
            },
            "package_launch.json": {
                **report_base, "reportType": "package_launch", "signals": {"ready": True}, "findings": [],
                "executablePath": "Builds/Windows/Spirits_Calling.exe", "packagePath": "Builds/Windows", "logPath": "evidence/launch.log",
                "process": {"started": True, "pid": 123, "terminatedByRunner": True, "exitCode": -15},
            },
            "audio_validation.json": {
                **report_base, "reportType": "audio_validation",
                "checks": [{
                    "id": f"audio.import.{Path(source).stem}", "source": source,
                    "importedAsset": f"Content/Audio/{Path(source).stem}.uasset",
                    "runtimeObject": f"/Game/Audio/{Path(source).stem}",
                    "inventoryStatus": "pass", "importStatus": "pass", "cookStatus": "pass", "status": "pass",
                } for source in AUDIO_SOURCE_PATHS],
                "ambient": {"status": "pass", "evidencePath": "evidence/gate.log"},
            },
            "version_consistency.json": {
                **report_base, "reportType": "version_consistency", "projectVersion": "0.9.0",
                "comparisons": [
                    {"iniField": "ProjectVersion", "metadataField": "projectVersion", "iniValue": "0.9.0", "metadataValue": "0.9.0", "matches": True},
                    {"iniField": "ProjectName", "metadataField": "projectName", "iniValue": "Spirits Calling", "metadataValue": "Spirits Calling", "matches": True},
                    {"iniField": "CompanyName", "metadataField": "companyName", "iniValue": "XiuJiang Studio", "metadataValue": "XiuJiang Studio", "matches": True},
                ], "failures": [],
            },
        }
        for filename, payload in reports.items():
            with open(os.path.join(root, "evidence", filename), "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        release_gates = []
        for gate_id in REQUIRED_RELEASE_GATE_IDS:
            gate = {
                "id": gate_id,
                "owner": "fixture-owner",
                "priority": "P0",
                "status": "pass",
                "evidencePath": "evidence/gate.log",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            if gate_id == "release.audio.imports":
                gate["evidencePath"] = "evidence/audio_validation.json"
                gate["checks"] = [
                    {"id": f"audio.import.{Path(source).stem}", "source": source, "status": "pass", "evidencePath": "evidence/audio_validation.json"}
                    for source in AUDIO_SOURCE_PATHS
                ] + [{"id": "audio.ambient.loop_or_fallback", "source": "Content/Audio/S_Ambient.uasset", "status": "pass", "evidencePath": "evidence/audio_validation.json"}]
            release_gates.append(gate)
        automated_gates = [
            {"id": "validation.package_closure", "owner": "fixture-owner", "priority": "P0", "status": "pass", "evidencePath": "evidence/package_closure.json", "timestamp": "2026-01-01T00:00:00Z"},
            {"id": "validation.package_launch", "owner": "fixture-owner", "priority": "P0", "status": "pass", "evidencePath": "evidence/package_launch.json", "timestamp": "2026-01-01T00:00:00Z"},
            {"id": "validation.version_consistency", "owner": "fixture-owner", "priority": "P0", "status": "pass", "evidencePath": "evidence/version_consistency.json", "timestamp": "2026-01-01T00:00:00Z"},
        ]
        return {
            "schemaVersion": "1.0",
            "packageAcceptance": "ready",
            "packageVersion": "0.9.0",
            "sourceRevision": "abc1234",
            "engineVersion": "5.8",
            "cookMaps": ["/Game/Maps/DemoMap"],
            "platform": "Win64",
            "configuration": "Shipping",
            "ioStore": True,
            "packagePath": "Builds/Windows",
            "launchLog": "evidence/launch.log",
            "smokeMatrix": {
                "cases": [
                    {"id": "smoke.easy", "status": "pass", "evidencePath": "evidence/easy.log"},
                    {"id": "package.launch", "status": "pass", "evidencePath": "evidence/package_launch.json"},
                ]
            },
            "gates": [{
                "id": "package.acceptance",
                "owner": "release",
                "priority": "P0",
                "status": "pass",
                "evidencePath": "evidence/gate.log",
                "timestamp": "2026-01-01T00:00:00Z",
            }] + release_gates + automated_gates,
            "evidence": [{"id": "package.acceptance.evidence", "path": "evidence/gate.log"}],
            "unresolvedIssues": [],
            "earliestFailure": None,
            "machine": {"os": "Windows", "cpu": "CPU", "gpu": "GPU", "ram": "32 GB"},
            "stability": {
                "status": "pass",
                "measurementStatus": "pass",
                "readinessEligible": True,
                "executionMode": "live",
                "evidenceSource": "evidence/gate.log",
                "requestedDurationSeconds": 1800,
                "observedDurationSeconds": 1800,
                "queryTimeoutSeconds": 5,
                "maxAllowedHangSeconds": 10,
                "startedAt": "2026-01-01T00:00:00Z",
                "endedAt": "2026-01-01T00:30:00Z",
                "crashDetected": False,
                "crashTimestamp": None,
                "hangDetected": False,
                "maxConsecutiveHangSeconds": 0,
                "queries": [{"timestamp": "2026-01-01T00:05:00Z", "latencySeconds": 0.1, "responded": True}],
                "memory": {
                    "atFiveMinutes": {"timestamp": "2026-01-01T00:05:00Z", "privateWorkingSetBytes": 100},
                    "atEnd": {"timestamp": "2026-01-01T00:30:00Z", "privateWorkingSetBytes": 110},
                    "growthRatio": 0.1, "maxGrowthRatio": 0.2, "withinThreshold": True,
                },
                "machine": {"os": "Windows", "cpu": "CPU", "gpu": "GPU", "ram": "32 GB"},
                "failureReasons": ["none"],
            },
            "releaseScope": {
                "documentPath": "scope.md",
                "includedCapabilities": ["PC single-player", "LAN/friend connection", "PCVR"],
                "excludedCapabilities": ["public matchmaking", "dedicated servers", "Nakama authentication", "anti-cheat"],
            },
        }

    def test_complete_ready_record_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual([], validate_record(self._ready_record(root), root))

    def test_load_and_validate_infers_uproject_root_for_relative_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            Path(root, "Game.uproject").write_text("{}", encoding="utf-8")
            record = self._ready_record(root)
            record_path = Path(root, "Docs", "Release", "record.json")
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps(record), encoding="utf-8")

            loaded, issues = load_and_validate(str(record_path))

            self.assertEqual("ready", loaded["packageAcceptance"])
            self.assertEqual([], issues)

    def test_ready_record_with_missing_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._ready_record(root)
            record["gates"][0]["evidencePath"] = "evidence/missing.log"
            issues = validate_record(record, root)
            self.assertTrue(any(item.code == "unlocatable" for item in issues))

    def test_failed_gate_requires_earliest_reproducible_failure(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._ready_record(root)
            record["packageAcceptance"] = "blocked"
            record["gates"][0].update({
                "status": "fail",
                "failureReason": "cook failed",
                "resolutionStatus": "open",
            })
            record["unresolvedIssues"] = [{
                "id": "issue-1",
                "gateId": "package.acceptance",
                "reason": "cook failed",
                "evidencePath": "evidence/gate.log",
                "resolutionStatus": "open",
            }]
            record["earliestFailure"] = None
            issues = validate_record(record, root)
            self.assertTrue(any(item.code == "missing" for item in issues))

    def test_failed_gate_requires_reason_and_resolution_status(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._ready_record(root)
            record["packageAcceptance"] = "blocked"
            record["gates"][0]["status"] = "fail"
            record["unresolvedIssues"] = [{
                "id": "issue-1",
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
            issues = validate_record(record, root)
            codes = {item.code for item in issues}
            self.assertIn("missing_or_empty", codes)

    def test_missing_required_record_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = self._ready_record(root)
            del record["smokeMatrix"]
            issues = validate_record(record, root)
            self.assertTrue(any(item.path == "smokeMatrix" and item.code == "missing" for item in issues))

    def test_writer_converts_legacy_smoke_results_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            results = [("A1 編譯綠燈", "FAIL", "compiler error")]
            smoke = {"B1 單機-簡單": {"status": "SKIP", "note": ""}}
            record = build_record(results, smoke, root)
            self.assertEqual("blocked", record["packageAcceptance"])
            self.assertEqual("A1 編譯綠燈", record["earliestFailure"]["step"])
            self.assertEqual("evidence/missing/preflight.build.missing", record["earliestFailure"]["logPath"])
            output = os.path.join(root, "Docs", "Release", "record.json")
            issues = write_record(record, output, base_dir=root)
            self.assertTrue(issues)
            self.assertTrue(os.path.exists(output))
            self.assertTrue(os.path.exists(os.path.splitext(output)[0] + ".md"))
            with open(output, encoding="utf-8") as handle:
                json.load(handle)


if __name__ == "__main__":
    unittest.main(verbosity=2)
