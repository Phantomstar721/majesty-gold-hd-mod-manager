"""Final script/description -> MMFR handoff, without preparing a profile.

All cases call the same pure finalizer used by composition. Installed cases
read real inputs and generate source bundles in memory; no compiler or package
output is invoked. Expected hidden IDs are not derived using the collector.
"""
from dataclasses import replace
from itertools import permutations
import struct
import unittest
import xml.etree.ElementTree as ET

from majesty_cam import compose
from majesty_cam.descriptions import DescriptionMergeResult, parse_descriptions
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.inventory_spell_display import CAPABILITY
from majesty_cam.package import load_package
from majesty_cam.runtime_capabilities import decode_runtime_capability_manifest
from majesty_cam.runtime_features import (
    EnchantmentRowFeature, MapFogQueryFeature, MovementQueryFeature,
    NameGeneratorFeature, NativeTimingFeature, RuntimeFeatureRegistry,
    decode_runtime_feature_registry, derive_feature_runtime_capabilities,
    encode_runtime_feature_registry, normalize_runtime_features,
)
from majesty_cam.scoped_output import ScriptBundle
from majesty_cam.script_review import group_conflicts
from majesty_cam.spell_discovery import discover, transform_descriptions
from test_selected_feature_boundaries import GOG, PACKAGES, STEAM


def action(identifier, name, *, flags="IsSpell", kind="Action"):
    element = ET.Element("Description", type=kind, subType="Standard", ID=identifier, Name=name)
    if flags is not None:
        ET.SubElement(ET.SubElement(element, "Game"), "Flags", value=flags)
    return element


def descriptions(*elements):
    root = ET.Element("Descriptions")
    root.extend(elements)
    document = parse_descriptions(ET.tostring(root, encoding="utf-8"))
    return DescriptionMergeResult(document, document.to_bytes(), (), ())


def output(name, instructions):
    source = parse_gpl(f"function {name}(agent Actor)\ndeclare\nbegin\n{instructions}\nend\n")
    source_set = SemanticMergeResult(source.items, ()).emit_project_source_set()
    return compose.GplComposeResult(source_set, (), (), (), ())


def bundle(common="", base="", expansion=""):
    return ScriptBundle(output("Common", common), (
        ("Majesty", output("Base", base)),
        ("MajestyExpansion", output("Expansion", expansion)),
    ))


def learn(name, visibility="FALSE"):
    argument = "" if visibility is None else ", " + visibility
    return f'$LearnSpell(Actor, "{name}"{argument});'


class RegistryWireAssertions:
    def assert_native_hidden_wire(self, registry, payload, expected):
        self.assertEqual(registry.hidden_inventory_actions, expected)
        self.assertEqual(decode_runtime_feature_registry(payload), registry)
        self.assertEqual(encode_runtime_feature_registry(registry), payload)
        if expected:
            # Native RuntimeFeatureRegistry.cpp reads strictly increasing U32s,
            # not text FourCCs. Hidden records are the final MMFR section.
            count_offset = len(payload) - 4 * (len(expected) + 1)
            self.assertEqual(struct.unpack_from("<I", payload, count_offset)[0], len(expected))
            values = struct.unpack_from(f"<{len(expected)}I", payload, count_offset + 4)
            self.assertEqual(values, tuple(struct.unpack("<I", value.encode("ascii"))[0] for value in expected))
            self.assertTrue(all(left < right for left, right in zip(values, values[1:])))


class GeneratedRegistryHandoffTests(RegistryWireAssertions, unittest.TestCase):
    def finalize(self, scripts, stock=None, resolved=None, registry=None):
        return compose.finalize_script_runtime_feature_registry(
            registry or RuntimeFeatureRegistry(), scripts, stock or {},
            resolved if resolved is not None else descriptions())

    def test_three_outputs_union_uses_native_order_and_deduplicates_stably(self):
        records = descriptions(action("A021", "Strength"), action("A040", "Shield"),
                               action("APS1", "Private"), action("A020", "Speed"))
        calls = (learn("Strength") + learn("Speed"),
                 learn("Shield") + learn("Private") + learn("Strength"),
                 learn("Private") + learn("Speed"))
        expected = ("A020", "A040", "A021", "APS1")
        self.assertNotEqual(expected, tuple(sorted(expected)), "fixture must expose textual sorting")
        payloads = []
        for parts in permutations(calls):
            for reverse_patches in (False, True):
                scripts = bundle(*parts)
                if reverse_patches:
                    scripts = replace(scripts, patches=tuple(reversed(scripts.patches)))
                with self.subTest(parts=parts, reverse_patches=reverse_patches):
                    registry, payload = self.finalize(scripts, records.document.index, records)
                    self.assert_native_hidden_wire(registry, payload, expected)
                    payloads.append(payload)
        self.assertTrue(all(payload == payloads[0] for payload in payloads))

    def test_effective_descriptions_replace_stock_by_key_before_classification(self):
        stock = descriptions(action("A020", "OldName"), action("A021", "StockOnly"),
                             action("APS1", "NoLongerSpell"))
        selected = descriptions(action("A020", "SelectedName"), action("APS1", "NoLongerSpell", flags="Item"),
                                action("A040", "PrivateName"), action("A040", "PrivateName", kind="Unit"))
        scripts = bundle("".join(learn(name) for name in (
            "OldName", "SelectedName", "StockOnly", "NoLongerSpell", "PrivateName")))
        original_stock = dict(stock.document.index)
        registry, payload = self.finalize(scripts, original_stock, selected)
        self.assert_native_hidden_wire(registry, payload, ("A020", "A040", "A021"))
        self.assertEqual(original_stock, stock.document.index, "the stock snapshot must remain unchanged")

    def test_same_named_distinct_actions_remain_ambiguous_after_overlay(self):
        stock = descriptions(action("A020", "Shared"), action("A040", "StockOnly"))
        selected = descriptions(action("APS1", "sHaReD"), action("APS2", "Private"))
        registry, payload = self.finalize(bundle(learn("Shared"), learn("StockOnly"), learn("Private")),
                                          stock.document.index, selected)
        self.assert_native_hidden_wire(registry, payload, ("A040", "APS2"))

    def test_visible_default_or_computed_visibility_in_any_other_output_vetoes_only_that_name(self):
        records = descriptions(action("A040", "Mixed"), action("APS1", "Hidden"))
        for hidden_scope, visible_scope in permutations(range(3), 2):
            for visibility in (None, "TRUE", "Visibility"):
                parts = ["", "", ""]
                parts[hidden_scope] = learn("Mixed") + learn("Hidden")
                parts[visible_scope] = learn("Mixed", visibility)
                with self.subTest(hidden_scope=hidden_scope, visible_scope=visible_scope, visibility=visibility):
                    registry, payload = self.finalize(bundle(*parts), records.document.index)
                    self.assert_native_hidden_wire(registry, payload, ("APS1",))

    def test_dynamic_names_indirect_calls_and_malformed_calls_in_other_output_veto_global_inference(self):
        records = descriptions(action("A040", "Hidden"), action("APS1", "AlsoHidden"))
        uncertain = ('$LearnSpell(Actor, ActionName, FALSE);', 'Callback = $LearnSpell;',
                     '$LearnSpell(Actor, "Hidden", FALSE, Extra);')
        for hidden_scope, uncertain_scope in permutations(range(3), 2):
            for instruction in uncertain:
                parts = ["", "", ""]
                parts[hidden_scope] = learn("Hidden") + learn("AlsoHidden")
                parts[uncertain_scope] = instruction
                with self.subTest(hidden_scope=hidden_scope, uncertain_scope=uncertain_scope, instruction=instruction):
                    registry, payload = self.finalize(bundle(*parts), records.document.index)
                    self.assert_native_hidden_wire(registry, payload, ())
                    self.assertNotIn(CAPABILITY, derive_feature_runtime_capabilities((CAPABILITY,), registry))

    def test_existing_registry_features_survive_and_hidden_ids_are_recomputed(self):
        original = normalize_runtime_features((
            NameGeneratorFeature("NM90", ("HN90", "HN91", "HN92", "HN93")),
            EnchantmentRowFeature("EF90", "Existing row"), MapFogQueryFeature(), MovementQueryFeature(),
            NativeTimingFeature(("A020",), ("EF90",)),
        ))
        previous = replace(original, hidden_inventory_actions=("ZZ99",))
        registry, payload = self.finalize(bundle(learn("Hidden")),
            descriptions(action("A040", "Hidden")).document.index, registry=previous)
        self.assertEqual(replace(registry, hidden_inventory_actions=()), original)
        self.assert_native_hidden_wire(registry, payload, ("A040",))
        before = set(derive_feature_runtime_capabilities((), original))
        self.assertEqual(set(derive_feature_runtime_capabilities((), registry)), before | {CAPABILITY})
        self.assertEqual(previous.hidden_inventory_actions, ("ZZ99",))

    def test_empty_missing_and_non_spell_actions_clear_stale_hidden_registry(self):
        previous = RuntimeFeatureRegistry(movement_query=True, hidden_inventory_actions=("A040",))
        records = descriptions(action("A040", "NotSpell", flags=None), action("APS1", "OnlyUnit", kind="Unit"))
        for scripts in (bundle(), bundle(learn("Absent")), bundle(learn("NotSpell"), learn("OnlyUnit"))):
            with self.subTest(scripts=scripts):
                registry, payload = self.finalize(scripts, records.document.index, registry=previous)
                self.assertEqual(registry, RuntimeFeatureRegistry(movement_query=True))
                self.assertEqual(payload, encode_runtime_feature_registry(RuntimeFeatureRegistry(movement_query=True)))
                self.assertNotIn(CAPABILITY, derive_feature_runtime_capabilities((CAPABILITY,), registry))

    def test_final_capability_manifest_tracks_final_hidden_table_without_duplicates(self):
        original = RuntimeFeatureRegistry(map_fog_query=True, movement_query=True)
        records = descriptions(action("A040", "Hidden"))
        hidden, _ = self.finalize(bundle(learn("Hidden")), records.document.index, registry=original)
        capabilities, payload = compose._derive_runtime_capabilities(
            (CAPABILITY,), has_private_activity_text=False, runtime_feature_registry=hidden)
        self.assertEqual(decode_runtime_capability_manifest(payload), capabilities)
        self.assertEqual(capabilities.count(CAPABILITY), 1)
        self.assertEqual(set(capabilities), set(derive_feature_runtime_capabilities((), original)) | {CAPABILITY})
        empty, _ = self.finalize(bundle(), records.document.index, registry=hidden)
        capabilities, payload = compose._derive_runtime_capabilities(
            capabilities, has_private_activity_text=False, runtime_feature_registry=empty)
        self.assertEqual(decode_runtime_capability_manifest(payload), capabilities)
        self.assertNotIn(CAPABILITY, capabilities)
        self.assertEqual(set(capabilities), set(derive_feature_runtime_capabilities((), original)))

    def test_malformed_collected_fourcc_is_rejected_by_final_serialization(self):
        for identifier in ("ABC", "ABCDE", "A B1", "éBC1"):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(compose.ComposeError, "runtime features"):
                self.finalize(bundle(learn("Hidden")), descriptions(action(identifier, "Hidden")).document.index)

    def test_existing_invalid_feature_is_not_silently_dropped_at_handoff(self):
        invalid = RuntimeFeatureRegistry(native_timing=NativeTimingFeature(("bad",), ()))
        with self.assertRaisesRegex(compose.ComposeError, "four printable ASCII bytes"):
            self.finalize(bundle(), registry=invalid)

    def test_registry_limit_is_enforced_after_cross_output_collection(self):
        records = descriptions(*(action(f"X{index:03X}", f"Hidden{index}") for index in range(1025)))
        calls = [learn(f"Hidden{index}") for index in range(1025)]
        registry, payload = self.finalize(bundle("".join(calls[:400]), "".join(calls[400:800]),
                                                 "".join(calls[800:1024])), records.document.index)
        expected = tuple(sorted((f"X{index:03X}" for index in range(1024)),
                                key=lambda value: struct.unpack("<I", value.encode("ascii"))[0]))
        self.assert_native_hidden_wire(registry, payload, expected)
        with self.assertRaisesRegex(compose.ComposeError, "count 1025 exceeds.*limit of 1024"):
            self.finalize(bundle("".join(calls[:400]), "".join(calls[400:800]), "".join(calls[800:])),
                          records.document.index)

    def test_encoder_and_native_wire_validation_are_not_relaxed_by_finalization(self):
        records = descriptions(action("A021", "Strength"), action("A040", "Shield"))
        registry, payload = self.finalize(bundle(learn("Strength"), learn("Shield")), records.document.index)
        self.assert_native_hidden_wire(registry, payload, ("A040", "A021"))
        for ids, message in ((("A021", "A040"), "numeric FourCC order"),
                             (("A040", "A040"), "duplicate IDs")):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, message):
                encode_runtime_feature_registry(replace(registry, hidden_inventory_actions=ids))
        offset = len(payload) - 12
        malformed = (payload[:-1], payload + b"x",
                     payload[:offset] + struct.pack("<I", 1025) + payload[offset+4:],
                     payload[:offset+4] + payload[-4:] + payload[-8:-4],
                     payload[:offset+4] + payload[-8:-4] * 2)
        for index, wire in enumerate(malformed):
            with self.subTest(case=index), self.assertRaises(ValueError):
                decode_runtime_feature_registry(wire)


class InstalledGeneratedRegistryHandoffTests(RegistryWireAssertions, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(root) for _, root in PACKAGES if not root.is_dir()]
        cls.games = tuple(game for game in (STEAM, GOG) if (game / "SDK/OriginalQuests").is_dir())
        if missing or not cls.games:
            raise unittest.SkipTest("installed source fixtures unavailable: " + ", ".join(missing or [str(STEAM)]))
        cls.inventories = tuple(compose.inventory_package(compose.SelectedMod(alias, load_package(root)))
                                for alias, root in PACKAGES)

    def test_actual_selected_sources_continue_through_effective_actions_and_registry_handoff(self):
        # Literal installed IDs deliberately interleave stock A0xx, private
        # APSx, and native NRxx/ARxx records in their U32 order.
        expected = ("A020", "A040", "A021", "APS1", "NRd1", "NRi1", "NRk1", "A022", "APS2", "ARa2",
                    "A023", "APS3", "A024", "A054", "APS4", "A025", "A039")
        original = compose.resolve_runtime_feature_registry(self.inventories)
        self.assertTrue(original.features, "installed fixture must retain real preexisting runtime features")
        priority = [i.selected.package.mod_id.strip("{}").casefold() for i in self.inventories]

        def choose(conflicts):
            return {pair.identity: min((pair.left.owner, pair.right.owner), key=priority.index)
                    for pair in group_conflicts(conflicts)}

        for game in self.games:
            with self.subTest(game=str(game)):
                stock = {key: value[0] for key, value in compose._load_effective_stock_descriptions(game).items()}
                resolved = compose.merge_description_resources(self.inventories, stock_records=stock)
                resolved, potions = compose.prepare_potion_descriptions(
                    resolved, stock, compose.potion_policies(self.inventories))
                spell_plan = discover(compose._spell_policy_bindings(self.inventories),
                                      tuple(record.to_element() for record in resolved.document.records))
                resolved = transform_descriptions(resolved, spell_plan)
                scripts = compose.prepare_gpl_bundle(game, self.inventories, script_conflict_resolver=choose,
                    potion_plan=potions, spell_policy_plan=spell_plan, source_context_descriptions=resolved)
                self.assertEqual({scope for scope, _ in scripts.outputs}, {"Any", "Majesty", "MajestyExpansion"})
                finalized, payload = compose.finalize_script_runtime_feature_registry(original, scripts, stock, resolved)
                self.assert_native_hidden_wire(finalized, payload, expected)
                self.assertEqual(replace(finalized, hidden_inventory_actions=()), original)
                self.assertEqual(finalized.hidden_inventory_actions[1:3], ("A040", "A021"))
                effective = {**stock, **resolved.document.index}
                names = {effective[("Action", identifier)].to_element().get("Name").casefold()
                         for identifier in ("APS1", "APS2", "APS3", "APS4")}
                self.assertEqual(names, {"alchemist_strength_potion", "alchemist_shapeshift_potion",
                                        "alchemist_fire_balm", "alchemist_regeneration_elixer"})
                self.assertIn(CAPABILITY, derive_feature_runtime_capabilities((), finalized))


if __name__ == "__main__":
    unittest.main()
