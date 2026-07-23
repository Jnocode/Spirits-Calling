#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio, version, packaged-launch and readiness-ingestion fixtures."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

try:
    from Scripts.audio_validation import AUDIO_NAMES, build_audio_report
    from Scripts.package_launch_smoke import parse_runtime_log, run_package_smoke
    from Scripts.readiness_record_validator import validate_record
    from Scripts.readiness_record_writer import attach_validation_reports, build_record
    from Scripts.test_readiness_record import ReadinessRecordFixtures
    from Scripts.version_consistency_validator import build_version_report
except ModuleNotFoundError:
    from audio_validation import AUDIO_NAMES, build_audio_report
    from package_launch_smoke import parse_runtime_log, run_package_smoke
    from readiness_record_validator import validate_record
    from readiness_record_writer import attach_validation_reports, build_record
    from test_readiness_record import ReadinessRecordFixtures
    from version_consistency_validator import build_version_report


class ReleaseValidationFixtures(unittest.TestCase):
    def _audio_tree(self, root: Path) -> tuple[Path, Path]:
        raw = root / "RawAssets" / "Audio"
        imported = root / "Content" / "Audio"
        raw.mkdir(parents=True)
        imported.mkdir(parents=True)
        for name in AUDIO_NAMES:
            with wave.open(str(raw / f"{name}.wav"), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(48000)
                handle.writeframes(b"\0\0" * 16)
            (imported / f"{name}.uasset").write_bytes(b"\xc1\x83\x2a\x9e" + b"imported-fixture")
        manifest = root / "package_manifest.json"
        manifest.write_text(json.dumps({"cookedObjects": [f"/Game/Audio/{name}.{name}" for name in AUDIO_NAMES]}), encoding="utf-8")
        ambient = root / "ambient.json"
        ambient.write_text(json.dumps({
            "executionMode": "live", "status": "pass",
            "assetPath": "/Game/Audio/S_Ambient", "loopEnabled": True,
        }), encoding="utf-8")
        return manifest, ambient

    def _version_tree(self, root: Path, version: str = "0.9.0") -> None:
        config = root / "Config"
        config.mkdir(parents=True, exist_ok=True)
        (config / "DefaultGame.ini").write_text(
            "[/Script/EngineSettings.GeneralProjectSettings]\n"
            f"ProjectVersion={version}\nProjectName=Spirits Calling\nCompanyName=XiuJiang Studio\n",
            encoding="utf-8",
        )
        (config / "SpiritsVersion.json").write_text(json.dumps({
            "projectVersion": "0.9.0", "displayVersion": "v0.9.0", "engineVersion": "5.8",
            "projectName": "Spirits Calling", "companyName": "XiuJiang Studio",
        }), encoding="utf-8")

    def test_audio_live_report_requires_raw_imported_cooked_and_ambient_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, ambient = self._audio_tree(root)
            report = build_audio_report(root, cooked_manifest=manifest, ambient_evidence=ambient)
            self.assertEqual("pass", report["status"])
            self.assertTrue(report["readinessEligible"])
            self.assertEqual(9, len(report["checks"]))
            self.assertTrue(all(item["status"] == "pass" for item in report["checks"]))

    def test_raw_wav_alone_never_becomes_import_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, ambient = self._audio_tree(root)
            (root / "Content" / "Audio" / "S_Victory.uasset").unlink()
            report = build_audio_report(root, cooked_manifest=manifest, ambient_evidence=ambient)
            victory = next(item for item in report["checks"] if item["name"] == "S_Victory")
            self.assertEqual("pass", victory["inventoryStatus"])
            self.assertEqual("blocked", victory["importStatus"])
            self.assertEqual("blocked", report["status"])

    def test_audio_malformed_wav_and_fixture_false_pass_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, ambient = self._audio_tree(root)
            (root / "RawAssets" / "Audio" / "S_Click.wav").write_bytes(b"not-wave")
            malformed = build_audio_report(root, cooked_manifest=manifest, ambient_evidence=ambient)
            self.assertEqual("fail", next(item for item in malformed["checks"] if item["name"] == "S_Click")["inventoryStatus"])
            fixture = build_audio_report(root, cooked_manifest=manifest, ambient_evidence=ambient, execution_mode="fixture")
            self.assertEqual("blocked", fixture["status"])
            self.assertFalse(fixture["readinessEligible"])
            (root / "Content" / "Audio" / "S_Click.uasset").write_bytes(b"not-an-unreal-package")
            invalid_import = build_audio_report(root, cooked_manifest=manifest, ambient_evidence=ambient)
            self.assertEqual("blocked", next(item for item in invalid_import["checks"] if item["name"] == "S_Click")["importStatus"])

    def test_version_consistency_success_mismatch_and_malformed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._version_tree(root)
            self.assertEqual("pass", build_version_report(root)["status"])
            self._version_tree(root, "0.9.1")
            mismatch = build_version_report(root)
            self.assertEqual("fail", mismatch["status"])
            self.assertIn("Version.Mismatch", {item["code"] for item in mismatch["failures"]})
            (root / "Config" / "SpiritsVersion.json").write_text("{bad", encoding="utf-8")
            malformed = build_version_report(root)
            self.assertIn("Version.MetadataLoadError", {item["code"] for item in malformed["failures"]})

    def test_launch_log_parser_has_stable_ready_missing_crash_and_hang_codes(self) -> None:
        clean = parse_runtime_log("LogInit: Game Engine Initialized\nLogLoad: Bringing World /Game/Maps/DemoMap\n")
        self.assertTrue(clean["ready"])
        self.assertEqual([], clean["findings"])
        unrelated = parse_runtime_log("LogInit: Game Engine Initialized\nDisplay: selected DemoMap option\n")
        self.assertFalse(unrelated["ready"])
        text = "\n".join([
            "TravelFailure: LoadMapFailure map /Game/Maps/Missing not found",
            "Failed to find object Class /Script/Missing",
            "Failed to load asset /Game/Audio/Missing",
            "Fatal error: unhandled exception",
            "Game thread timed out; hang detected",
        ])
        codes = {item["code"] for item in parse_runtime_log(text)["findings"]}
        self.assertTrue({"Package.MissingMap", "Package.MissingClass", "Package.MissingAsset", "Runtime.Crash", "Runtime.Hang"}.issubset(codes))

    def test_launch_missing_package_and_dry_run_never_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing = run_package_smoke(root / "missing.exe", log_path=root / "launch.log")
            self.assertEqual("blocked", missing["status"])
            dry = run_package_smoke(root / "missing.exe", log_path=root / "launch.log", dry_run=True)
            self.assertEqual("not_run", dry["status"])
            self.assertFalse(dry["readinessEligible"])

    @staticmethod
    def _launch_layout(root: Path) -> tuple[Path, Path]:
        executable = root / "Spirits_Calling.exe"
        executable.write_bytes(b"fixture-executable")
        (root / "Content" / "Paks").mkdir(parents=True)
        return executable, root / "launch.log"

    class _FakeProcess:
        def __init__(self, returncode: int | None = None):
            self.pid = 123
            self.returncode = returncode

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = -9

    def test_launch_lifecycle_ready_terminates_runner_owned_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable, log = self._launch_layout(Path(temp))
            process = self._FakeProcess()

            def popen(*args, **kwargs):
                kwargs["stdout"].write("LogInit: Game Engine Initialized\nLogLoad: Bringing World /Game/Maps/DemoMap\n")
                kwargs["stdout"].flush()
                return process

            module = run_package_smoke.__module__
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", side_effect=popen):
                report = run_package_smoke(executable, log_path=log)
            self.assertEqual("pass", report["status"])
            self.assertTrue(report["process"]["terminatedByRunner"])
            self.assertTrue(report["readinessEligible"])

    def test_launch_lifecycle_start_failure_and_early_exit_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable, log = self._launch_layout(Path(temp))
            module = run_package_smoke.__module__
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", side_effect=OSError("denied")):
                start_failure = run_package_smoke(executable, log_path=log)
            self.assertEqual("Launch.ProcessStartFailed", start_failure["findings"][-1]["code"])
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", return_value=self._FakeProcess(7)):
                early_exit = run_package_smoke(executable, log_path=log)
            self.assertEqual("fail", early_exit["status"])
            self.assertEqual("Launch.ProcessExited", early_exit["findings"][-1]["code"])

    def test_launch_lifecycle_hang_and_total_timeout_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable, log = self._launch_layout(Path(temp))
            module = run_package_smoke.__module__
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", return_value=self._FakeProcess()):
                hang = run_package_smoke(executable, log_path=log, timeout_seconds=1, hang_timeout_seconds=0.01)
            self.assertEqual("Runtime.Hang", hang["findings"][-1]["code"])
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", return_value=self._FakeProcess()):
                timeout = run_package_smoke(executable, log_path=log, timeout_seconds=0.01, hang_timeout_seconds=10)
            self.assertEqual("Launch.Timeout", timeout["findings"][-1]["code"])

    def test_launch_invalid_ready_regex_is_blocked_before_process_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable, log = self._launch_layout(Path(temp))
            module = run_package_smoke.__module__
            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen") as popen:
                report = run_package_smoke(executable, log_path=log, ready_patterns=["("])
            self.assertEqual("blocked", report["status"])
            self.assertEqual("Launch.InvalidReadyPattern", report["findings"][-1]["code"])
            popen.assert_not_called()

    @staticmethod
    def _write_report(root: Path, filename: str, report_type: str) -> Path:
        evidence = root / "evidence" / "gate.log"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("locatable\n", encoding="utf-8")
        base = {
            "schemaVersion": "1.0", "reportType": report_type, "executionMode": "live",
            "status": "pass", "readinessEligible": True, "evidencePaths": [str(evidence)],
        }
        if report_type == "package_closure":
            package = root / "Builds" / "Windows"
            (package / "Content" / "Paks").mkdir(parents=True, exist_ok=True)
            manifest = root / "PackageManifest.json"
            manifest.write_text("{}", encoding="utf-8")
            base.update({
                "valid": True, "errorCount": 0, "errors": [], "packagePath": str(package),
                "ioStoreManifestPath": str(manifest), "evidencePaths": [str(manifest)],
            })
        elif report_type == "package_launch":
            package = root / "Builds" / "Windows"
            (package / "Content" / "Paks").mkdir(parents=True, exist_ok=True)
            executable = package / "Spirits_Calling.exe"
            executable.write_bytes(b"fixture-exe")
            base.update({
                "signals": {"ready": True}, "findings": [], "executablePath": str(executable),
                "logPath": str(evidence), "packagePath": str(package),
                "process": {"started": True, "pid": 123, "terminatedByRunner": True, "exitCode": -15},
            })
        elif report_type == "audio_validation":
            sources = (
                "RawAssets/Audio/S_Alarm.wav", "RawAssets/Audio/S_Ambient.wav", "RawAssets/Audio/S_Attack.wav",
                "RawAssets/Audio/S_Click.wav", "RawAssets/Audio/S_Death.wav", "RawAssets/Audio/S_Defeat.wav",
                "RawAssets/Audio/S_Hit.wav", "RawAssets/Audio/S_Summon.wav", "RawAssets/Audio/S_Victory.wav",
            )
            checks = []
            for source in sources:
                raw = root / source
                imported = root / "Content" / "Audio" / f"{raw.stem}.uasset"
                raw.parent.mkdir(parents=True, exist_ok=True)
                imported.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(b"fixture-wave")
                imported.write_bytes(b"\xc1\x83\x2a\x9e" + b"fixture-uasset")
                checks.append({
                    "id": f"audio.import.{raw.stem}", "source": source,
                    "importedAsset": f"Content/Audio/{raw.stem}.uasset", "runtimeObject": f"/Game/Audio/{raw.stem}",
                    "inventoryStatus": "pass", "importStatus": "pass", "cookStatus": "pass", "status": "pass",
                })
            base.update({"checks": checks, "ambient": {"status": "pass", "evidencePath": str(evidence)}})
        elif report_type == "version_consistency":
            base.update({
                "projectVersion": "0.9.0",
                "comparisons": [
                    {"iniField": "ProjectVersion", "metadataField": "projectVersion", "iniValue": "0.9.0", "metadataValue": "0.9.0", "matches": True},
                    {"iniField": "ProjectName", "metadataField": "projectName", "iniValue": "Spirits Calling", "metadataValue": "Spirits Calling", "matches": True},
                    {"iniField": "CompanyName", "metadataField": "companyName", "iniValue": "XiuJiang Studio", "metadataValue": "XiuJiang Studio", "matches": True},
                ],
                "failures": [],
            })
        path = root / filename
        path.write_text(json.dumps(base), encoding="utf-8")
        return path

    def test_readiness_ingestion_only_upgrades_corresponding_live_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = build_record([], {}, str(root))
            paths = {
                "closure_report": self._write_report(root, "closure.json", "package_closure"),
                "launch_report": self._write_report(root, "launch.json", "package_launch"),
                "audio_report": self._write_report(root, "audio.json", "audio_validation"),
                "version_report": self._write_report(root, "version.json", "version_consistency"),
            }
            updated = attach_validation_reports(record, str(root), **{key: str(path) for key, path in paths.items()})
            by_id = {gate["id"]: gate for gate in updated["gates"]}
            self.assertEqual("pass", by_id["validation.package_closure"]["status"])
            self.assertEqual("pass", by_id["validation.package_launch"]["status"])
            self.assertEqual("pass", by_id["validation.version_consistency"]["status"])
            self.assertEqual("pass", by_id["release.audio.imports"]["status"])
            for gate_id in ("release.steam.account_app_id", "release.store.capsule_art", "release.legal.eula_privacy"):
                self.assertEqual("not_run", by_id[gate_id]["status"])
            self.assertEqual("not_run", updated["stability"]["status"])
            self.assertEqual("blocked", updated["packageAcceptance"])
            evidence_ids = {item["id"] for item in updated["evidence"]}
            for gate_id in ("validation.package_closure", "validation.package_launch", "validation.version_consistency", "release.audio.imports"):
                self.assertNotIn(gate_id + ".evidence", evidence_ids)
                self.assertIn(gate_id + ".report", evidence_ids)

    def test_duplicate_audio_rows_cannot_upgrade_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self._write_report(root, "audio.json", "audio_validation")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["checks"] = [payload["checks"][0].copy() for _ in range(9)]
            path.write_text(json.dumps(payload), encoding="utf-8")
            record = attach_validation_reports(build_record([], {}, str(root)), str(root), audio_report=str(path))
            gate = next(item for item in record["gates"] if item["id"] == "release.audio.imports")
            self.assertEqual("blocked", gate["status"])

    def test_anonymous_version_comparison_cannot_upgrade_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self._write_report(root, "version.json", "version_consistency")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["comparisons"] = [{"matches": True}]
            path.write_text(json.dumps(payload), encoding="utf-8")
            record = attach_validation_reports(build_record([], {}, str(root)), str(root), version_report=str(path))
            gate = next(item for item in record["gates"] if item["id"] == "validation.version_consistency")
            self.assertEqual("blocked", gate["status"])

    def test_fixture_report_cannot_upgrade_and_manual_false_pass_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture_path = self._write_report(root, "launch.json", "package_launch")
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            payload["executionMode"] = "fixture"
            fixture_path.write_text(json.dumps(payload), encoding="utf-8")
            record = attach_validation_reports(build_record([], {}, str(root)), str(root), launch_report=str(fixture_path))
            gate = next(item for item in record["gates"] if item["id"] == "validation.package_launch")
            self.assertEqual("not_run", gate["status"])

            ready = ReadinessRecordFixtures()._ready_record(str(root))
            launch_report = root / "evidence" / "package_launch.json"
            payload = json.loads(launch_report.read_text(encoding="utf-8"))
            payload["executionMode"] = "fixture"
            launch_report.write_text(json.dumps(payload), encoding="utf-8")
            issues = validate_record(ready, str(root))
            self.assertTrue(any(item.code == "fabricated_pass" for item in issues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
