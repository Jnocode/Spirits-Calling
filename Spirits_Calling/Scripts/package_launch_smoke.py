#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch a packaged Win64 executable and emit fail-closed JSON evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "package_launch"
ERROR_PATTERNS = (
    ("Package.MissingMap", re.compile(r"(?:failed to load map|loadmapfailure|map .+ not found|can't find file[^\n]*\.umap)", re.I)),
    ("Package.MissingClass", re.compile(r"(?:can't find class|failed to (?:find|load)[^\n]*class|createexport[^\n]*class)", re.I)),
    ("Package.MissingAsset", re.compile(r"(?:can't find file|failed to (?:find object|load)[^\n]*(?:/Game/|asset))", re.I)),
    ("Runtime.Crash", re.compile(r"(?:fatal error|unhandled exception|critical error|assertion failed|crash detected)", re.I)),
    ("Runtime.Hang", re.compile(r"(?:hang detected|game thread timed out|heartbeat timeout|not responding)", re.I)),
)
MAP_READY_PATTERNS = (
    re.compile(r"Bringing World[^\n]*/Game/Maps/DemoMap(?:\b|\.)", re.I),
    re.compile(r"LoadMap[^\n]*/Game/Maps/DemoMap(?:\b|\.)", re.I),
)
DEFAULT_READY_PATTERNS = MAP_READY_PATTERNS
REJECTED_EXE_TOKENS = ("unrealeditor", "server", "-cmd")

# Ordered launch stages the runtime emits as stable, greppable markers. The
# title/menu stage also accepts the DemoMap "bringing world" line so an older
# build without the marker still satisfies the clean-launch stage. Reaching a
# stage records a runtime milestone only; it is never a release Pass by itself.
SMOKE_STAGES = (
    (
        "title_menu",
        (
            re.compile(r"\[SpiritsSmoke\]\s*Stage=MenuReady", re.I),
            *MAP_READY_PATTERNS,
        ),
    ),
    (
        "pc_in_progress",
        (re.compile(r"\[SpiritsSmoke\]\s*Stage=MatchInProgress", re.I),),
    ),
)
VALID_STAGE_NAMES = tuple(name for name, _ in SMOKE_STAGES)


def parse_stage_progress(text: str) -> list[str]:
    """Return the ordered smoke stages whose markers appear in the log text."""
    reached: list[str] = []
    for name, patterns in SMOKE_STAGES:
        if any(pattern.search(text or "") for pattern in patterns):
            reached.append(name)
    return reached


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_runtime_log(
    text: str,
    ready_patterns: Optional[Iterable[str]] = None,
    required_stages: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Parse launch readiness, stage progress, and missing/crash/hang findings.

    ``required_stages`` (a subset of :data:`VALID_STAGE_NAMES`) tightens readiness
    so every requested launch stage must be observed. When it is omitted the
    original DemoMap-ready behaviour is preserved for backward compatibility.
    """
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for line_number, line in enumerate(str(text or "").splitlines(), start=1):
        for code, pattern in ERROR_PATTERNS:
            if pattern.search(line):
                key = (code, line_number)
                if key not in seen:
                    seen.add(key)
                    findings.append({"code": code, "line": line_number, "message": line.strip()[:1000]})
                break
    map_ready = any(pattern.search(text or "") for pattern in MAP_READY_PATTERNS)
    if ready_patterns:
        patterns = [re.compile(item, re.I) for item in ready_patterns]
        ready = map_ready and any(pattern.search(text or "") for pattern in patterns)
    else:
        ready = map_ready

    stages = parse_stage_progress(text)
    if required_stages:
        wanted = [name for name in required_stages if name in VALID_STAGE_NAMES]
        ready = ready and all(name in stages for name in wanted)
    return {
        "ready": ready,
        "crashDetected": any(item["code"] == "Runtime.Crash" for item in findings),
        "hangDetected": any(item["code"] == "Runtime.Hang" for item in findings),
        "stages": stages,
        "findings": findings,
    }


def _packaged_root(executable: Path, supplied: Optional[Path]) -> Optional[Path]:
    candidates = [supplied.resolve()] if supplied else []
    candidates.extend([executable.parent, *executable.parents])
    for candidate in candidates:
        if candidate.is_dir() and ((candidate / "Content" / "Paks").is_dir() or any(candidate.glob("*/Content/Paks"))):
            return candidate
    return None


def _base_report(executable: Path, log_path: Path, execution_mode: str, timeout_seconds: float, hang_timeout_seconds: float) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "reportType": REPORT_TYPE,
        "executionMode": execution_mode,
        "status": "not_run",
        "readinessEligible": False,
        "executablePath": str(executable),
        "packagePath": None,
        "logPath": str(log_path),
        "startedAt": None,
        "endedAt": None,
        "durationSeconds": 0.0,
        "timeoutSeconds": timeout_seconds,
        "hangTimeoutSeconds": hang_timeout_seconds,
        "process": {"started": False, "pid": None, "exitCode": None, "terminatedByRunner": False},
        "signals": {"ready": False, "crashDetected": False, "hangDetected": False},
        "requiredStages": [],
        "stagesReached": [],
        "findings": [],
        "evidencePaths": [],
        "machine": {"os": platform.platform(), "cpu": platform.processor() or "not-recorded"},
    }


def _finish(report: dict[str, Any], status: str, code: str, message: str, started: Optional[float] = None) -> dict[str, Any]:
    report["status"] = status
    report["endedAt"] = _timestamp()
    report["durationSeconds"] = round(max(0.0, time.monotonic() - started), 3) if started is not None else 0.0
    if code:
        report["findings"].append({"code": code, "message": message})
    return report


def _stop_process(process: subprocess.Popen[Any], report: dict[str, Any]) -> None:
    if process.poll() is not None:
        report["process"]["exitCode"] = process.returncode
        return
    report["process"]["terminatedByRunner"] = True
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    report["process"]["exitCode"] = process.returncode


def run_package_smoke(
    executable: Path | str,
    *,
    log_path: Path | str,
    package_root: Path | str | None = None,
    timeout_seconds: float = 120.0,
    hang_timeout_seconds: float = 30.0,
    execution_mode: str = "live",
    dry_run: bool = False,
    extra_args: Optional[list[str]] = None,
    ready_patterns: Optional[list[str]] = None,
    required_stages: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Run only a real packaged executable; fixture/dry-run can never pass."""
    exe = Path(executable).expanduser().resolve()
    log = Path(log_path).expanduser().resolve()
    mode = execution_mode if execution_mode in {"live", "fixture"} else "fixture"
    report = _base_report(exe, log, mode, timeout_seconds, hang_timeout_seconds)
    stages = [name for name in (required_stages or []) if name in VALID_STAGE_NAMES]
    report["requiredStages"] = stages
    if required_stages and any(name not in VALID_STAGE_NAMES for name in required_stages):
        unknown = [name for name in required_stages if name not in VALID_STAGE_NAMES]
        return _finish(report, "blocked", "Launch.InvalidStage", f"unknown launch stages: {unknown}")
    if dry_run or mode != "live":
        reason = "dry-run does not launch or prove a package" if dry_run else "fixture execution cannot prove package launch"
        return _finish(report, "not_run", "Launch.NotRun", reason)
    if ready_patterns:
        try:
            for pattern in ready_patterns:
                re.compile(pattern, re.I)
        except re.error as exc:
            return _finish(report, "blocked", "Launch.InvalidReadyPattern", str(exc))
    if not exe.is_file():
        return _finish(report, "blocked", "Launch.ExecutableMissing", "packaged executable does not exist")
    if exe.suffix.casefold() != ".exe" or any(token in exe.name.casefold() for token in REJECTED_EXE_TOKENS):
        return _finish(report, "blocked", "Launch.NotPackagedClient", "executable must be a packaged Win64 client, not Editor/server/cmd")
    root = _packaged_root(exe, Path(package_root) if package_root else None)
    if root is None:
        return _finish(report, "blocked", "Launch.PackageLayoutMissing", "no packaged Content/Paks layout is locatable")
    if timeout_seconds <= 0 or hang_timeout_seconds <= 0:
        return _finish(report, "blocked", "Launch.InvalidTimeout", "timeouts must be positive")

    report["packagePath"] = str(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report["startedAt"] = _timestamp()
    command = [str(exe), "-stdout", "-FullStdOutLogOutput", "-unattended", *list(extra_args or [])]
    try:
        with log.open("w", encoding="utf-8", errors="replace") as stream:
            process = subprocess.Popen(command, cwd=str(root), stdout=stream, stderr=subprocess.STDOUT)
        report["process"].update({"started": True, "pid": process.pid})
    except OSError as exc:
        return _finish(report, "blocked", "Launch.ProcessStartFailed", str(exc), started)

    last_size = -1
    last_progress = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            size = len(text)
            if size != last_size:
                last_size = size
                last_progress = now
            parsed = parse_runtime_log(text, ready_patterns, stages)
            report["signals"] = {key: parsed[key] for key in ("ready", "crashDetected", "hangDetected")}
            report["stagesReached"] = parsed["stages"]
            report["findings"] = parsed["findings"]
            if parsed["findings"]:
                _stop_process(process, report)
                return _finish(report, "fail", "", "", started)
            exit_code = process.poll()
            if exit_code is not None:
                report["process"]["exitCode"] = exit_code
                return _finish(report, "fail", "Launch.ProcessExited", f"process exited before readiness with code {exit_code}", started)
            if parsed["ready"]:
                _stop_process(process, report)
                report["readinessEligible"] = True
                report["evidencePaths"] = [str(exe), str(root), str(log)]
                return _finish(report, "pass", "", "", started)
            if now - last_progress >= hang_timeout_seconds:
                report["signals"]["hangDetected"] = True
                _stop_process(process, report)
                return _finish(report, "fail", "Runtime.Hang", "no launch-log progress before readiness within hang timeout", started)
            if now - started >= timeout_seconds:
                _stop_process(process, report)
                return _finish(report, "fail", "Launch.Timeout", "readiness marker was not observed before timeout", started)
            time.sleep(0.2)
    finally:
        if process.poll() is None:
            _stop_process(process, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--hang-timeout", type=float, default=30.0)
    parser.add_argument("--execution-mode", choices=("live", "fixture"), default="live")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arg", action="append", default=[])
    parser.add_argument("--ready-pattern", action="append")
    parser.add_argument("--require-stage", action="append", choices=VALID_STAGE_NAMES,
                        help="require a named launch stage marker (repeatable): title_menu, pc_in_progress")
    args = parser.parse_args()
    report = run_package_smoke(
        args.exe, log_path=args.log, package_root=args.package_root,
        timeout_seconds=args.timeout, hang_timeout_seconds=args.hang_timeout,
        execution_mode=args.execution_mode, dry_run=args.dry_run,
        extra_args=args.arg, ready_patterns=args.ready_pattern,
        required_stages=args.require_stage,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output), "findings": len(report["findings"])}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
