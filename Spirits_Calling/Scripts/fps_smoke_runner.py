#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate a 5-minute active-wave frame-rate window into fail-closed evidence.

This is an evidence evaluator, not a benchmark simulator. A fixture can validate
the interchange shape, but it is always downgraded to ``not_run`` and can never
produce a hardware frame-rate ``pass``. A live window only passes when it spans
at least five minutes of active-wave samples, averages at least 90 FPS, and
carries complete machine/build metadata.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Optional

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "fps_window"
MIN_WINDOW_SECONDS = 300.0
TARGET_AVERAGE_FPS = 90.0
MACHINE_FIELDS = ("os", "cpu", "gpu", "ram")
NOT_RECORDED = "not-recorded"


def _timestamp(now: Optional[dt.datetime] = None) -> str:
    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _machine(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {field: str(source.get(field) or NOT_RECORDED).strip() for field in MACHINE_FIELDS}


def _active_samples(raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            t = float(item.get("t", item.get("time")))
            fps = float(item.get("fps"))
        except (TypeError, ValueError):
            continue
        active = item.get("activeWave", item.get("active_wave", True))
        rows.append({"t": t, "fps": fps, "activeWave": bool(active)})
    rows.sort(key=lambda row: row["t"])
    return rows


def evaluate_fps_window(
    raw_samples: Any,
    *,
    execution_mode: str = "fixture",
    machine: Any = None,
    build_version: str = NOT_RECORDED,
    source_revision: str = NOT_RECORDED,
    now: Optional[dt.datetime] = None,
) -> dict[str, Any]:
    """Reduce raw frame samples to a fail-closed 5-minute active-wave verdict."""
    mode = str(execution_mode or "fixture").strip().lower()
    if mode not in {"live", "fixture"}:
        mode = "fixture"

    samples = _active_samples(raw_samples)
    active = [row for row in samples if row["activeWave"]]
    window_seconds = (active[-1]["t"] - active[0]["t"]) if len(active) >= 2 else 0.0
    average_fps = round(sum(row["fps"] for row in active) / len(active), 3) if active else 0.0
    machine_profile = _machine(machine)
    build = str(build_version or NOT_RECORDED).strip() or NOT_RECORDED
    revision = str(source_revision or NOT_RECORDED).strip() or NOT_RECORDED

    reasons: list[str] = []
    status = "pass"

    if mode != "live":
        status = "not_run"
        reasons.append("fixture frame samples cannot prove hardware frame rate")
    else:
        if len(active) < 2:
            reasons.append("fewer than two active-wave frame samples were recorded")
        if window_seconds + 1e-6 < MIN_WINDOW_SECONDS:
            reasons.append(f"active-wave window {window_seconds:.1f}s is under the required {MIN_WINDOW_SECONDS:.0f}s")
        if average_fps + 1e-6 < TARGET_AVERAGE_FPS:
            reasons.append(f"average {average_fps:.1f} FPS is under the required {TARGET_AVERAGE_FPS:.0f} FPS")
        if any(not value or value == NOT_RECORDED for value in machine_profile.values()):
            reasons.append("OS/CPU/GPU/RAM machine profile is incomplete")
        if build == NOT_RECORDED or revision == NOT_RECORDED:
            reasons.append("build version and source revision metadata are incomplete")
        status = "fail" if reasons else "pass"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "reportType": REPORT_TYPE,
        "executionMode": mode,
        "status": status,
        "readinessEligible": status == "pass",
        "timestamp": _timestamp(now),
        "windowSeconds": round(window_seconds, 3),
        "requiredWindowSeconds": MIN_WINDOW_SECONDS,
        "averageFps": average_fps,
        "targetAverageFps": TARGET_AVERAGE_FPS,
        "sampleCount": len(samples),
        "activeSampleCount": len(active),
        "buildVersion": build,
        "sourceRevision": revision,
        "machine": machine_profile,
        "failureReasons": reasons,
    }


def evaluate_fps_file(input_path: str, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    with open(input_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    source = payload if isinstance(payload, dict) else {}
    return evaluate_fps_window(
        source.get("samples", payload if isinstance(payload, list) else []),
        execution_mode=str(source.get("executionMode", source.get("execution_mode", "fixture"))),
        machine=source.get("machine"),
        build_version=str(source.get("buildVersion", source.get("build_version", NOT_RECORDED))),
        source_revision=str(source.get("sourceRevision", source.get("source_revision", NOT_RECORDED))),
        now=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="frame-sample JSON: {samples:[{t,fps,activeWave}], machine, ...}")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_fps_file(args.input)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "avgFps": report["averageFps"], "windowSeconds": report["windowSeconds"]}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
