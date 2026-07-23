#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replayable and live 30-minute stability telemetry runner.

The runner has two deliberately different modes:

* ``--command`` performs a real local process run and collects machine/process
  telemetry.  A query command is required; an absent query is not a pass.
* ``--fixture`` replays deterministic telemetry for boundary tests.  A fixture
  can prove that the evaluator understands a boundary, but it is always marked
  ``not_run`` for release readiness and can never fabricate hardware evidence.

The output is a stability evidence object.  ``readiness_record_writer.py`` can
embed that object in the canonical Release_Readiness_Record.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from typing import Any, Optional

DURATION_SECONDS = 30 * 60
QUERY_TIMEOUT_SECONDS = 5.0
MAX_HANG_SECONDS = 10.0
MEMORY_CHECK_SECONDS = 5 * 60
MAX_MEMORY_GROWTH = 0.20
VALID_STATUSES = {"pass", "fail", "not_run", "blocked"}


def _timestamp(value: Optional[dt.datetime] = None) -> str:
    moment = value or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _run_text(command: str, timeout: float = 2.0, env: Optional[dict[str, str]] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (result.stdout or "").strip()
    return value or None


def _machine_profile() -> dict[str, str]:
    """Collect real host values; never substitute guessed hardware labels."""
    os_name = platform.platform() or None
    cpu = platform.processor() or platform.uname().processor or None
    gpu: Optional[str] = None
    ram: Optional[str] = None

    if os.name == "nt":
        gpu = _run_text("powershell -NoProfile -Command \"(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)\"")
        if not cpu:
            cpu = _run_text("powershell -NoProfile -Command \"(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)\"")
        ram_bytes = _run_text("powershell -NoProfile -Command \"(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory\"")
        if ram_bytes and ram_bytes.isdigit():
            ram = f"{int(ram_bytes)} bytes"
    else:
        gpu = _run_text("lspci 2>/dev/null | grep -i -E 'vga|3d|display' | head -n 1")
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        ram = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass

    return {
        "os": os_name or "",
        "cpu": cpu or "",
        "gpu": gpu or "",
        "ram": ram or "",
    }


def _private_working_set_bytes(pid: int) -> Optional[int]:
    """Return private working set bytes from the OS, or None if unavailable."""
    if os.name == "nt":
        value = _run_text(
            f"powershell -NoProfile -Command \"(Get-Process -Id {pid} -ErrorAction Stop).PrivateMemorySize64\"",
            timeout=2.0,
        )
        if value and value.isdigit():
            return int(value)
        return None

    # Linux's VmRSS is not private working set.  Prefer psutil USS when the
    # environment already provides it; do not relabel an approximate metric.
    try:
        import psutil  # type: ignore
        return int(psutil.Process(pid).memory_full_info().uss)
    except (ImportError, OSError, AttributeError, ValueError):
        return None


def _query_value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    value = item.get(key, default)
    return value


def _valid_machine(machine: Any) -> bool:
    return isinstance(machine, dict) and all(_non_empty(machine.get(key)) for key in ("os", "cpu", "gpu", "ram"))


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assess_telemetry(data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate replayed/live measurements without trusting claimed summaries."""
    requested = _as_float(data.get("requestedDurationSeconds", DURATION_SECONDS))
    observed = _as_float(data.get("observedDurationSeconds", 0))
    mode = str(data.get("executionMode", "fixture")).strip().lower()
    machine = data.get("machine")
    queries = data.get("queries") if isinstance(data.get("queries"), list) else []
    memory = data.get("memory") if isinstance(data.get("memory"), dict) else {}
    reasons: list[str] = []

    if requested is None or requested < DURATION_SECONDS:
        reasons.append("requested duration is shorter than 1800 seconds")
    if observed is None or observed < DURATION_SECONDS:
        reasons.append("observed duration is shorter than 1800 seconds")
    if not queries:
        reasons.append("no input/state query observations were recorded")

    max_hang = 0.0
    for index, query in enumerate(queries):
        if not isinstance(query, dict):
            reasons.append(f"query {index} is not an object")
            continue
        latency = _as_float(query.get("latencySeconds"))
        if latency is None:
            reasons.append(f"query {index} has no measured latency")
        elif latency > QUERY_TIMEOUT_SECONDS:
            reasons.append(f"query {index} exceeded the 5 second response limit")
        if query.get("responded") is not True:
            reasons.append(f"query {index} did not respond")
        hang = _as_float(query.get("hangSeconds", 0)) or 0.0
        max_hang = max(max_hang, hang)
    if max_hang > MAX_HANG_SECONDS:
        reasons.append("a continuous hang exceeded 10 seconds")

    crash_detected = data.get("crashDetected") is True or data.get("processEndedEarly") is True
    if crash_detected:
        reasons.append("process crash or premature process exit detected")

    five_minute = memory.get("atFiveMinutes") if isinstance(memory.get("atFiveMinutes"), dict) else {}
    at_end = memory.get("atEnd") if isinstance(memory.get("atEnd"), dict) else {}
    baseline = _as_float(five_minute.get("privateWorkingSetBytes"))
    ending = _as_float(at_end.get("privateWorkingSetBytes"))
    growth: Optional[float] = None
    within_memory = False
    if baseline is None or ending is None or baseline <= 0:
        reasons.append("5 minute and ending private working set readings are incomplete")
    else:
        growth = (ending - baseline) / baseline
        within_memory = growth <= MAX_MEMORY_GROWTH
        if not within_memory:
            reasons.append("private working set growth exceeded 20 percent")

    if not _valid_machine(machine):
        reasons.append("OS, CPU, GPU and RAM machine profile is incomplete")

    measurement_status = "pass" if not reasons else "fail"
    # A fixture is useful for deterministic boundary tests, never release
    # evidence.  It may have a passing measurement but remains not_run.
    readiness_status = measurement_status if mode == "live" else ("not_run" if measurement_status == "pass" else "fail")
    return {
        "status": readiness_status,
        "measurementStatus": measurement_status,
        "readinessEligible": readiness_status == "pass" and mode == "live",
        "executionMode": mode,
        "evidenceSource": "live-process" if mode == "live" else "deterministic-fixture",
        "requestedDurationSeconds": requested if requested is not None else 0,
        "observedDurationSeconds": observed if observed is not None else 0,
        "queryTimeoutSeconds": QUERY_TIMEOUT_SECONDS,
        "maxAllowedHangSeconds": MAX_HANG_SECONDS,
        "startedAt": data.get("startedAt") or "",
        "endedAt": data.get("endedAt") or "",
        "crashDetected": crash_detected,
        "crashTimestamp": data.get("crashTimestamp"),
        "hangDetected": max_hang > 0,
        "maxConsecutiveHangSeconds": max_hang,
        "queries": queries,
        "memory": {
            "atFiveMinutes": five_minute,
            "atEnd": at_end,
            "growthRatio": growth,
            "maxGrowthRatio": MAX_MEMORY_GROWTH,
            "withinThreshold": within_memory,
        },
        "machine": machine if isinstance(machine, dict) else {"os": "", "cpu": "", "gpu": "", "ram": ""},
        "failureReasons": reasons or ["none"],
    }


def _live_telemetry(command: str, query_command: str, duration: float, interval: float, cwd: Optional[str]) -> dict[str, Any]:
    if not query_command.strip():
        raise ValueError("--query-command is required for live telemetry")
    if duration < DURATION_SECONDS:
        raise ValueError("live stability runs must request the full 1800 seconds")
    if interval <= 0:
        raise ValueError("--sample-interval must be positive")

    started_at = _timestamp()
    started = time.monotonic()
    machine = _machine_profile()
    process = subprocess.Popen(command, shell=True, cwd=cwd, env=os.environ.copy())
    queries: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    hang_started: Optional[float] = None
    crash_timestamp: Optional[str] = None
    process_ended_early = False
    end_memory: Optional[int] = None

    try:
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= duration:
                break
            query_started = time.monotonic()
            env = os.environ.copy()
            env["STABILITY_TARGET_PID"] = str(process.pid)
            try:
                result = subprocess.run(query_command, shell=True, capture_output=True, text=True, timeout=QUERY_TIMEOUT_SECONDS, env=env, cwd=cwd, check=False)
                responded = result.returncode == 0
            except subprocess.TimeoutExpired:
                responded = False
            query_elapsed = time.monotonic() - query_started
            if responded:
                hang_seconds = 0.0
                hang_started = None
            else:
                hang_started = hang_started if hang_started is not None else elapsed
                hang_seconds = max(0.0, elapsed - hang_started)
            queries.append({
                "timestamp": _timestamp(),
                "elapsedSeconds": round(elapsed, 3),
                "latencySeconds": round(query_elapsed, 3),
                "responded": responded,
                "hangSeconds": round(hang_seconds, 3),
            })
            return_code = process.poll()
            if return_code is not None:
                process_ended_early = elapsed + interval < duration
                if return_code != 0:
                    crash_timestamp = _timestamp()
                break
            samples.append({
                "timestamp": _timestamp(),
                "elapsedSeconds": round(elapsed, 3),
                "privateWorkingSetBytes": _private_working_set_bytes(process.pid),
                "alive": True,
            })
            time.sleep(min(interval, max(0.0, duration - (time.monotonic() - started))))
    finally:
        if process.poll() is None:
            # Capture the final private working set before terminating the
            # monitored process; after termination the OS no longer exposes it.
            end_memory = _private_working_set_bytes(process.pid)
        if process.poll() is None and time.monotonic() - started >= duration:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    observed = min(duration, time.monotonic() - started)
    five_minute_sample = next((item for item in samples if float(item.get("elapsedSeconds", 0)) >= MEMORY_CHECK_SECONDS), None)
    at_five = five_minute_sample or {}
    at_end = {"timestamp": _timestamp(), "privateWorkingSetBytes": end_memory}
    raw = {
        "executionMode": "live",
        "requestedDurationSeconds": duration,
        "observedDurationSeconds": observed,
        "startedAt": started_at,
        "endedAt": _timestamp(),
        "machine": machine,
        "queries": queries,
        "crashDetected": crash_timestamp is not None,
        "crashTimestamp": crash_timestamp,
        "processEndedEarly": process_ended_early,
        "memory": {"atFiveMinutes": at_five, "atEnd": at_end},
    }
    result = assess_telemetry(raw)
    result["samples"] = samples
    return result


def run_fixture(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        fixture = json.load(handle)
    if not isinstance(fixture, dict):
        raise ValueError("fixture must be a JSON object")
    return assess_telemetry({**fixture, "executionMode": "fixture"})


def write_json(result: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run or replay 30-minute stability telemetry")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--command", help="live package command to monitor")
    group.add_argument("--fixture", help="deterministic telemetry fixture JSON")
    parser.add_argument("--query-command", help="live input/state query command; PID is in STABILITY_TARGET_PID")
    parser.add_argument("--duration", type=float, default=DURATION_SECONDS)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--cwd")
    parser.add_argument("--output", required=True, help="telemetry evidence JSON output")
    args = parser.parse_args(argv)
    try:
        if args.fixture:
            result = run_fixture(args.fixture)
        else:
            result = _live_telemetry(args.command, args.query_command or "", args.duration, args.sample_interval, args.cwd)
        write_json(result, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": result.get("status"), "measurementStatus": result.get("measurementStatus"), "output": args.output}, ensure_ascii=False))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
