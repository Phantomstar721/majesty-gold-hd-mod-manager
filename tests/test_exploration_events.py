from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import json

from majesty_cam.exploration_events import EVENT, CAPABILITY, MAX_EXPRESSION_INTEGER, service_source, validate_service
from majesty_cam.gameplay_events import add_gameplay_event_observers, event_stock_paths
from majesty_cam.gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from majesty_cam.compose import _derive_runtime_capabilities, compile_gpl
from majesty_cam.shared_features import StockGameplayEventObserver, EVENT_SIGNATURES
from gpl_sampler_harness import Agent, SamplerHarness


class ExplorationEventsTests(unittest.TestCase):
    def test_source_only_native_package_is_merge_without_dummy_cam(self):
        from majesty_cam.manager.catalog import scan_catalog, CatalogKind
        from majesty_cam.manager.preflight import prepare_merge_package
        from majesty_cam.manager.compatibility import CompatibilityRegistry
        mod_id = "{BC0532A2-7A04-445A-B6D1-8BAC69FBC455}"
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "SourceOnly"
            package.mkdir()
            (package / "Content.gpl").write_text(
                "function Consumer(agent Source, integer Owner, integer Tiles, integer Epoch)\n"
                "declare\nbegin\nend\n", encoding="utf-8")
            (package / "Content.bcd").write_bytes(b"language-fixture-placeholder")
            (package / "Mod.mmxml").write_text(
                f'<Majesty><Mod id="{mod_id}"><DisplayName lang="en_US">Fixture</DisplayName>'
                '<DataConfiguration><Dataset base="Any"><Load><GPL>'
                '<Target>Content.bcd</Target><Source>Content.gpl</Source></GPL></Load>'
                '</Dataset></DataConfiguration></Mod></Majesty>', encoding="utf-8")
            definition = dict(schema_version=3, mod_id=mod_id, internal_name="Fixture",
                              display_name="Fixture", custom_buildings=[], runtime_features=[
                                  dict(type="stock.gameplay-event-observer.v1", feature_key="tiles",
                                       event=EVENT, callback_symbol="Consumer")])
            path = package / "mod-definition.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            entry = scan_catalog(local_mods_root=Path(tmp)).entries[0]
            self.assertEqual(entry.kind, CatalogKind.MERGE)
            self.assertFalse(entry.has_cam)
            prepared = prepare_merge_package(content_id=mod_id, display_name="Fixture",
                source_root=package, registry=CompatibilityRegistry({}))
            self.assertEqual(prepared.issues, ())
            self.assertEqual(prepared.inventory.cams, ())
            definition["runtime_features"][0]["callback_symbol"] = "MM_Bad"
            path.write_text(json.dumps(definition), encoding="utf-8")
            entry = scan_catalog(local_mods_root=Path(tmp)).entries[0]
            self.assertEqual(entry.kind, CatalogKind.MERGE)
            self.assertFalse(entry.merge_ready)
            definition["runtime_features"] = []
            path.write_text(json.dumps(definition), encoding="utf-8")
            self.assertEqual(scan_catalog(local_mods_root=Path(tmp)).entries[0].kind, CatalogKind.STANDARD)

    def harness(self):
        vm = SamplerHarness(service_source(("Consumer_A", "Consumer_B")))
        calls = []
        vm.calls["getunitplayernumber"] = lambda source: source.owner
        vm.calls["isvalidgamepiece"] = lambda source: isinstance(source, Agent) and source.valid
        for key in ("consumer_a", "consumer_b"):
            vm.calls[key] = lambda *args, key=key: calls.append((key, *args))
        return vm, calls

    def agent(self, owner=0):
        unit = Agent()
        unit.owner, unit.valid = owner, True
        return unit

    def test_opt_in_native_event_has_no_stock_source_dependency(self):
        feature = StockGameplayEventObserver("tiles", EVENT, "Consumer_A")
        self.assertEqual(event_stock_paths((feature,)), ())
        self.assertEqual(EVENT_SIGNATURES[EVENT], ("agent", "integer", "integer", "integer"))
        caps, _ = _derive_runtime_capabilities((CAPABILITY,), has_private_activity_text=False)
        self.assertNotIn(CAPABILITY, caps)
        caps, _ = _derive_runtime_capabilities((), has_private_activity_text=False, has_source_exploration=True)
        self.assertIn(CAPABILITY, caps)

    def test_saved_pending_and_completed_delivery_do_not_replay(self):
        vm, calls = self.harness()
        unit = self.agent()
        self.assertEqual(vm.call("MM_EO_Record", unit, 0, 73), 1)
        self.assertEqual(vm.call("MM_EO_Record", unit, 0, 55), 1)
        snapshot = deepcopy(vm.root)
        vm.root = snapshot
        vm.call("MM_EO_Dispatch")
        self.assertEqual([row[2:] for row in calls], [(0, 128, 0), (0, 128, 0)])
        vm.root = deepcopy(vm.root)
        vm.call("MM_EO_Dispatch")
        self.assertEqual(len(calls), 2)

    def test_owner_away_and_back_invalidates_pending_and_advances_epoch(self):
        vm, calls = self.harness()
        unit = self.agent()
        vm.call("MM_EO_Record", unit, 0, 73)
        vm.call("MM_EO_Invalidate", unit)
        unit.owner = 1
        vm.call("MM_EO_Invalidate", unit)
        unit.owner = 0
        vm.call("MM_EO_Record", unit, 0, 55)
        vm.call("MM_EO_Dispatch")
        self.assertEqual([row[2:] for row in calls], [(0, 55, 2), (0, 55, 2)])

    def test_nested_levelup_reveal_is_a_separate_batch(self):
        vm, calls = self.harness()
        first, second = self.agent(), self.agent()
        vm.call("MM_EO_Record", first, 0, 128)
        vm.call("MM_EO_Record", second, 0, 5)
        original = vm.calls["consumer_a"]
        def callback(source, owner, tiles, epoch):
            original(source, owner, tiles, epoch)
            if source is first:
                vm.call("MM_EO_Record", second, 0, 7)
        vm.calls["consumer_a"] = callback
        vm.call("MM_EO_Dispatch")
        self.assertEqual([row[3] for row in calls], [128, 128, 5, 5])
        vm.call("MM_EO_Dispatch")
        self.assertEqual([row[3] for row in calls], [128, 128, 5, 5, 7, 7])

    def test_transfer_or_deletion_during_dispatch_cancels_later_delivery(self):
        for delete in (False, True):
            vm, calls = self.harness()
            unit = self.agent()
            vm.call("MM_EO_Record", unit, 0, 1)
            def first(*args):
                if delete:
                    unit.valid = False
                else:
                    vm.call("MM_EO_Invalidate", unit)
            vm.calls["consumer_a"] = first
            vm.call("MM_EO_Dispatch")
            self.assertEqual(calls, [])

    def test_overflow_is_explicit_and_does_not_corrupt_pending(self):
        vm, _ = self.harness()
        unit = self.agent()
        vm.call("MM_EO_Record", unit, 0, MAX_EXPRESSION_INTEGER)
        self.assertEqual(vm.call("MM_EO_Record", unit, 0, 1), -2)
        self.assertEqual(unit["MM_ExplorationPending_v1"], MAX_EXPRESSION_INTEGER)
        unit["MM_ExplorationEpoch_v1"] = MAX_EXPRESSION_INTEGER
        self.assertEqual(vm.call("MM_EO_Invalidate", unit), -2)

    def test_first_reveal_bound_matches_stock_fixed_point_operators(self):
        # Traced GplInteger operators: 0x59A850 shifts left 10;
        # subtraction 0x59ABD2 and comparison 0x59AA95 use that representation.
        import ctypes
        import re
        fixed = lambda value: ctypes.c_int32(value << 10).value
        def overflow(tiles, pending, bound):
            remaining = ctypes.c_int32(fixed(bound)-fixed(pending)).value >> 10
            return fixed(tiles) > fixed(remaining)
        self.assertTrue(overflow(17, 0, 2147483647))  # Exact reported crash.
        self.assertFalse(overflow(17, 0, MAX_EXPRESSION_INTEGER))
        self.assertFalse(overflow(17, MAX_EXPRESSION_INTEGER-17, MAX_EXPRESSION_INTEGER))
        self.assertTrue(overflow(17, MAX_EXPRESSION_INTEGER-16, MAX_EXPRESSION_INTEGER))
        text = service_source(("Consumer_A",))
        literals = [int(n) for n in re.findall(r"\b\d+\b", text)]
        self.assertIn(MAX_EXPRESSION_INTEGER, literals)
        self.assertTrue(all(n <= MAX_EXPRESSION_INTEGER for n in literals))
        vm, calls = self.harness()
        unit = self.agent()
        self.assertEqual(vm.call("MM_EO_Record", unit, 0, 17), 1)
        vm.call("MM_EO_Dispatch")
        self.assertEqual([row[3] for row in calls], [17, 17])

    def test_native_record_does_not_call_consumers_or_schedule(self):
        text = parse_gpl(service_source(("Consumer_A",))).require(DefinitionKind.FUNCTION, "MM_EO_Record").text
        self.assertNotIn("Consumer_A", text)
        self.assertNotIn("NewThread", service_source(("Consumer_A",)))

    def test_composition_owns_reserved_symbols_and_stock_compiler_accepts_service(self):
        source = parse_gpl("function Consumer_A(agent Source, integer Owner, integer Tiles, integer Epoch)\ndeclare\nbegin\nend\n")
        result = add_gameplay_event_observers(SemanticMergeResult(source.items, ()), {EVENT: ("Consumer_A",)}, {})
        functions = {item.normalized_name: item.text for item in result.items}
        validate_service(functions, True)
        counts = dict.fromkeys(functions, 1)
        validate_service(functions, True, counts)
        for symbol in ("consumer_a", "mm_eo_record"):
            with self.assertRaisesRegex(ValueError, "exactly once"):
                validate_service(functions, True, {**counts, symbol: 2})
        with self.assertRaisesRegex(ValueError, "without"):
            validate_service(functions, False)
        changed = dict(functions)
        changed["mm_eo_invalidate"] = changed["mm_eo_invalidate"].replace("+= 1", "+= 0")
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_service(changed, True)
        with self.assertRaisesRegex(ValueError, "collides"):
            add_gameplay_event_observers(result, {EVENT: ("Consumer_A",)}, {})
        compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
        if compiler.is_file():
            with TemporaryDirectory(prefix="manager-exploration-language-") as tmp:
                compile_gpl(result.emit_project_source_set("Fixture.gpl", "Fixture.dat"), compiler, Path(tmp)/"compiler", stem="Fixture")


if __name__ == "__main__":
    unittest.main()
