#!/usr/bin/env python3
"""Pure replicated-match oracle used by Property 7.

This model intentionally does not open sockets, create Unreal actors, or infer
hardware/network success.  The host is authoritative; clients receive delayed
and reordered snapshots and apply them monotonically by revision.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

WAITING_TO_START = "WaitingToStart"
IN_PROGRESS = "InProgress"
ENDED = "Ended"
NO_TEAM = -1


@dataclass(frozen=True)
class MatchSnapshot:
    revision: int = 0
    phase: str = WAITING_TO_START
    winner: int = NO_TEAM
    difficulty: int = 1
    map_index: int = 0
    team_by_client: tuple[tuple[str, int], ...] = ()
    civilization_by_team: tuple[tuple[int, int], ...] = ()
    loadout_by_team: tuple[tuple[int, tuple[int, ...]], ...] = ()
    summoned_units: tuple[tuple[str, str, int], ...] = ()
    possessions: tuple[tuple[str, str], ...] = ()
    combat_events: tuple[tuple[str, str, int], ...] = ()
    movement_revisions: tuple[tuple[str, int], ...] = ()
    menu_revision: int = 0


@dataclass
class _ClientReplica:
    snapshot: MatchSnapshot = field(default_factory=MatchSnapshot)
    pending: list[MatchSnapshot] = field(default_factory=list)
    connected: bool = True


class ReplicatedMatchModel:
    """Authoritative host plus monotonic client snapshot replicas."""

    def __init__(self, host_id: str = "host") -> None:
        self.host_id = host_id
        self.host_snapshot = MatchSnapshot()
        self._clients: dict[str, _ClientReplica] = {
            host_id: _ClientReplica(snapshot=self.host_snapshot)
        }
        self.events: list[dict[str, Any]] = []
        self._unit_counter = 0

    @staticmethod
    def normalize_map_index(value: int) -> int:
        return max(0, min(1, int(value)))

    @property
    def connected_clients(self) -> tuple[str, ...]:
        return tuple(sorted(self._clients))

    @property
    def host_operable(self) -> bool:
        return self.host_id in self._clients and self._clients[self.host_id].connected

    def join(self, client_id: str, *, succeed: bool = True) -> bool:
        if not succeed or not client_id or client_id in self._clients:
            self.events.append({"code": "Match.JoinFailed", "client": client_id})
            return False
        self._clients[client_id] = _ClientReplica(snapshot=self.host_snapshot)
        return True

    def disconnect(self, client_id: str) -> bool:
        if client_id not in self._clients:
            return False
        if client_id == self.host_id:
            return False
        del self._clients[client_id]
        self.events.append({"code": "Match.Disconnected", "client": client_id})
        return True

    def configure_match(
        self,
        *,
        difficulty: int,
        map_index: int,
        team_by_client: Iterable[tuple[str, int]],
        civilization_by_team: Iterable[tuple[int, int]],
        loadout_by_team: Iterable[tuple[int, Iterable[int]]],
    ) -> None:
        self._commit(
            phase=IN_PROGRESS,
            difficulty=max(0, min(2, int(difficulty))),
            map_index=self.normalize_map_index(map_index),
            team_by_client=tuple(sorted((str(client), int(team)) for client, team in team_by_client)),
            civilization_by_team=tuple(sorted((int(team), int(civ)) for team, civ in civilization_by_team)),
            loadout_by_team=tuple(sorted((int(team), tuple(int(item) for item in loadout)) for team, loadout in loadout_by_team)),
        )

    def request(self, client_id: str, kind: str, **payload: Any) -> bool:
        """Process one client request on the authoritative host."""
        if client_id not in self._clients or not self._clients[client_id].connected:
            return False
        if self.host_snapshot.phase == ENDED and kind not in {"menu"}:
            return False
        if kind == "summon":
            self._unit_counter += 1
            unit_id = str(payload.get("unit_id") or f"unit-{self._unit_counter}")
            team = int(payload.get("team", self._team_for(client_id)))
            archetype = int(payload.get("archetype", 0))
            summons = self.host_snapshot.summoned_units + ((unit_id, client_id, team * 10 + archetype),)
            self._commit(summoned_units=summons)
        elif kind == "possession":
            unit_id = str(payload["unit_id"])
            if not any(item[0] == unit_id for item in self.host_snapshot.summoned_units):
                return False
            possessions = tuple(item for item in self.host_snapshot.possessions if item[0] != client_id)
            self._commit(possessions=possessions + ((client_id, unit_id),))
        elif kind == "combat":
            unit_id = str(payload.get("unit_id", "unknown"))
            damage = int(payload.get("damage", 1))
            events = self.host_snapshot.combat_events + ((client_id, unit_id, damage),)
            self._commit(combat_events=events)
        elif kind == "movement":
            revisions = dict(self.host_snapshot.movement_revisions)
            revisions[client_id] = revisions.get(client_id, 0) + 1
            self._commit(movement_revisions=tuple(sorted(revisions.items())))
        elif kind == "menu":
            self._commit(menu_revision=self.host_snapshot.menu_revision + 1)
        elif kind == "winner":
            self._commit(phase=ENDED, winner=int(payload.get("team", NO_TEAM)))
        else:
            return False
        return True

    def _team_for(self, client_id: str) -> int:
        return dict(self.host_snapshot.team_by_client).get(client_id, NO_TEAM)

    def _commit(self, **changes: Any) -> None:
        self.host_snapshot = replace(self.host_snapshot, revision=self.host_snapshot.revision + 1, **changes)
        for replica in self._clients.values():
            replica.pending.append(self.host_snapshot)

    def deliver(self, client_id: str, order: Iterable[int] | None = None) -> None:
        replica = self._clients[client_id]
        if order is None:
            order = range(len(replica.pending))
        pending = list(replica.pending)
        for index in order:
            if 0 <= index < len(pending):
                candidate = pending[index]
                if candidate.revision > replica.snapshot.revision:
                    replica.snapshot = candidate
        replica.pending.clear()

    def drain(self, delivery_order: dict[str, Iterable[int]] | None = None) -> None:
        for client_id in self.connected_clients:
            order = delivery_order.get(client_id) if delivery_order else None
            self.deliver(client_id, order)

    def snapshot_for(self, client_id: str) -> MatchSnapshot:
        return self._clients[client_id].snapshot

    def pending_count(self, client_id: str) -> int:
        return len(self._clients[client_id].pending)
