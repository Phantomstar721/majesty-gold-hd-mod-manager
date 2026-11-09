import unittest
from types import SimpleNamespace

from majesty_cam.action_callback_bridge import (
    add_bridges, bridge_source, bridge_symbol, validate_bridge,
)
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.stock_controller_features import StockMx05LiveAgentListPanel
from gpl_sampler_harness import Agent, SamplerHarness


class ActionBridgeTests(unittest.TestCase):
    def test_pair_preserves_order_and_translates_boolean_once(self):
        for success in (False, True):
            with self.subTest(success=success):
                vm = SamplerHarness(bridge_source('Hire', paired=True))
                building, hero = Agent(), Agent()
                calls = []
                vm.calls['hire'] = lambda *args: calls.append(args) or success
                self.assertEqual(vm.call(bridge_symbol('Hire', paired=True), building, hero), int(success))
                self.assertEqual(calls, [(building, hero)])

    def test_legacy_identity_and_single_argument_are_unchanged(self):
        import hashlib
        self.assertEqual(bridge_symbol('Hire'), 'MM_Action_' + hashlib.sha256(b'hire').hexdigest()[:24])
        self.assertNotEqual(bridge_symbol('Hire'), bridge_symbol('Hire', paired=True))
        vm = SamplerHarness(bridge_source('Hire'))
        hero, calls = Agent(), []
        vm.calls['hire'] = lambda *args: calls.append(args) or True
        self.assertEqual(vm.call(bridge_symbol('Hire'), hero), 1)
        self.assertEqual(calls, [(hero,)])

    def test_validator_rejects_swapped_arguments_and_wrong_scope(self):
        symbol = bridge_symbol('Hire', paired=True)
        callback = 'function Hire(agent Building, agent Hero) is boolean declare begin return True; end'
        functions = {symbol.casefold(): bridge_source('Hire', paired=True), 'hire': callback}
        counts = {name: 1 for name in functions}
        self.assertEqual(validate_bridge(symbol, functions, counts, paired=True), ('Hire', callback))
        with self.assertRaises(ValueError):
            validate_bridge(symbol, functions, counts)
        functions[symbol.casefold()] = functions[symbol.casefold()].replace('$Hire(Building, Hero)', '$Hire(Hero, Building)')
        with self.assertRaises(ValueError):
            validate_bridge(symbol, functions, counts, paired=True)

    def test_generation_selects_pair_from_declared_scope(self):
        panel = StockMx05LiveAgentListPanel(
            'hire', 'Forge', 'FH01', 8100, 'Count', 'Row', 'Revision',
            None, None, None, None, 'Cost', 'Hire',
            action_agent_scope='parent-and-selected-row')
        inventory = SimpleNamespace(selected=SimpleNamespace(package=SimpleNamespace(
            definition=SimpleNamespace(runtime_features=(panel,)))))
        result = add_bridges(SemanticMergeResult((), ()), (inventory,))
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].normalized_name, bridge_symbol('Hire', paired=True).casefold())
        with self.assertRaises(ValueError):
            add_bridges(result, (inventory,))

    def test_secondary_gate_uses_single_agent_integer_bridge(self):
        from majesty_cam.stock_controller_features import StockAp10Ap69SecondaryPanel
        panel = StockAp10Ap69SecondaryPanel('page', 'Forge', 'FP01', 'FRG', 31720,
                    required_level=3, eligibility_callback_symbol='Eligible')
        inventory = SimpleNamespace(selected=SimpleNamespace(package=SimpleNamespace(
            definition=SimpleNamespace(runtime_features=(panel,)))))
        result = add_bridges(SemanticMergeResult((), ()), (inventory,))
        self.assertEqual(result.items[0].text.strip(), bridge_source('Eligible').strip())


if __name__ == '__main__':
    unittest.main()
