from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from majesty_cam.gpl import parse_gpl, merge_sources
from majesty_cam.gpl_function_merge import FunctionMergeError, _Parser, merge_function
from majesty_cam.compose import compile_gpl


def function(body, name="Shared", argument="unit", declarations=""):
    return f"function {name}(agent {argument}) is boolean\ndeclare\n{declarations}\nbegin\n{body}\nend"


BASE = function('return FALSE;')
LEFT = function('if (unit\'s "Title" == "Alpha") begin $ActA(unit); return TRUE; end return FALSE;')
RIGHT = function('if (unit\'s "title" == "Beta") begin $ActB(unit); return TRUE; end return FALSE;')


class GuardMergeTests(unittest.TestCase):
    def test_disjoint_literals_keep_both_bodies_in_exclusive_dispatch(self):
        results = [merge_function(BASE, dict(order)) for order in permutations({'a': LEFT, 'b': RIGHT}.items())]
        self.assertEqual(results[0], results[1])
        nodes = _Parser(results[0]).function()[2]
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].body, _Parser(LEFT).function()[2][:1])
        self.assertEqual(nodes[0].otherwise[0].body, _Parser(RIGHT).function()[2][:1])
        self.assertEqual(nodes[-1].head, ('return', 'false', ';'))

    def test_nested_helper_rejection_guard_and_argument_mapping(self):
        helpers = {
            'attempt': function('if ($HasWayPoints(actor)) return FALSE; if ($eligible(actor)==FALSE) return FALSE; $Action(actor); return TRUE;', 'attempt', 'actor', 'list members;'),
            'eligible': function('if ($invalid(hero)) return FALSE; if (hero\'s "title" != "Beta") return FALSE; if ($OpaqueCheck(hero)) return FALSE; return TRUE;', 'eligible', 'hero'),
            'invalid': function('if ($IsValidGamePiece(who)==FALSE) begin $DebugOut("invalid"); return TRUE; end return FALSE;', 'invalid', 'who'),
        }
        right = function('if ($attempt(unit)) return TRUE; return FALSE;')
        merged = merge_function(BASE, {'a': LEFT, 'b': right}, function_lookup=helpers.get)
        self.assertIn('"Beta"', merged)
        self.assertIn('$attempt ( unit )', merged)
        self.assertNotIn('function eligible', merged)

    def test_conjoined_predicate_and_three_disjoint_types(self):
        a = LEFT.replace('"Alpha")', '"Alpha" && $Extra(unit))')
        c = RIGHT.replace('"Beta"', '"Gamma"').replace('$ActB', '$ActC')
        merged = merge_function(BASE, {'a': a, 'b': RIGHT, 'c': c})
        for name in ('$acta', '$actb', '$actc', '$extra'):
            self.assertEqual(merged.count(name), 1)

    def test_ambiguous_domains_do_not_merge(self):
        alternatives = [
            RIGHT.replace('"Beta"', '"Alpha"'),
            RIGHT.replace('"Beta"', '"alpha"'),
            RIGHT.replace('unit\'s "title"', 'other\'s "title"'),
            RIGHT.replace('"title"', '"subtype"'),
            RIGHT.replace('==', '!='),
            RIGHT.replace('"Beta")', '"Beta" || $Other(unit))'),
            RIGHT.replace('return FALSE;', '$Extra(unit); return FALSE;'),
            RIGHT.replace('end return', 'end else $Else(unit); return'),
            RIGHT.replace('"Beta"', '"B\\eta"'),
        ]
        for right in alternatives:
            with self.subTest(right=right), self.assertRaises(FunctionMergeError):
                merge_function(BASE, {'a': LEFT, 'b': right})

    def test_opaque_calls_writes_and_cycles_before_guard_do_not_prove_safety(self):
        right = function('if ($attempt(unit)) return TRUE; return FALSE;')
        for prefix in ('$Opaque(unit);', 'unit\'s "Title"="Beta";',
                       'if ($Opaque(unit)) return FALSE;',
                       'if (unit\'s "Callback"(unit)) return FALSE;',
                       'if (unit\'s "Counter" ++ > 0) return FALSE;',
                       'if ($HasWayPoints(unit)) return TRUE;',
                       'if ($attempt(unit)==FALSE) return FALSE;',
                       'if ($Unknown(unit)==FALSE) return FALSE;'):
            helper = function(prefix + ' if (unit\'s "title"!="Beta") return FALSE; return TRUE;', 'attempt')
            with self.subTest(prefix=prefix), self.assertRaises(FunctionMergeError):
                merge_function(BASE, {'a': LEFT, 'b': right}, function_lookup={'attempt': helper}.get)

    def test_different_helper_definitions_never_borrow_a_guard_from_one_owner(self):
        right = function('if ($attempt(unit)) return TRUE; return FALSE;')
        ahelper = function('if (unit\'s "Title"!="Beta") return FALSE; return TRUE;', 'attempt')
        bhelper = ahelper.replace('"Beta"', '"Alpha"')
        result = merge_sources([parse_gpl(BASE)], {
            'a': [parse_gpl(LEFT), parse_gpl(ahelper)],
            'b': [parse_gpl(right), parse_gpl(bhelper)],
        })
        self.assertIn('shared', {c.key[1] for c in result.conflicts})

    def test_selected_override_of_query_is_not_assumed_readonly(self):
        helper = function('if ($HasWayPoints(unit)) return FALSE; if (unit\'s "Title"!="Beta") return FALSE; return TRUE;', 'attempt')
        unsafe_query = function('$ChangeSomething(unit); return FALSE;', 'HasWayPoints')
        right = function('if ($attempt(unit)) return TRUE; return FALSE;')
        with self.assertRaises(FunctionMergeError):
            merge_function(BASE, {'a': LEFT, 'b': right}, function_lookup={
                'attempt': helper, 'haswaypoints': unsafe_query}.get)

    def test_stock_helper_lookup_is_lazy_and_not_emitted(self):
        helper = function('if ($validity(unit)) return FALSE; if (unit\'s "Title"!="Beta") return FALSE; return TRUE;', 'attempt')
        validity = parse_gpl(function('if ($IsValidGamePiece(unit)==FALSE) return TRUE; return FALSE;', 'validity')).items[0]
        loader = Mock(return_value={validity.key: validity})
        right = function('if ($attempt(unit)) return TRUE; return FALSE;')
        result = merge_sources([parse_gpl(BASE)], {'a': [parse_gpl(LEFT)],
                              'b': [parse_gpl(right), parse_gpl(helper)]}, function_loader=loader)
        self.assertFalse(result.conflicts)
        loader.assert_called_once_with(('validity',))
        self.assertNotIn('validity', {i.normalized_name for i in result.items})
        loader.reset_mock()
        merge_function(BASE, {'a': LEFT, 'b': RIGHT}, function_lookup=loader)
        loader.assert_not_called()

    def test_helper_budget_fails_closed(self):
        helpers = {f'h{i}': function(f'if ($h{i+1}(unit)==FALSE) return FALSE; return TRUE;', f'h{i}') for i in range(40)}
        right = function('if ($h0(unit)) return TRUE; return FALSE;')
        with self.assertRaises(FunctionMergeError):
            merge_function(BASE, {'a': LEFT, 'b': right}, function_lookup=helpers.get)

    def test_helper_only_predicates_do_not_hoist_a_new_property_access(self):
        helpers = {name: function(f'if ($IsValidGamePiece(unit)==FALSE) return FALSE; if (unit\'s "Title"!="{title}") return FALSE; return TRUE;', name)
                   for name, title in [('one', 'Alpha'), ('two', 'Beta')]}
        with self.assertRaises(FunctionMergeError):
            merge_function(BASE, {'a': function('if ($one(unit)) return TRUE; return FALSE;'),
                                  'b': function('if ($two(unit)) return TRUE; return FALSE;')},
                           function_lookup=helpers.get)

    def test_nested_conflict_keeps_stock_fallback_and_waypoint_gate(self):
        base = function('if ($HasWayPoints(unit)==FALSE) begin return FALSE; end')
        # Insert each complete branch inside the stock outer gate.
        left = base.replace('return FALSE;', 'if (unit\'s "Title"=="Alpha") return TRUE; return FALSE;')
        right = base.replace('return FALSE;', 'if (unit\'s "Title"=="Beta") return TRUE; return FALSE;')
        nodes = _Parser(merge_function(base, {'a': left, 'b': right})).function()[2]
        self.assertEqual(nodes[0].head, _Parser(base).function()[2][0].head)
        self.assertEqual(nodes[0].body[-1].head, ('return', 'false', ';'))

    @unittest.skipUnless(Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Gplbcc.exe').is_file(), 'installed compiler unavailable')
    def test_exclusive_dispatch_compiles_in_temporary_language_fixture(self):
        merged = merge_function(BASE, {'a': LEFT, 'b': RIGHT})
        result = merge_sources([], {'fixture': [parse_gpl(merged)]})
        with TemporaryDirectory(prefix='gpl-guard-fixture-') as tmp:
            compile_gpl(result.emit_project_source_set('Fixture.gpl', 'Fixture.dat'),
                        Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Gplbcc.exe'),
                        Path(tmp) / 'compiler', stem='Fixture')


if __name__ == '__main__':
    unittest.main()
