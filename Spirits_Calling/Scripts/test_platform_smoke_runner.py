#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixture/schema tests for the PCVR hardware evidence adapter."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

try:
    from Scripts.platform_smoke_runner import (
        REQUIRED_CASES,
        attach_hardware_evidence,
        build_hardware_evidence,
        normalize_run,
    )
    from Scripts.readiness_record_validator import validate_record
    from Scripts.readiness_record_writer import build_record
except ModuleNotFoundError:
    from platform_smoke_runner import REQUIRED_CASES, attach_hardware_evidence, build_hardware_evidence, normalize_run
    from readiness_record_validator import validate_record
    from readiness_record_writer import build_record


class PlatformSmokeRunnerFixtures(unittest.TestCase):
    def _live_run(self, root: str, adapter: str = "quest_link") -> dict:
        cases = {}
        for case_id in REQUIRED_CASES:
            path = os.path.join(root, f"{case_id}.log")
            Path(path).write_text(f"live {case_id}\n", encoding="utf-8")
            cases[case_id] = {"status": "pass", "logPath": path}
        return {
            "id": f"pcvr.{adapter}.2026-03-31",
            "adapter": adapter,
            "executionMode": "live",
            "status": "pass",
            "buildVersion": "0.9.0",
            "sourceRevision": "abc1234",
            "hmd": "Meta Quest 3",
            "runtime": "OpenXR via Quest Link",
            "hardwarePresent": True,
            "modeSelection": {"selectedMode": "PCVR_Mode", "detected": True},
            "machine": {"os": "Windows 11", "cpu": "CPU", "gpu": "GPU", "ram": "32 GB"},
            "cases": cases,
        }

    def test_fixture_pass_is_downgraded_and_never_claims_hardware(self) -> None:
        row = normalize_run({
            "adapter": "quest_link",
            "executionMode": "fixture",
            "status": "pass",
            "hardwarePresent": True,
            "hmd": "fake HMD",
            "runtime": "fake runtime",
            "modeSelection": {"selectedMode": "PCVR_Mode"},
            "cases": {case_id: {"status": "pass"} for case_id in REQUIRED_CASES},
        })
        self.assertEqual("not_run", row["status"])
        self.assertTrue(any("fixture" in reason for reason in row["failureReasons"]))
        self.assertTrue(all(case["status"] == "not_run" for case in row["cases"]))

    def test_missing_hardware_always_lists_quest_link_as_not_run(self) -> None:
        evidence = build_hardware_evidence([], project_root=os.getcwd())
        self.assertEqual(["quest_link"], [run["adapter"] for run in evidence["runs"]])
        self.assertEqual("not_run", evidence["runs"][0]["status"])
        self.assertFalse(evidence["runs"][0]["hardwarePresent"])

    def test_live_run_requires_real_profile_and_locatable_case_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            row = normalize_run(self._live_run(root), project_root=root)
            self.assertEqual("pass", row["status"])
            self.assertEqual("PCVR_Mode", row["modeSelection"]["selectedMode"])
            self.assertEqual(set(REQUIRED_CASES), {case["id"] for case in row["cases"]})

    def test_writer_adds_per_case_smoke_rows_without_fabricating_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = build_record([], {}, root)
            updated = attach_hardware_evidence(record, {"runs": [self._live_run(root)]}, root)
            self.assertEqual("pass", updated["hardwareEvidence"]["runs"][0]["status"])
            ids = {case["id"] for case in updated["smokeMatrix"]["cases"]}
            self.assertTrue({f"pcvr.quest_link.{case_id}" for case_id in REQUIRED_CASES}.issubset(ids))
            issues = validate_record(updated, root)
            hardware_issues = [issue for issue in issues if issue.path.startswith("hardwareEvidence")]
            self.assertEqual([], hardware_issues)

    def test_live_steamvr_run_is_included_when_hardware_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            evidence = build_hardware_evidence([self._live_run(root, "steamvr")], project_root=root)
            self.assertEqual(["quest_link", "steamvr"], [run["adapter"] for run in evidence["runs"]])
            self.assertEqual("pass", evidence["runs"][1]["status"])
            self.assertEqual(set(REQUIRED_CASES), {case["id"] for case in evidence["runs"][1]["cases"]})
            self.assertEqual(5, len(evidence["runs"][1]["evidencePaths"]))

    def test_live_pass_with_missing_hardware_profile_cannot_remain_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._live_run(root)
            run["hmd"] = "not-recorded"
            row = normalize_run(run, project_root=root)
            self.assertEqual("fail", row["status"])
            self.assertIn("HMD model is not recorded", row["failureReasons"])

    def test_live_pass_with_undetected_mode_selection_cannot_remain_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._live_run(root)
            run["modeSelection"]["detected"] = False
            row = normalize_run(run, project_root=root)
            self.assertEqual("fail", row["status"])
            self.assertIn("mode selection was not detected", row["failureReasons"][-1])

    def test_live_pass_with_incomplete_machine_or_build_metadata_cannot_remain_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._live_run(root)
            run["machine"]["gpu"] = "not-recorded"
            run["sourceRevision"] = "not-recorded"
            row = normalize_run(run, project_root=root)
            self.assertEqual("fail", row["status"])
            self.assertTrue(any("machine profile" in reason for reason in row["failureReasons"]))
            self.assertTrue(any("build version" in reason for reason in row["failureReasons"]))

    def test_validator_rejects_manually_fabricated_fixture_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            record = build_record([], {}, root)
            record["hardwareEvidence"]["runs"][0]["status"] = "pass"
            issues = validate_record(record, root)
            self.assertTrue(any(issue.code in {"fabricated_pass", "missing_hardware", "wrong_mode"} for issue in issues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
