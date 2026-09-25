from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from majesty_cam.action_callback_bridge import bridge_symbol, bridge_source, add_bridges, validate_bridge
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.compose import compile_gpl
from majesty_cam.stock_controller_features import StockMx04Mx05OccupantActionPanel
from gpl_sampler_harness import SamplerHarness, Agent


class ActionCallbackBridgeTests(unittest.TestCase):
    def test_generated_once_and_registry_uses_integer_adapter(self):
        from majesty_cam.stock_controller_registry import resolve_stock_controller_registry
        feature = StockMx04Mx05OccupantActionPanel("offers", "Example", "MX05", 0x7101,
                                                  "Example_Cost", "Example_Action")
        inventory = SimpleNamespace(selected=SimpleNamespace(package=SimpleNamespace(
            definition=SimpleNamespace(runtime_features=(feature,)))))
        original = SemanticMergeResult((), ())
        result = add_bridges(original, (inventory, inventory))
        self.assertEqual(len(result.items), 1)
        with self.assertRaisesRegex(ValueError, "collides"):
            add_bridges(result, (inventory,))
        registry = resolve_stock_controller_registry((feature,),
            {"offers": (int.from_bytes(b"CG01", "little"), int.from_bytes(b"CG02", "little"))})
        self.assertEqual(registry.occupant_action_panels[0].action_callback_symbol,
                         bridge_symbol("Example_Action"))

    def test_boolean_result_is_converted_once_without_coercion(self):
        for result in (False, True):
            vm = SamplerHarness(bridge_source("Example_Action"))
            calls = []
            def action(subject):
                calls.append(subject)
                return result
            vm.calls["example_action"] = action
            subject = Agent()
            self.assertEqual(vm.call(bridge_symbol("Example_Action"), subject), int(result))
            self.assertEqual(calls, [subject])

    def test_exact_bridge_and_collision_checks_and_compiler(self):
        from majesty_cam.gameplay_events import require_callback
        from majesty_cam.gpl import DefinitionKind
        callback = "function Example_Action(agent Subject) is boolean\ndeclare\nbegin\nreturn True;\nend\n"
        source = callback + bridge_source("Example_Action")
        parsed = parse_gpl(source)
        functions = {item.normalized_name: item.text for item in parsed.items}
        counts = dict.fromkeys(functions, 1)
        symbol = bridge_symbol("Example_Action")
        name, text = validate_bridge(symbol, functions, counts)
        require_callback(parse_gpl(text).require(DefinitionKind.FUNCTION, name), name, ("agent",), True)
        self.assertEqual(symbol, bridge_symbol("example_action"))
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_bridge(symbol, {**functions, symbol.casefold(): functions[symbol.casefold()].replace("return 1", "return 0")}, counts)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_bridge(symbol, functions, {**counts, "example_action": 2})
        compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
        if compiler.is_file():
            result = SemanticMergeResult(parsed.items, ())
            with TemporaryDirectory(prefix="manager-action-abi-") as tmp:
                compile_gpl(result.emit_project_source_set(), compiler, Path(tmp)/"compiler")


if __name__ == "__main__":
    unittest.main()
