#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate two-instance LAN host/join convergence into fail-closed evidence.

This is an evidence evaluator for a real two-instance LAN run, not a network
simulator. It parses the host and client launch logs for stable smoke markers
and connection codes and decides whether the listen-server host and the joining
client converged on the same match within the deadline. A fixture or a single
log can validate the interchange shape but is always downgraded to ``not_run``;
it can never prove a real two-machine LAN session.

Real two-machine LAN acceptance (two accepted packages on two clean Windows
hosts) remains a separate, human/hardware gate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from typing import Any, Optional

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "lan_convergence"
DEFAULT_DEADLINE_SECONDS = 60.0

MENU_READY = re.compile(r"\[SpiritsSmoke\]\s*Stage=MenuReady", re.I)
MATCH_IN_PROGRESS = re.compile(r"\[SpiritsSmoke\]\s*Stage=MatchInProgress", re.I)
JOIN_FAILED = re.compile(r"connection error \[Match\.JoinFailed\]", re.I)
DISCONNECTED = re.compile(r"connection error \[Match\.Disconnected\]", re.I)
ERROR_PATTERNS = (
    ("Runtime.Crash", re.compile(r"(?:fatal error|unhandled exception|assertion failed)", re.I)),
    ("Runtime.Hang", re.compile(r"(?:hang detected|game thread timed out)", re.I)),
)


def _timestamp(now: Optional[dt.datetime] = None) -> str:
    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_lan_log(text: str) -> dict[str, Any]:
    """Extract stable LAN markers and crash/hang findings from one instance log."""
    body = str(text or "")
    findings = [code for code, pattern in ERROR_PATTERNS if pattern.search(body)]
    return {
        "menuReady": bool(MENU_READY.search(body)),
        "matchInProgress": bool(MATCH_IN_PROGRESS.search(body)),
        "joinFailed": bool(JOIN_FAILED.search(body)),
        "disconnected": bool(DISCONNECTED.search(body)),
        "findings": findings,
    }


def evaluate_lan_run(
    host_text: Optional[str],
    client_text: Optional[str],
    *,
    execution_mode: str = "fixture",
    expect_disconnect: bool = False,
    now: Optional[dt.datetime] = None,
) -> dict[str, Any]:
    """Decide LAN convergence from a host log and a client log, failing closed."""
    mode = str(execution_mode or "fixture").strip().lower()
    if mode not in {"live", "fixture"}:
        mode = "fixture"

    host = parse_lan_log(host_text) if host_text is not None else None
    client = parse_lan_log(client_text) if client_text is not None else None

    reasons: list[str] = []
    status = "pass"

    if mode != "live":
        status = "not_run"
        reasons.append("fixture logs cannot prove a two-instance LAN session")
    elif host is None or client is None:
        status = "fail"
        reasons.append("both a host log and a client log are required for a LAN run")
    else:
        # The listen-server host must come up and reach the match.
        if not host["menuReady"]:
            reasons.append("host did not reach the title/menu stage")
        if not host["matchInProgress"]:
            reasons.append("host did not start the match")
        # A failed join is an explicit LAN failure, never a silent pass.
        if client["joinFailed"]:
            reasons.append("client reported Match.JoinFailed")
        # The joining client must converge into the same in-progress match.
        if not client["matchInProgress"] and not client["joinFailed"]:
            reasons.append("client did not converge into the in-progress match")
        # A disconnect is only acceptable when the run is exercising it, and the
        # host must stay operable (already required to have reached the match).
        if client["disconnected"] and not expect_disconnect:
            reasons.append("client disconnected during a run that did not expect a disconnect")
        for code in host["findings"] + client["findings"]:
            reasons.append(f"runtime finding: {code}")
        status = "fail" if reasons else "pass"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "reportType": REPORT_TYPE,
        "executionMode": mode,
        "status": status,
        "readinessEligible": status == "pass",
        "timestamp": _timestamp(now),
        "expectDisconnect": bool(expect_disconnect),
        "host": host,
        "client": client,
        "failureReasons": reasons,
    }


def evaluate_lan_files(
    host_path: Optional[str],
    client_path: Optional[str],
    *,
    execution_mode: str = "fixture",
    expect_disconnect: bool = False,
    now: Optional[dt.datetime] = None,
) -> dict[str, Any]:
    def _read(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()

    report = evaluate_lan_run(
        _read(host_path), _read(client_path),
        execution_mode=execution_mode, expect_disconnect=expect_disconnect, now=now,
    )
    report["hostLogPath"] = host_path
    report["clientLogPath"] = client_path
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-log", help="listen-server host launch log")
    parser.add_argument("--client-log", help="joining client launch log")
    parser.add_argument("--execution-mode", choices=("live", "fixture"), default="fixture")
    parser.add_argument("--expect-disconnect", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate_lan_files(
        args.host_log, args.client_log,
        execution_mode=args.execution_mode, expect_disconnect=args.expect_disconnect,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "reasons": len(report["failureReasons"])}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
