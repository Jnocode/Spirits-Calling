#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P8 generated action/property tests.

Feature: spirits-calling-requirements, Property 8: Platform interaction and
release-scope invariant
"""
from __future__ import annotations

import random
import unittest
from pathlib import Path

try:
    from Scripts.platform_action_router import (
        FORBIDDEN_SCOPE_TERMS,
        PC_ACTIONS,
        SHIPPED_MULTIPLAYER_SCOPE,
        SNAP_TURN_MIN_INTERVAL,
        ComfortTurnGate,
        PlatformAction,
        PlatformActionRouter,
        validate_runtime_seams,
        validate_scope,
    )
except ModuleNotFoundError:
    from platform_action_router import (
        FORBIDDEN_SCOPE_TERMS,
        PC_ACTIONS,
        SHIPPED_MULTIPLAYER_SCOPE,
        SNAP_TURN_MIN_INTERVAL,
        ComfortTurnGate,
        PlatformAction,
        PlatformActionRouter,
        validate_runtime_seams,
        validate_scope,
    )


ITERATIONS = 250
ROOT = Path(__file__).resolve().parents[1]


def _action(kind: str, timestamp: float, rng: random.Random, target: str = "") -> PlatformAction:
    value = 1.0 if kind == "snap_turn" else rng.uniform(-1.0, 1.0)
    return PlatformAction(kind=kind, timestamp=timestamp, value=value, target=target)


def _pc_sequence(rng: random.Random) -> list[PlatformAction]:
    now = 0.0
    def next_action(kind: str, target: str = "") -> PlatformAction:
        nonlocal now
        now += rng.uniform(0.001, 0.75)
        return _action(kind, now, rng, target)

    sequence = [
        next_action("movement"),
        next_action("summon_select"),
        next_action("summon_place"),
        next_action("possession"),
        next_action("light_attack"),
        next_action("heavy_attack"),
        next_action("menu_toggle"),
        next_action("movement"),  # must be ignored while menu is open
        next_action("summon_place"),  # must be ignored while menu is open
        next_action("menu_toggle"),
        next_action("restart"),
    ]
    # Generated noise is inserted without removing the required action set.
    for _ in range(rng.randrange(0, 5)):
        index = rng.randrange(len(sequence) + 1)
        sequence.insert(index, next_action(rng.choice(["movement", "summon_select"])))
    return sequence


def _vr_sequence(rng: random.Random) -> list[PlatformAction]:
    now = 0.0
    def next_action(kind: str, target: str = "") -> PlatformAction:
        nonlocal now
        now += rng.uniform(0.001, 0.75)
        return _action(kind, now, rng, target)

    target = rng.choice(("Play", "difficulty", "map", "civilization", "Host LAN", "Resume", "Quit"))
    sequence = [
        next_action("movement"),
        next_action("vertical"),
        next_action("snap_turn"),
        next_action("pointed_possession"),
        next_action("heavy_attack"),
        next_action("return_to_spirit"),
        next_action("summon_cycle"),
        next_action("pointed_summon"),
        next_action("menu_toggle"),
        next_action("vr_menu_hover", target),
        next_action("vr_menu_click", target),
        next_action("movement"),
        next_action("vertical"),
        next_action("pointed_summon"),
        next_action("snap_turn"),
        next_action("menu_toggle"),
        next_action("movement"),
    ]
    for _ in range(rng.randrange(0, 5)):
        index = rng.randrange(len(sequence) + 1)
        sequence.insert(index, next_action(rng.choice(["movement", "vertical", "summon_cycle"])))
    return sequence


class PlatformActionRouterUnitTests(unittest.TestCase):
    """Specific examples for menu routing, boundaries, and scope."""

    def test_snap_turn_exact_boundary_is_accepted_and_short_interval_rejected(self) -> None:
        gate = ComfortTurnGate()
        self.assertTrue(gate.try_accept(10.0))
        self.assertFalse(gate.try_accept(10.0 + SNAP_TURN_MIN_INTERVAL - 0.000001))
        self.assertTrue(gate.try_accept(10.0 + SNAP_TURN_MIN_INTERVAL))
        self.assertEqual(2, gate.accepted)
        self.assertEqual(1, gate.rejected)

    def test_vr_menu_routes_hover_click_and_locks_all_transform_inputs(self) -> None:
        router = PlatformActionRouter("PCVR_Mode")
        router.apply(PlatformAction("menu_toggle", 1.0))
        before = (router.state.position, router.state.yaw)
        self.assertTrue(router.apply(PlatformAction("vr_menu_hover", 1.1, target="Play")))
        self.assertTrue(router.apply(PlatformAction("vr_menu_click", 1.2, target="Play")))
        for kind, value in (("movement", 1.0), ("vertical", 1.0), ("pointed_summon", 0.0), ("snap_turn", 1.0)):
            self.assertFalse(router.apply(PlatformAction(kind, 1.3, value=value)))
        self.assertEqual(before, (router.state.position, router.state.yaw))
        self.assertEqual(["Play"], router.state.menu_hover_targets)
        self.assertEqual(["Play"], router.state.menu_click_targets)

    def test_scope_is_explicit_and_rejects_forbidden_shipped_claims(self) -> None:
        self.assertEqual([], validate_scope(SHIPPED_MULTIPLAYER_SCOPE))
        invalid = {
            "supported": ("PC single-player", "LAN", "public matchmaking", "dedicated servers"),
            "excluded": (),
        }
        errors = validate_scope(invalid)
        self.assertTrue(any("forbidden shipped capability" in error for error in errors))
        self.assertTrue(FORBIDDEN_SCOPE_TERMS)

    def test_runtime_seams_are_present_and_menu_gates_transform_handlers(self) -> None:
        spirit = (ROOT / "Source/SpiritsCalling/SpiritPawn.cpp").read_text(encoding="utf-8")
        vr = (ROOT / "Source/SpiritsCalling/SpiritVRPawn.cpp").read_text(encoding="utf-8")
        menu = (ROOT / "Source/SpiritsCalling/MainMenuWidget.cpp").read_text(encoding="utf-8")
        self.assertEqual([], validate_runtime_seams(spirit, vr, menu))


class PlatformActionRouterPropertyTests(unittest.TestCase):
    """Generated P8 properties; each property executes 250 iterations."""

    # **Validates: Requirements 2.2, 2.5, 2.6, 2.11**
    def test_property_p8_generated_pc_sequences_cover_documented_actions(self) -> None:
        for seed in range(ITERATIONS):
            rng = random.Random(seed)
            router = PlatformActionRouter("PC_Mode")
            sequence = _pc_sequence(rng)
            for action in sequence:
                router.apply(action)
            self.assertTrue(PC_ACTIONS.issubset(router.state.completed), f"seed={seed}")
            self.assertIn("movement", router.state.blocked_while_menu, f"seed={seed}")
            self.assertIn("summon_place", router.state.blocked_while_menu, f"seed={seed}")
            self.assertFalse(router.state.possessed, f"seed={seed}")

    # **Validates: Requirements 2.3, 2.5, 2.6**
    def test_property_p8_generated_vr_sequences_cover_actions_menu_lock_and_routing(self) -> None:
        required = {
            "movement", "vertical", "snap_turn", "pointed_possession", "pointed_summon",
            "summon_cycle", "return_to_spirit", "heavy_attack", "menu_toggle",
            "vr_menu_hover", "vr_menu_click",
        }
        for seed in range(ITERATIONS):
            rng = random.Random(10000 + seed)
            router = PlatformActionRouter("PCVR_Mode")
            sequence = _vr_sequence(rng)
            for action in sequence:
                router.apply(action)
            self.assertTrue(required.issubset(router.state.completed), f"seed={10000 + seed}")
            self.assertTrue(router.state.menu_hover_targets, f"seed={10000 + seed}")
            self.assertEqual(router.state.menu_hover_targets, router.state.menu_click_targets, f"seed={10000 + seed}")
            self.assertIn("movement", router.state.blocked_while_menu, f"seed={10000 + seed}")
            self.assertIn("vertical", router.state.blocked_while_menu, f"seed={10000 + seed}")
            self.assertIn("pointed_summon", router.state.blocked_while_menu, f"seed={10000 + seed}")
            self.assertIn("snap_turn", router.state.blocked_while_menu, f"seed={10000 + seed}")

    # **Validates: Requirements 2.6**
    def test_property_p8_generated_timestamps_enforce_snap_turn_gate(self) -> None:
        for seed in range(ITERATIONS):
            rng = random.Random(20000 + seed)
            base = rng.uniform(0.0, 1000.0)
            short_delta = rng.uniform(0.0, SNAP_TURN_MIN_INTERVAL - 1e-6)
            gate = ComfortTurnGate()
            self.assertTrue(gate.try_accept(base), f"seed={20000 + seed}")
            self.assertFalse(gate.try_accept(base + short_delta), f"seed={20000 + seed}")
            self.assertTrue(gate.try_accept(base + SNAP_TURN_MIN_INTERVAL), f"seed={20000 + seed}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
