#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed fixtures for staged package launch, 5-minute FPS, and LAN convergence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from Scripts.package_launch_smoke import parse_runtime_log, parse_stage_progress, run_package_smoke
    from Scripts.fps_smoke_runner import (
        MIN_WINDOW_SECONDS,
        TARGET_AVERAGE_FPS,
        evaluate_fps_window,
    )
    from Scripts.lan_smoke_runner import evaluate_lan_run, parse_lan_log
except ModuleNotFoundError:
    from package_launch_smoke import parse_runtime_log, parse_stage_progress, run_package_smoke
    from fps_smoke_runner import MIN_WINDOW_SECONDS, TARGET_AVERAGE_FPS, evaluate_fps_window
    from lan_smoke_runner import evaluate_lan_run, parse_lan_log


MENU_LOG = "LogInit: Game Engine Initialized\nLogTemp: Display: [SpiritsSmoke] Stage=MenuReady\n"
MAP_LOG = "LogLoad: Bringing World /Game/Maps/DemoMap\n"
IN_PROGRESS_LOG = "LogTemp: Display: [SpiritsSmoke] Stage=MatchInProgress\n"


class StagedLaunchParsing(unittest.TestCase):
    def test_stage_progress_detects_menu_and_match_markers(self) -> None:
        self.assertEqual(["title_menu"], parse_stage_progress(MENU_LOG))
        self.assertEqual(["title_menu"], parse_stage_progress(MAP_LOG))  # map-ready satisfies title stage
        self.assertEqual(["title_menu", "pc_in_progress"], parse_stage_progress(MENU_LOG + IN_PROGRESS_LOG))
        self.assertEqual([], parse_stage_progress("LogInit: nothing relevant here\n"))

    def test_required_stage_tightens_readiness_without_breaking_default(self) -> None:
        # Backward-compatible default: DemoMap ready alone is ready, and reports stages.
        default = parse_runtime_log(MAP_LOG)
        self.assertTrue(default["ready"])
        self.assertEqual(["title_menu"], default["stages"])

        # Requiring the in-progress stage is not satisfied by the menu alone.
        menu_only = parse_runtime_log(MENU_LOG, required_stages=["title_menu", "pc_in_progress"])
        self.assertFalse(menu_only["ready"])

        both = parse_runtime_log(MAP_LOG + MENU_LOG + IN_PROGRESS_LOG, required_stages=["title_menu", "pc_in_progress"])
        self.assertTrue(both["ready"])

    def test_unknown_required_stage_is_blocked_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Spirits_Calling.exe"
            exe.write_bytes(b"fixture")
            report = run_package_smoke(exe, log_path=root / "l.log", required_stages=["nonsense"])
            self.assertEqual("blocked", report["status"])
            self.assertEqual("Launch.InvalidStage", report["findings"][-1]["code"])

    def test_dry_run_with_required_stages_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = run_package_smoke(root / "missing.exe", log_path=root / "l.log",
                                       dry_run=True, required_stages=["title_menu"])
            self.assertEqual("not_run", report["status"])
            self.assertFalse(report["readinessEligible"])
            self.assertEqual(["title_menu"], report["requiredStages"])

    def test_live_two_stage_launch_passes_only_when_both_markers_appear(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Spirits_Calling.exe"
            exe.write_bytes(b"fixture")
            (root / "Content" / "Paks").mkdir(parents=True)
            log = root / "launch.log"
            module = run_package_smoke.__module__

            class _Proc:
                pid = 1
                returncode = None

                def poll(self):
                    return self.returncode

                def terminate(self):
                    self.returncode = -15

                def wait(self, timeout=None):
                    return self.returncode

                def kill(self):
                    self.returncode = -9

            def popen(*args, **kwargs):
                kwargs["stdout"].write(MAP_LOG + MENU_LOG + IN_PROGRESS_LOG)
                kwargs["stdout"].flush()
                return _Proc()

            with mock.patch(f"{module}.platform.platform", return_value="Windows"), mock.patch(
                f"{module}.platform.processor", return_value="CPU"
            ), mock.patch(f"{module}.subprocess.Popen", side_effect=popen):
                report = run_package_smoke(exe, log_path=log, required_stages=["title_menu", "pc_in_progress"])
            self.assertEqual("pass", report["status"])
            self.assertEqual(["title_menu", "pc_in_progress"], report["stagesReached"])
            self.assertTrue(report["readinessEligible"])


class FpsWindowEvaluation(unittest.TestCase):
    def _live_samples(self, *, seconds: float = MIN_WINDOW_SECONDS, fps: float = 95.0) -> list[dict]:
        step = 1.0
        count = int(seconds / step) + 1
        return [{"t": i * step, "fps": fps, "activeWave": True} for i in range(count)]

    def _live_kwargs(self) -> dict:
        return {
            "execution_mode": "live",
            "machine": {"os": "Windows 11", "cpu": "CPU", "gpu": "GPU", "ram": "32 GB"},
            "build_version": "0.9.0",
            "source_revision": "abc1234",
        }

    def test_fixture_samples_never_pass_hardware_fps(self) -> None:
        report = evaluate_fps_window(self._live_samples(), execution_mode="fixture",
                                     machine={"os": "x", "cpu": "x", "gpu": "x", "ram": "x"},
                                     build_version="0.9.0", source_revision="abc")
        self.assertEqual("not_run", report["status"])
        self.assertFalse(report["readinessEligible"])

    def test_live_window_passes_at_five_minutes_and_ninety_fps(self) -> None:
        report = evaluate_fps_window(self._live_samples(fps=91.0), **self._live_kwargs())
        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["windowSeconds"], MIN_WINDOW_SECONDS)
        self.assertGreaterEqual(report["averageFps"], TARGET_AVERAGE_FPS)

    def test_live_short_window_fails_closed(self) -> None:
        report = evaluate_fps_window(self._live_samples(seconds=120.0), **self._live_kwargs())
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("under the required" in reason and "s" in reason for reason in report["failureReasons"]))

    def test_live_low_average_fails_closed(self) -> None:
        report = evaluate_fps_window(self._live_samples(fps=72.0), **self._live_kwargs())
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("FPS" in reason for reason in report["failureReasons"]))

    def test_live_incomplete_metadata_fails_closed(self) -> None:
        kwargs = self._live_kwargs()
        kwargs["machine"]["gpu"] = "not-recorded"
        kwargs["source_revision"] = "not-recorded"
        report = evaluate_fps_window(self._live_samples(), **kwargs)
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("machine profile" in reason for reason in report["failureReasons"]))
        self.assertTrue(any("build version" in reason for reason in report["failureReasons"]))


class LanConvergenceEvaluation(unittest.TestCase):
    HOST = MENU_LOG + IN_PROGRESS_LOG
    CLIENT = MENU_LOG + IN_PROGRESS_LOG

    def test_parse_lan_log_extracts_markers(self) -> None:
        parsed = parse_lan_log(self.HOST + "LogTemp: Warning: [Match] connection error [Match.Disconnected]\n")
        self.assertTrue(parsed["menuReady"])
        self.assertTrue(parsed["matchInProgress"])
        self.assertTrue(parsed["disconnected"])
        self.assertFalse(parsed["joinFailed"])

    def test_fixture_lan_run_is_not_run(self) -> None:
        report = evaluate_lan_run(self.HOST, self.CLIENT, execution_mode="fixture")
        self.assertEqual("not_run", report["status"])

    def test_live_lan_run_converges(self) -> None:
        report = evaluate_lan_run(self.HOST, self.CLIENT, execution_mode="live")
        self.assertEqual("pass", report["status"])

    def test_live_lan_requires_both_logs(self) -> None:
        report = evaluate_lan_run(self.HOST, None, execution_mode="live")
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("host log and a client log" in reason for reason in report["failureReasons"]))

    def test_live_client_join_failure_fails_closed(self) -> None:
        client = MENU_LOG + "LogTemp: Warning: [Match] connection error [Match.JoinFailed]\n"
        report = evaluate_lan_run(self.HOST, client, execution_mode="live")
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("Match.JoinFailed" in reason for reason in report["failureReasons"]))

    def test_live_unexpected_disconnect_fails_but_expected_passes(self) -> None:
        client = self.CLIENT + "LogTemp: Warning: [Match] connection error [Match.Disconnected]\n"
        unexpected = evaluate_lan_run(self.HOST, client, execution_mode="live")
        self.assertEqual("fail", unexpected["status"])
        expected = evaluate_lan_run(self.HOST, client, execution_mode="live", expect_disconnect=True)
        self.assertEqual("pass", expected["status"])

    def test_live_runtime_crash_finding_fails_closed(self) -> None:
        host = self.HOST + "Fatal error: unhandled exception\n"
        report = evaluate_lan_run(host, self.CLIENT, execution_mode="live")
        self.assertEqual("fail", report["status"])
        self.assertTrue(any("Runtime.Crash" in reason for reason in report["failureReasons"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
