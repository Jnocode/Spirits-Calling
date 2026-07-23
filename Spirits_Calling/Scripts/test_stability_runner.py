#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic boundary tests for the stability telemetry evaluator."""
from __future__ import annotations

import copy
import tempfile
import unittest

try:
    from Scripts.stability_runner import assess_telemetry
    from Scripts.readiness_record_writer import build_record
except ModuleNotFoundError:
    from stability_runner import assess_telemetry
    from readiness_record_writer import build_record


class StabilityTelemetryFixtures(unittest.TestCase):
    def _fixture(self) -> dict:
        return {
            "executionMode": "fixture",
            "requestedDurationSeconds": 1800,
            "observedDurationSeconds": 1800,
            "startedAt": "2026-01-01T00:00:00Z",
            "endedAt": "2026-01-01T00:30:00Z",
            "machine": {"os": "fixture-os", "cpu": "fixture-cpu", "gpu": "fixture-gpu", "ram": "fixture-ram"},
            "queries": [
                {"timestamp": "2026-01-01T00:05:00Z", "latencySeconds": 0.1, "responded": True},
                {"timestamp": "2026-01-01T00:30:00Z", "latencySeconds": 5.0, "responded": True},
            ],
            "memory": {
                "atFiveMinutes": {"timestamp": "2026-01-01T00:05:00Z", "privateWorkingSetBytes": 1000},
                "atEnd": {"timestamp": "2026-01-01T00:30:00Z", "privateWorkingSetBytes": 1200},
            },
            "crashDetected": False,
            "processEndedEarly": False,
        }

    def test_valid_fixture_is_measurement_pass_but_not_release_pass(self) -> None:
        result = assess_telemetry(self._fixture())
        self.assertEqual("pass", result["measurementStatus"])
        self.assertEqual("not_run", result["status"])
        self.assertFalse(result["readinessEligible"])
        self.assertEqual(0.2, result["memory"]["growthRatio"])

    def test_memory_growth_above_twenty_percent_fails(self) -> None:
        fixture = self._fixture()
        fixture["memory"]["atEnd"]["privateWorkingSetBytes"] = 1201
        result = assess_telemetry(fixture)
        self.assertEqual("fail", result["measurementStatus"])
        self.assertIn("private working set growth exceeded 20 percent", result["failureReasons"])

    def test_query_latency_above_five_seconds_fails(self) -> None:
        fixture = self._fixture()
        fixture["queries"][0]["latencySeconds"] = 5.001
        result = assess_telemetry(fixture)
        self.assertEqual("fail", result["measurementStatus"])
        self.assertIn("query 0 exceeded the 5 second response limit", result["failureReasons"])

    def test_missing_machine_profile_fails_closed(self) -> None:
        fixture = self._fixture()
        fixture["machine"] = {"os": "fixture-os", "cpu": "", "gpu": "fixture-gpu", "ram": "fixture-ram"}
        result = assess_telemetry(fixture)
        self.assertEqual("fail", result["measurementStatus"])
        self.assertIn("OS, CPU, GPU and RAM machine profile is incomplete", result["failureReasons"])

    def test_incomplete_duration_fails_even_when_other_measurements_are_good(self) -> None:
        fixture = self._fixture()
        fixture["observedDurationSeconds"] = 1799.999
        result = assess_telemetry(fixture)
        self.assertEqual("fail", result["measurementStatus"])
        self.assertIn("observed duration is shorter than 1800 seconds", result["failureReasons"])

    def test_writer_does_not_promote_fixture_to_release_pass(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            telemetry = assess_telemetry(self._fixture())
            record = build_record([], {"B6 30分掛機": {"status": "PASS", "stability": telemetry}}, root)
            self.assertEqual("not_run", record["stability"]["status"])
            b6_id = next(case["id"] for case in record["smokeMatrix"]["cases"] if case["id"].startswith("smoke.b6"))
            b6 = next(gate for gate in record["gates"] if gate["id"] == b6_id)
            self.assertEqual("not_run", b6["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
