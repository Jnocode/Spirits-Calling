#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure drift-guard tests binding the canonical asset manifest to the material
hook contract and to the package-closure runtime reference set.

These close two coverage gaps without needing imported assets or a cooked
package:

* 6.5 — the Editor wiring script ``wire_civ_materials.py`` (which hard-imports
  ``unreal`` and cannot run headlessly) had no test. Its material parameter
  names, material paths and civilization/arena hooks must stay bound to the
  canonical manifest so a manifest edit cannot silently break Editor wiring.
* 6.4 — the package-closure validator's runtime reference set must stay a
  superset of the manifest's runtime paths, and store-only assets must never
  enter that set, guarding manifest/closure drift.

Actual runtime resolution, cook closure and material import still require
imported assets and an accepted cooked/staged package and remain blocked.
"""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    from Scripts.asset_manifest_validator import (
        MANIFEST_PATH,
        NO_HOOK_ASSIGNED,
        load_manifest,
        runtime_entries,
        store_only_entries,
    )
    from Scripts.package_closure_validator import _required_references
except ModuleNotFoundError:
    from asset_manifest_validator import (
        MANIFEST_PATH,
        NO_HOOK_ASSIGNED,
        load_manifest,
        runtime_entries,
        store_only_entries,
    )
    from package_closure_validator import _required_references

CIV_PATTERN_HOOK = "BodyMID.PatternTex|SoulShrine.PatternTex"
EXPECTED_CIVILIZATIONS = {"East", "Norse", "Egypt", "Cyber"}
EXPECTED_ARENA_HOOKS = {
    "ArenaMaterialHook.Void.Ground",
    "ArenaMaterialHook.Void.Sky",
    "ArenaMaterialHook.Sands.Ground",
    "ArenaMaterialHook.Sands.Sky",
}
WIRE_SCRIPT = Path(__file__).resolve().parent / "wire_civ_materials.py"


class MaterialHookContract(unittest.TestCase):
    """6.5 — manifest hooks must match what the Editor wiring script wires."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(MANIFEST_PATH)
        cls.entries = cls.manifest["entries"]

    def test_four_civilization_patterns_share_the_body_and_shrine_hook(self) -> None:
        civ = [e for e in self.entries if e.get("category") == "civilization_pattern"]
        self.assertEqual(4, len(civ))
        self.assertEqual(EXPECTED_CIVILIZATIONS, {e.get("civilization") for e in civ})
        for entry in civ:
            self.assertEqual(CIV_PATTERN_HOOK, entry.get("hook"))

    def test_four_arena_textures_map_bijectively_to_arena_hooks(self) -> None:
        arena = [e for e in self.entries if e.get("category") == "arena_texture"]
        self.assertEqual(4, len(arena))
        hooks = [e.get("hook") for e in arena]
        self.assertEqual(EXPECTED_ARENA_HOOKS, set(hooks))
        self.assertEqual(len(hooks), len(set(hooks)))  # bijective, no reuse

    def test_store_capsule_has_no_material_hook_and_no_runtime_path(self) -> None:
        store = [e for e in self.entries if e.get("category") == "store_draft"]
        self.assertEqual(1, len(store))
        self.assertEqual(NO_HOOK_ASSIGNED, store[0].get("hook"))
        self.assertIsNone(store[0].get("runtimePath"))
        self.assertEqual("store_only", store[0].get("cookClass"))

    def test_editor_wiring_script_stays_bound_to_the_manifest_contract(self) -> None:
        # The Editor script hard-imports `unreal`; assert its contract by source
        # so a manifest/param rename cannot silently desync the two.
        text = WIRE_SCRIPT.read_text(encoding="utf-8")
        for token in ('"Color"', '"PatternTex"', '"EmissiveStrength"', "/Game/Materials", "M_UnitBody"):
            self.assertIn(token, text, f"wire_civ_materials.py must reference {token}")
        # It must drive imports from the canonical manifest's runtime entries,
        # not a hard-coded list, so hooks/paths follow the manifest.
        self.assertIn("cookClass", text)
        self.assertIn('"runtime"', text)
        self.assertIn('entry["runtimePath"]', text)
        self.assertIn('entry["hook"]', text)


class RuntimeReferenceContract(unittest.TestCase):
    """6.4 — closure runtime references must track the manifest runtime paths."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(MANIFEST_PATH)

    def test_closure_requires_every_manifest_runtime_path(self) -> None:
        runtime_paths = {e["runtimePath"] for e in runtime_entries(self.manifest)}
        self.assertTrue(runtime_paths)  # the manifest declares runtime assets
        # package_manifest empty: the manifest-derived references still appear.
        references = {path for path, _ in _required_references({}, self.manifest)}
        missing = runtime_paths - references
        self.assertEqual(set(), missing, f"closure omits manifest runtime paths: {missing}")

    def test_store_only_assets_never_enter_the_runtime_reference_set(self) -> None:
        references = {path for path, _ in _required_references({}, self.manifest)}
        for entry in store_only_entries(self.manifest):
            # Store-only assets carry no runtimePath and must not be referenced.
            self.assertIsNone(entry.get("runtimePath"))
            for token in ("Store_capsule_concept", "store.capsule.concept"):
                self.assertNotIn(token, references)


if __name__ == "__main__":
    unittest.main(verbosity=2)
