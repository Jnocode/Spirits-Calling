#!/usr/bin/env python3
"""Generated convergence tests for the LAN replicated-match contract.

Feature: spirits-calling-requirements, Property 7:
The host is authoritative, snapshots converge after delayed/reordered delivery,
failed joins do not change connection state, and a remaining client stays live
through disconnect and Ended.
"""
from __future__ import annotations

import random
import unittest

try:
    from Scripts.replicated_match_model import ENDED, IN_PROGRESS, ReplicatedMatchModel
except ModuleNotFoundError:  # Direct execution: python Scripts/PropertyP7LanConvergenceTests.py
    from replicated_match_model import ENDED, IN_PROGRESS, ReplicatedMatchModel  # type: ignore


ITERATIONS = 128


class PropertyP7LanConvergenceTests(unittest.TestCase):
    """**Validates: Requirements 1.10, 2.8-2.10, 4.10**"""

    @staticmethod
    def _deliver_reordered(model: ReplicatedMatchModel, rng: random.Random) -> None:
        orders: dict[str, list[int]] = {}
        for client_id in model.connected_clients:
            pending = model.pending_count(client_id)
            order = list(range(pending))
            rng.shuffle(order)
            orders[client_id] = order
        model.drain(orders)

    def test_generated_host_client_sequences_converge_and_preserve_liveness(self) -> None:
        for seed in range(ITERATIONS):
            rng = random.Random(0x7000 + seed)
            model = ReplicatedMatchModel()
            client_id = f"client-{seed}"
            difficulty = rng.randrange(3)
            map_selection = rng.choice((-100, -1, 0, 1, 2, 100))
            model.configure_match(
                difficulty=difficulty,
                map_index=map_selection,
                team_by_client=(("host", 0), (client_id, 1)),
                civilization_by_team=((0, rng.randrange(4)), (1, rng.randrange(4))),
                loadout_by_team=((0, (0, 1, 2)), (1, (0, 1, 2))),
            )
            self.assertTrue(model.join(client_id), f"seed={seed}")
            self._deliver_reordered(model, rng)
            self.assertEqual(IN_PROGRESS, model.host_snapshot.phase, f"seed={seed}")
            self.assertEqual(model.host_snapshot, model.snapshot_for("host"), f"seed={seed}")
            self.assertEqual(model.host_snapshot, model.snapshot_for(client_id), f"seed={seed}")
            self.assertIn(model.host_snapshot.map_index, (0, 1), f"seed={seed}")

            # A failed third-party Join IP must not invent a connected match or
            # alter the already-operable host/client pair.
            self.assertFalse(model.join(f"failed-{seed}", succeed=False), f"seed={seed}")
            self.assertNotIn(f"failed-{seed}", model.connected_clients, f"seed={seed}")
            self.assertTrue(model.host_operable, f"seed={seed}")
            self.assertEqual("Match.JoinFailed", model.events[-1]["code"], f"seed={seed}")

            unit_ids: list[str] = []
            for step in range(rng.randrange(8, 18)):
                actor = rng.choice(("host", client_id))
                kind = rng.choice(("movement", "menu", "summon", "combat"))
                if kind == "summon":
                    self.assertTrue(model.request(actor, "summon", archetype=rng.randrange(3)), f"seed={seed} step={step}")
                    unit_ids.append(model.host_snapshot.summoned_units[-1][0])
                elif kind == "combat":
                    unit_id = rng.choice(unit_ids) if unit_ids else "shrine"
                    self.assertTrue(model.request(actor, "combat", unit_id=unit_id, damage=rng.randrange(1, 100)), f"seed={seed} step={step}")
                else:
                    self.assertTrue(model.request(actor, kind), f"seed={seed} step={step}")
                self._deliver_reordered(model, rng)
                for connected in model.connected_clients:
                    self.assertEqual(model.host_snapshot, model.snapshot_for(connected), f"seed={seed} step={step} client={connected}")

            # Possession is tested after at least one generated summon, and the
            # remaining host must continue to process input after disconnect.
            if unit_ids:
                self.assertTrue(model.request(client_id, "possession", unit_id=unit_ids[0]), f"seed={seed}")
                self._deliver_reordered(model, rng)
            self.assertTrue(model.disconnect(client_id), f"seed={seed}")
            self.assertNotIn(client_id, model.connected_clients, f"seed={seed}")
            self.assertTrue(model.host_operable, f"seed={seed}")
            self.assertTrue(model.request("host", "movement"), f"seed={seed}")
            self.assertTrue(model.request("host", "winner", team=0), f"seed={seed}")
            self._deliver_reordered(model, rng)
            self.assertEqual(ENDED, model.host_snapshot.phase, f"seed={seed}")
            self.assertEqual(model.host_snapshot, model.snapshot_for("host"), f"seed={seed}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
