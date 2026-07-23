#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure PC/PCVR action contract used by Property P8.

This module intentionally models input projection only. It does not create a
world, actors, HMD, Steam session, LAN connection, or hardware pass record.
The Unreal pawns remain the runtime implementation; this adapter supplies a
small immutable-ish oracle for generated action sequences and boundary tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

SNAP_TURN_MIN_INTERVAL = 0.35
SNAP_TURN_DEADZONE = 0.6

PC_ACTIONS = frozenset({
    "movement",
    "summon_select",
    "summon_place",
    "possession",
    "light_attack",
    "heavy_attack",
    "menu_toggle",
    "restart",
})
VR_ACTIONS = frozenset({
    "movement",
    "vertical",
    "snap_turn",
    "pointed_possession",
    "pointed_summon",
    "summon_cycle",
    "return_to_spirit",
    "heavy_attack",
    "menu_toggle",
    "vr_menu_hover",
    "vr_menu_click",
})
FORBIDDEN_SCOPE_TERMS = frozenset({
    "public matchmaking",
    "dedicated server",
    "dedicated servers",
    "nakama",
    "anti-cheat",
    "anti cheat",
})
SUPPORTED_SCOPE_TERMS = frozenset({
    "pc single-player",
    "pcvr",
    "lan",
    "friend connection",
})

# This is the only scope this adapter will accept as shipped capability. It is
# deliberately a declaration, not evidence that a network or hardware run passed.
SHIPPED_MULTIPLAYER_SCOPE = {
    "supported": ("PC single-player", "LAN", "friend connection", "PCVR"),
    "excluded": (
        "public matchmaking",
        "dedicated servers",
        "Nakama authentication",
        "anti-cheat",
    ),
}


@dataclass(frozen=True)
class PlatformAction:
    kind: str
    timestamp: float
    value: float = 0.0
    target: str = ""


@dataclass
class ComfortTurnGate:
    """Monotonic timestamp gate; exact 0.35s is accepted."""

    minimum_interval: float = SNAP_TURN_MIN_INTERVAL
    last_accepted: Optional[float] = None
    accepted: int = 0
    rejected: int = 0

    def try_accept(self, timestamp: float) -> bool:
        # Timestamps commonly arrive from binary floating-point arithmetic;
        # tolerate representation noise at the exact 0.35s contract boundary.
        epsilon = 1e-9
        if self.last_accepted is not None and timestamp - self.last_accepted + epsilon < self.minimum_interval:
            self.rejected += 1
            return False
        self.last_accepted = timestamp
        self.accepted += 1
        return True


@dataclass
class RouterState:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    yaw: float = 0.0
    menu_open: bool = False
    possessed: bool = False
    selected_archetype: int = 0
    completed: set[str] = field(default_factory=set)
    blocked_while_menu: list[str] = field(default_factory=list)
    menu_hover_targets: list[str] = field(default_factory=list)
    menu_click_targets: list[str] = field(default_factory=list)
    snap_turn_accepted: int = 0
    snap_turn_rejected: int = 0


class PlatformActionRouter:
    """Deterministic action oracle for PC and PCVR contract tests."""

    def __init__(self, mode: str) -> None:
        if mode not in {"PC_Mode", "PCVR_Mode"}:
            raise ValueError(f"unsupported mode: {mode}")
        self.mode = mode
        self.state = RouterState()
        self.turn_gate = ComfortTurnGate()

    @property
    def supported_actions(self) -> frozenset[str]:
        return PC_ACTIONS if self.mode == "PC_Mode" else VR_ACTIONS

    def _blocked(self, action: PlatformAction) -> bool:
        if self.state.menu_open and action.kind in {
            "movement", "vertical", "pointed_summon", "summon_place", "snap_turn"
        }:
            self.state.blocked_while_menu.append(action.kind)
            return True
        return False

    def _move(self, action: PlatformAction) -> None:
        if self.mode == "PC_Mode":
            self.state.position = (
                self.state.position[0] + action.value,
                self.state.position[1] + (1.0 if action.value >= 0 else -1.0),
                self.state.position[2],
            )
        else:
            self.state.position = (
                self.state.position[0] + action.value,
                self.state.position[1] + 0.5,
                self.state.position[2],
            )
        self.state.completed.add("movement")

    def apply(self, action: PlatformAction) -> bool:
        """Apply one action and return whether gameplay state accepted it."""
        if action.kind not in self.supported_actions:
            return False
        if action.kind == "menu_toggle":
            self.state.menu_open = not self.state.menu_open
            self.state.completed.add("menu_toggle")
            return True
        if self._blocked(action):
            return False
        if action.kind == "movement":
            self._move(action)
        elif action.kind == "vertical":
            self.state.position = (
                self.state.position[0], self.state.position[1], self.state.position[2] + action.value
            )
            self.state.completed.add("vertical")
        elif action.kind == "snap_turn":
            if abs(action.value) < SNAP_TURN_DEADZONE or not self.turn_gate.try_accept(action.timestamp):
                self.state.snap_turn_rejected += 1
                return False
            self.state.yaw += 45.0 if action.value > 0 else -45.0
            self.state.snap_turn_accepted += 1
            self.state.completed.add("snap_turn")
        elif action.kind in {"summon_select", "summon_cycle"}:
            self.state.selected_archetype = int(action.value) % 3
            self.state.completed.add(action.kind)
        elif action.kind in {"summon_place", "pointed_summon"}:
            self.state.completed.add(action.kind)
        elif action.kind in {"possession", "pointed_possession"}:
            self.state.possessed = True
            self.state.completed.add(action.kind)
        elif action.kind == "return_to_spirit":
            self.state.possessed = False
            self.state.completed.add(action.kind)
        elif action.kind in {"light_attack", "heavy_attack"}:
            if not self.state.possessed:
                return False
            self.state.completed.add(action.kind)
        elif action.kind == "restart":
            self.state.position = (0.0, 0.0, 0.0)
            self.state.yaw = 0.0
            self.state.possessed = False
            self.state.completed.add(action.kind)
        elif action.kind == "vr_menu_hover":
            if not self.state.menu_open:
                return False
            self.state.menu_hover_targets.append(action.target)
            self.state.completed.add(action.kind)
        elif action.kind == "vr_menu_click":
            if not self.state.menu_open:
                return False
            self.state.menu_click_targets.append(action.target)
            self.state.completed.add(action.kind)
        return True


def run_sequence(mode: str, actions: Iterable[PlatformAction]) -> PlatformActionRouter:
    router = PlatformActionRouter(mode)
    for action in actions:
        router.apply(action)
    return router


def validate_scope(declaration: Mapping[str, Any]) -> list[str]:
    """Return stable validation errors; forbidden terms cannot be shipped claims."""
    supported = {str(value).strip().lower() for value in declaration.get("supported", ())}
    excluded = {str(value).strip().lower() for value in declaration.get("excluded", ())}
    normalized_excluded = {value.replace("-", " ") for value in excluded}
    errors: list[str] = []
    if not {"lan", "friend connection"}.issubset(supported):
        errors.append("scope must include LAN and friend connection")
    if "pc single-player" not in supported or "pcvr" not in supported:
        errors.append("scope must include PC single-player and PCVR")
    for term in FORBIDDEN_SCOPE_TERMS:
        if any(term in value for value in supported):
            errors.append(f"forbidden shipped capability: {term}")
    for term in FORBIDDEN_SCOPE_TERMS:
        normalized_term = term.replace("-", " ")
        if not any(normalized_term in value for value in normalized_excluded):
            errors.append(f"scope must explicitly exclude: {term}")
    return errors


def validate_runtime_seams(spirit_pawn_source: str, vr_pawn_source: str, menu_source: str) -> list[str]:
    """Static seam checks complement the pure model without claiming hardware pass."""
    errors: list[str] = []
    if "PC->RequestPossessMinion" not in spirit_pawn_source or "PC->RequestSummon" not in spirit_pawn_source:
        errors.append("PC pawn must route possession and summon through controller requests")
    required_gate = {
        "OnMoveInput": "EPlatformAction::Movement",
        "OnVerticalInput": "EPlatformAction::Movement",
        "OnSummonInput": "EPlatformAction::Summon",
        "OnSnapTurnInput": "EPlatformAction::SnapTurn",
    }
    for method, action in required_gate.items():
        start = vr_pawn_source.find(f"void ASpiritVRPawn::{method}")
        end = vr_pawn_source.find("\nvoid ASpiritVRPawn::", start + 1)
        body = vr_pawn_source[start:] if start >= 0 and end < 0 else vr_pawn_source[start:end]
        has_legacy_gate = "bMenuOpen" in body
        has_shared_gate = "CanDispatchPlatformAction" in body and action in body
        if start < 0 or not (has_legacy_gate or has_shared_gate):
            errors.append(f"VR {method} must gate gameplay transform input while menu is open")
    if "WidgetInteraction->PressPointerKey" not in vr_pawn_source or "WidgetInteraction->ReleasePointerKey" not in vr_pawn_source:
        errors.append("VR menu pointer press/release routing is missing")
    if "ClientTravel" not in menu_source or "listen" not in menu_source:
        errors.append("menu must expose direct LAN host/join seams")
    return errors
