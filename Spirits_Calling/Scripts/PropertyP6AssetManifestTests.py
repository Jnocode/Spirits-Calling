#!/usr/bin/env python3
"""Generated property tests for P6 asset manifest and cook classification.

Feature: spirits-calling-requirements, Property 6:
Generated canonical and mutation inputs are checked against the external
manifest validator.  This remains a standard-library test so it can run in a
clean checkout without Unreal Editor or third-party test dependencies.
"""
from __future__ import annotations

import copy
import random
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from Scripts.asset_manifest_validator import (
        MANIFEST_PATH,
        REQUIRED_ASSETS,
        build_asset_validation_records,
        load_manifest,
        runtime_entries,
        store_only_entries,
        validate_manifest,
    )
except ModuleNotFoundError:  # Direct execution: python Scripts/PropertyP6AssetManifestTests.py
    from asset_manifest_validator import (  # type: ignore
        MANIFEST_PATH,
        REQUIRED_ASSETS,
        build_asset_validation_records,
        load_manifest,
        runtime_entries,
        store_only_entries,
        validate_manifest,
    )


Mutation = Callable[[dict[str, Any], random.Random], str | None]
ITERATIONS = 128


def _entry(manifest: dict[str, Any], asset_id: str) -> dict[str, Any]:
    return next(item for item in manifest["entries"] if item["id"] == asset_id)


def _mutate_missing_entry(manifest: dict[str, Any], rng: random.Random) -> str:
    removed = manifest["entries"].pop(rng.randrange(len(manifest["entries"])))
    return f"missing:{removed['id']}"


def _mutate_duplicate_mapping(manifest: dict[str, Any], rng: random.Random) -> str:
    target = copy.deepcopy(manifest["entries"][rng.randrange(8)])
    manifest["entries"].append(target)
    return target["id"]


def _mutate_wrong_category(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["category"] = "arena_texture" if target["category"] == "civilization_pattern" else "civilization_pattern"
    return target["id"]


def _mutate_wrong_source(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["source"] = target["source"].replace(".png", "_mutated.png")
    return target["id"]


def _mutate_wrong_runtime_path(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["runtimePath"] = str(target["runtimePath"]) + "_mutated"
    return target["id"]


def _mutate_wrong_hook(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["hook"] = "ArenaMaterialHook.Mutated"
    return target["id"]


def _mutate_missing_hook(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["hook"] = ""
    return target["id"]


def _mutate_wrong_civilization(manifest: dict[str, Any], rng: random.Random) -> str:
    civs = [item for item in manifest["entries"] if item["category"] == "civilization_pattern"]
    target = civs[rng.randrange(len(civs))]
    target["civilization"] = "Cyber" if target["civilization"] != "Cyber" else "East"
    return target["id"]


def _mutate_wrong_arena_pair(manifest: dict[str, Any], rng: random.Random) -> str:
    arenas = [item for item in manifest["entries"] if item["category"] == "arena_texture"]
    target = arenas[rng.randrange(len(arenas))]
    target["mapStyle"] = "Sands" if target["mapStyle"] == "Void" else "Void"
    target["surface"] = "sky" if target["surface"] == "ground" else "ground"
    return target["id"]


def _mutate_non_power_of_two(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["validation"] = {"width": 1000 + 2 * rng.randrange(16) + 1, "height": 1024}
    return target["id"]


def _mutate_over_size(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["validation"] = {"width": 4096, "height": 2048}
    return target["id"]


def _mutate_undocumented_skybox_exception(manifest: dict[str, Any], rng: random.Random) -> str:
    target = _entry(manifest, "arena.void.sky" if rng.randrange(2) == 0 else "arena.sands.sky")
    target["validation"] = {"width": 4096, "height": 2048}
    target["skyboxException"] = {
        "documented": True,
        "exceptionId": "unrecorded-generated-exception",
        "evidencePath": "evidence/not-in-readiness-record.log",
    }
    return target["id"]


def _mutate_invalid_runtime_ready(manifest: dict[str, Any], rng: random.Random) -> str:
    target = manifest["entries"][rng.randrange(8)]
    target["validation"] = {"width": 1000, "height": 1024}
    target["runtimeReady"] = True
    return target["id"]


def _mutate_store_into_runtime(manifest: dict[str, Any], rng: random.Random) -> str:
    target = _entry(manifest, "store.capsule.concept")
    target["cookClass"] = "runtime"
    return target["id"]


MUTATIONS: tuple[tuple[str, Mutation], ...] = (
    ("missing-entry", _mutate_missing_entry),
    ("duplicate-mapping", _mutate_duplicate_mapping),
    ("wrong-category", _mutate_wrong_category),
    ("wrong-source", _mutate_wrong_source),
    ("wrong-runtime-path", _mutate_wrong_runtime_path),
    ("wrong-hook", _mutate_wrong_hook),
    ("missing-hook", _mutate_missing_hook),
    ("wrong-civilization", _mutate_wrong_civilization),
    ("wrong-arena-pair", _mutate_wrong_arena_pair),
    ("non-power-of-two", _mutate_non_power_of_two),
    ("over-size", _mutate_over_size),
    ("undocumented-skybox-exception", _mutate_undocumented_skybox_exception),
    ("invalid-runtime-ready", _mutate_invalid_runtime_ready),
    ("store-runtime-classification", _mutate_store_into_runtime),
)


class PropertyP6AssetManifestTests(unittest.TestCase):
    """**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.8, 4.11**"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = MANIFEST_PATH.parents[2]
        cls.canonical = load_manifest(MANIFEST_PATH)

    def test_canonical_manifest_shape_hooks_pairs_and_store_exclusion(self) -> None:
        """The generated canonical manifest is accepted and has bijective runtime classification."""
        errors = validate_manifest(self.canonical, self.project_root)
        self.assertEqual([], errors, errors)

        entries = self.canonical["entries"]
        self.assertEqual(9, len(entries))
        self.assertEqual({item["id"] for item in REQUIRED_ASSETS}, {item["id"] for item in entries})
        self.assertEqual(8, len(runtime_entries(self.canonical)))
        self.assertEqual(["store.capsule.concept"], [item["id"] for item in store_only_entries(self.canonical)])
        self.assertNotIn("RawAssets/AI/Store/Store_capsule_concept.png", {item["source"] for item in runtime_entries(self.canonical)})

        civs = [item for item in entries if item["category"] == "civilization_pattern"]
        self.assertEqual({"East", "Norse", "Egypt", "Cyber"}, {item["civilization"] for item in civs})
        self.assertEqual(4, len({item["runtimePath"] for item in civs}))
        self.assertTrue(all(item["hook"] == "BodyMID.PatternTex|SoulShrine.PatternTex" for item in civs))

        arenas = [item for item in entries if item["category"] == "arena_texture"]
        for style in ("Void", "Sands"):
            pair = {item["surface"]: item for item in arenas if item["mapStyle"] == style}
            self.assertEqual({"ground", "sky"}, set(pair))
            self.assertEqual(f"ArenaMaterialHook.{style}.Ground", pair["ground"]["hook"])
            self.assertEqual(f"ArenaMaterialHook.{style}.Sky", pair["sky"]["hook"])

        records = build_asset_validation_records(self.canonical, self.project_root)
        self.assertTrue(all(item["runtimeReady"] for item in records if item.get("classification") != "store_only"))
        self.assertFalse(next(item for item in records if item["id"] == "store.capsule.concept")["runtimeReady"])

    def test_generated_canonical_and_mutated_manifests_fail_closed(self) -> None:
        """Generated canonical/mutation cases reject every invalid entry in 128 iterations."""
        rng = random.Random(0x506)  # stable generated-input seed
        cases: list[tuple[str, Mutation]] = list(MUTATIONS)
        while len(cases) < ITERATIONS:
            cases.append(MUTATIONS[rng.randrange(len(MUTATIONS))])

        mutation_checks = 0
        covered_mutations: set[str] = set()
        for iteration, (name, mutation) in enumerate(cases[:ITERATIONS]):
            mutation_checks += 1
            covered_mutations.add(name)
            mutated = copy.deepcopy(self.canonical)
            target_id = mutation(mutated, rng)
            errors = validate_manifest(mutated, self.project_root)
            self.assertTrue(errors, f"mutation {name} unexpectedly accepted at iteration {iteration}")

            records = build_asset_validation_records(mutated, self.project_root)
            if target_id is not None and target_id.startswith("missing:"):
                removed_id = target_id.split(":", 1)[1]
                self.assertNotIn(removed_id, {item.get("id") for item in records})
                continue
            if target_id is not None:
                target_records = [item for item in records if item.get("id") == target_id]
                self.assertTrue(target_records, f"mutation {name} lost target record at iteration {iteration}")
                self.assertTrue(
                    all(item.get("runtimeReady") is False for item in target_records),
                    f"mutation {name} marked invalid target runtime-ready at iteration {iteration}: {target_records}",
                )
                self.assertTrue(
                    all(item.get("failureReason") or item.get("classification") == "store_only" for item in target_records),
                    f"mutation {name} omitted failure reason at iteration {iteration}: {target_records}",
                )

        # Canonical acceptance is checked repeatedly with fresh copies, separately
        # from the 128 invalid mutation iterations above.
        canonical_checks = 16
        for iteration in range(canonical_checks):
            self.assertEqual([], validate_manifest(copy.deepcopy(self.canonical), self.project_root), iteration)

        self.assertEqual(ITERATIONS, mutation_checks)
        self.assertEqual({name for name, _ in MUTATIONS}, covered_mutations)
        self.assertGreaterEqual(canonical_checks, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
