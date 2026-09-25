from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.dataset_dependencies import (
    DatasetSymbols, close_dataset_dependencies, load_dataset_symbols,
    stock_dependency_paths,
)
from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from test_stock_gpl import _stock_game


def result(text):
    return SemanticMergeResult(parse_gpl(text, 'selected-mod').items, ())


def catalog(expressions='', base=(), functions=(), base_functions=(), helpers=''):
    items = parse_gpl(expressions, 'stock-expansion').items
    helper_items = {i.normalized_name: i for i in parse_gpl(helpers, 'stock-helpers').items}
    return DatasetSymbols(frozenset(base), {i.normalized_name: i for i in items},
                          frozenset(base_functions), frozenset(functions) | helper_items.keys(),
                          helper_items.__getitem__ if helpers else None)


class DatasetDependenciesTests(unittest.TestCase):
    def test_original_quest_item_comparison_gets_exact_stock_binding(self):
        original = result('function Item()\nbegin\nif (15 == #Bazaar_Item_One)\n'
                          'begin\nreturn;\nend\nend\n')
        fixed = close_dataset_dependencies(original, catalog(
            'expression #Bazaar_Item_One 20\nexpression #Unused 99\n'))
        self.assertEqual(fixed.items[0], original.items[0])
        self.assertEqual([i.name for i in fixed.items], ['Item', '#Bazaar_Item_One'])
        self.assertIn('20', fixed.items[-1].text)
        self.assertEqual(close_dataset_dependencies(fixed, catalog()), fixed)

    def test_closes_aliases_once_without_overriding_base_or_selected_values(self):
        stock = catalog('expression #A #B\nexpression #B 21\nexpression #Base 99\n',
                        base=('#base',))
        merged = close_dataset_dependencies(result(
            'expression #Owned 7\nfunction Item()\nbegin\n'
            'Result = #A + #a + #Base + #Owned;\nend\n'), stock)
        self.assertEqual([i.name for i in merged.items], ['#Owned', 'Item', '#B', '#A'])
        owned = result('expression #A 3\n')
        self.assertEqual(close_dataset_dependencies(owned, stock), owned)

    def test_comments_strings_and_external_bindings_do_not_create_dependencies(self):
        merged = result('function Item()\nbegin\n// #A $ExpansionOnly()\n'
                        '$DebugOut(1, "#A $ExpansionOnly");\n'
                        'Result = #ATTRIB_HP + #QuestLocal;\nend\n')
        self.assertEqual(close_dataset_dependencies(merged, catalog(
            'expression #A 20\n', functions=('expansiononly',))), merged)

    def test_missing_stock_source_is_rejected_and_supplied_functions_take_priority(self):
        stock = catalog(functions=('helper',))
        caller = result('function Item()\nbegin\n$Helper();\nend\n')
        with self.assertRaisesRegex(ValueError, r'selected-mod: Item: stock source for expansion-only function \$Helper'):
            close_dataset_dependencies(caller, stock)
        supplied = result('function Item()\nbegin\n$Helper();\nend\n'
                          'function Helper()\nbegin\nreturn;\nend\n')
        self.assertEqual(close_dataset_dependencies(supplied, stock), supplied)
        self.assertEqual(close_dataset_dependencies(caller, catalog(
            functions=('helper',), base_functions=('helper',))), caller)

    def test_transitive_helpers_callbacks_and_recursion_are_copied_exactly_once(self):
        stock = catalog('expression #Cost 21\n', helpers=(
            'function Helper()\nbegin\nResult = #Cost;\n$Next();\nend\n'
            'function Next()\nbegin\n$Helper();\nend\n'
            'function Unused()\nbegin\nreturn;\nend\n'))
        caller = result('function Item(agent unit)\nbegin\n'
                        'unit\'s "ActiveScript" = $Helper;\n$HELPER();\nend\n')
        linked = close_dataset_dependencies(caller, stock)
        self.assertEqual([i.name for i in linked.items], ['Item', '#Cost', 'Helper', 'Next'])
        self.assertEqual(linked.items[0], caller.items[0])
        self.assertEqual(linked.items[-2], stock.function_loader('helper'))
        self.assertEqual(linked.items[-1], stock.function_loader('next'))
        self.assertEqual(close_dataset_dependencies(linked, stock), linked)

    def test_closure_never_replaces_base_or_mod_functions_with_expansion_versions(self):
        stock = catalog(base_functions=('base',), helpers=(
            'function Helper()\nbegin\n$Base();\n$Owned();\nend\n'
            'function Base()\nbegin\n$Wrong();\nend\n'
            'function Owned()\nbegin\n$Wrong();\nend\n'
            'function Wrong()\nbegin\nreturn;\nend\n'))
        caller = result('function Item()\nbegin\n$Helper();\nend\n'
                        'function Owned()\nbegin\nreturn;\nend\n')
        linked = close_dataset_dependencies(caller, stock)
        self.assertEqual([i.name for i in linked.items], ['Item', 'Owned', 'Helper'])

    def test_rejects_cycles_and_function_valued_stock_expressions(self):
        caller = result('function Item()\nbegin\nResult = #A;\nend\n')
        for declarations, error in (
            ('expression #A #B\nexpression #B #A\n', 'cyclic'),
            ('expression #A $Something()\n', 'function evaluation'),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                close_dataset_dependencies(caller, catalog(declarations))

    def test_stock_base_includes_compatibility_project_and_source_edits_are_seen(self):
        with TemporaryDirectory() as tmp:
            game, _, sources = _stock_game(Path(tmp))
            sources[1].write_text('expression #Compatibility 4\n'
                                  'function Compatible()\nbegin\nreturn;\nend\n')
            sources[2].write_text('expression #Expansion 20\n')
            stock = load_dataset_symbols(game)
            self.assertIn('#compatibility', stock.base_expressions)
            self.assertIn('compatible', stock.base_functions)
            self.assertNotIn('#expansion', stock.base_expressions)
            self.assertIn('Result = 6', stock.function_loader('shared').text)
            sources[2].write_text('expression #Expansion 21\n')
            updated = load_dataset_symbols(game)
            self.assertIn('21', updated.expansion_expressions['#expansion'].text)
            paths = stock_dependency_paths(game)
            self.assertIn(sources[2].relative_to(game), paths)
            self.assertEqual(len(paths), len(set(paths)))


if __name__ == '__main__':
    unittest.main()
