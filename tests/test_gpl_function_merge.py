from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import os
from unittest.mock import Mock, patch

from majesty_cam.gpl import (DefinitionKind, SemanticItem, SemanticMergeResult, merge_sources,
                             parse_gpl, require_complete_semantic_coverage)
from majesty_cam.gpl_function_merge import FunctionMergeError, _Parser, merge_function
from majesty_cam.compose import ComposeError, compile_gpl, merge_gpl_resources


def function(body, locals="integer a,b,c;", signature="function Shared(agent unit)"):
    return f"{signature}\ndeclare\n{locals}\nbegin\n{body}\nend\n"


def structure(text):
    return _Parser(text).function()


class InstructionMergeTests(unittest.TestCase):
    def merged(self, base, sides, expected):
        for order in permutations(sides.items()):
            result = merge_function(base, dict(order))
            self.assertEqual(structure(result), structure(expected))
            require_complete_semantic_coverage(parse_gpl(result))

    def test_independent_statements_n_way_and_duplicate_edit(self):
        base = function('a=1; b=2; c=3;')
        self.merged(base, {'one':base.replace('a=1', 'a=10'),
                           'two':base.replace('b=2', 'b=20'),
                           'same':base.replace('a=1', 'a=10'),
                           'three':base.replace('c=3', 'c=30')},
                    function('a=10; b=20; c=30;'))

    def test_stock_copy_comments_case_and_line_endings_do_not_compete(self):
        base = function('a=1; b=2;')
        self.merged(base, {'changed':base.replace('a=1','a=7'),
                           'format':base.upper().replace(';', '; // comment\r\n')},
                    base.replace('a=1','a=7'))

    def test_changed_condition_and_added_branch_instruction(self):
        base = function('a=1; if ($Check(unit)) a=0; if (a==1) $Death(unit);')
        capture = base.replace('$Check', '$CustomCheck')
        credit = base.replace('a=0;', 'begin a=0; $Credit(unit); end')
        self.merged(base, {'capture':capture, 'credit':credit},
                    credit.replace('$Check', '$CustomCheck'))

    def test_else_if_and_redundant_blocks_are_equivalent(self):
        base = function('if (a) begin if (b) a=1; else a=2; end else c=3;')
        left = function('if(a) if(b) a=10; else a=2; else c=3;')
        right = base.replace('c=3', 'c=30')
        self.merged(base, {'left':left,'right':right}, base.replace('a=1','a=10').replace('c=3','c=30'))

    def test_do_not_steal_dangling_else(self):
        base = function('if(a) a=1; else a=2; b=3;')
        left = base.replace('a=1;', 'begin if(c) a=1; end')
        right = base.replace('b=3','b=30')
        self.merged(base, {'left':left,'right':right},left.replace('b=3','b=30'))

    def test_foreach_while_preserve_body_ownership(self):
        base = function('foreach unit in members do begin a=1; b=2; end while (c) do c=0;', 'integer a,b,c; list members;')
        self.merged(base, {'left':base.replace('a=1','a=5'), 'right':base.replace('b=2','b=7')},
                    base.replace('a=1','a=5').replace('b=2','b=7'))

    def test_declared_locals_merge_by_name_not_comma_position(self):
        base = function('a=1; b=2;', 'integer a,b;')
        left = function('a=1; b=2; x=3;', 'integer a,b,x;')
        right = function('z=$LocationOf(unit); a=1; b=2;', 'integer b,a; location z;')
        self.merged(base, {'left':left,'right':right},
                    function('z=$LocationOf(unit); a=1; b=2; x=3;', 'integer a,b,x; location z;'))

    def test_strings_operators_possessive_and_comments_are_preserved(self):
        base = function('a=1; unit\'s "Type"="SomeCase//notComment"; b=2;')
        self.merged(base, {'one':base.replace('a=1','a+=1'), 'two':base.replace('b=2','b<<2')},
                    base.replace('a=1','a+=1').replace('b=2','b<<2'))

    def test_stock_replacement_with_prefix_guard_preserves_early_return(self):
        base = function('a=1; b=2; $Death(unit); $Cleanup(unit);')
        left = function('if ($Revive(unit)) return; a=9; $Death(unit); $Cleanup(unit);')
        right = base.replace('$Death(unit);', '$Credit(unit); $Death(unit);')
        self.merged(base, {'left':left,'right':right},left.replace('$Death(unit);','$Credit(unit); $Death(unit);'))

    def test_identical_insertions_run_once(self):
        base = function('a=1; b=2; c=3;')
        left = base.replace('a=1;', '$Extra(unit); a=10;')
        right = base.replace('a=1;', '$Extra(unit); a=1;').replace('c=3','c=30')
        self.merged(base, {'left':left,'right':right},left.replace('c=3','c=30'))

    def test_competing_statement_edits_are_not_token_spliced(self):
        base = function('a=1; b=2;')
        cases = [
            (base.replace('a=1','a=5'),base.replace('a=1','a=7')),
            (base.replace('a=1','a+=1'),base.replace('a=1','a=7')),
            (base.replace('a=1;', ''),base.replace('a=1','a=7')),
            (base.replace('a=1;', '$Left(unit); a=1;'),base.replace('a=1;', '$Right(unit); a=1;')),
            (base.replace('integer a,b,c;', 'string a; integer b,c;'),base.replace('integer a,b,c;', 'agent a; integer b,c;')),
        ]
        for left,right in cases:
            with self.subTest(left=left,right=right), self.assertRaisesRegex(FunctionMergeError,'competing edits'):
                merge_function(base,{'Left Mod':left,'Right Mod':right})

    def test_conflicting_condition_and_removed_branch(self):
        base = function('if (a) b=1; else b=2; c=3;')
        with self.assertRaisesRegex(FunctionMergeError,'condition'):
            merge_function(base, {'one':base.replace('if (a)','if (b)'), 'two':base.replace('if (a)','if (c)')})
        with self.assertRaises(FunctionMergeError):
            merge_function(base, {'one':base.replace('if (a) b=1; else b=2;', ''), 'two':base.replace('b=1','b=10')})

    def test_reorder_and_repeated_anchor_ambiguity_are_not_guessed(self):
        for original, left in [('a=1; b=2;', 'b=2; a=1;'),
                               ('$Step(unit); $Step(unit); b=2;', '$Step(unit); b=2;')]:
            base=function(original)
            with self.subTest(original=original), self.assertRaisesRegex(FunctionMergeError,'reordered|ambiguous'):
                merge_function(base, {'one':function(left), 'two':base.replace('b=2','b=5')})

    def test_signature_change_with_body_edit_is_blocked(self):
        base = function('a=1;')
        with self.assertRaisesRegex(FunctionMergeError, 'signature'):
            merge_function(base, {'one':base.replace('agent unit','integer unit'), 'two':base.replace('a=1','a=2')})

    def test_string_value_case_is_not_normalized(self):
        base = function('unit\'s "Value"="Base";')
        with self.assertRaises(FunctionMergeError):
            merge_function(base, {'one':base.replace('"Base"','"Value"'), 'two':base.replace('"Base"','"value"')})

    def test_supplemental_ancestor_is_not_emitted_and_explicit_wins(self):
        base = parse_gpl(function('a=1; b=2;'))
        left = parse_gpl(function('a=10; b=2;'))
        right = parse_gpl(function('a=1; b=20;'))
        unrelated = parse_gpl(function('return;', signature='function Unselected()')).items[0]
        ancestors={item.key:item for item in (*base.items,unrelated)}
        merged=merge_sources([],{'left':[left],'right':[right]},function_ancestors=ancestors)
        self.assertEqual(len(merged.items),1)
        self.assertEqual(structure(merged.items[0].text),structure(function('a=10; b=20;')))
        explicit=SemanticItem.resolved('function','Shared',function('return;'))
        resolved=merge_sources([],{'left':[left],'right':[right]}, {explicit.key:explicit},function_ancestors=ancestors)
        self.assertEqual(resolved.items,(explicit,))

    def test_different_new_functions_without_stock_remain_blocked(self):
        result=merge_sources([],{'left':[parse_gpl(function('a=1;'))],
                                 'right':[parse_gpl(function('a=2;'))]})
        self.assertIn('no common stock',result.conflicts[0].detail)


class InstructionComposeTests(unittest.TestCase):
    def run_merge(self, sources, loader, **kwargs):
        inventories=tuple(SimpleNamespace(selected=SimpleNamespace(alias=owner)) for owner in sources)
        with patch('majesty_cam.compose._parse_inventory_gpl_sources',
                   side_effect=lambda inv:[parse_gpl(sources[inv.selected.alias])]):
            return merge_gpl_resources(inventories,stock_function_loader=loader,**kwargs)

    def test_lazy_lookup_and_auto_resolution_reporting(self):
        base=parse_gpl(function('a=1; b=2;')).items[0]
        loader=Mock(return_value={base.key:base})
        result=self.run_merge({'one':function('a=10; b=2;'),'two':function('a=1; b=20;')},loader)
        loader.assert_called_once_with(('Shared',))
        self.assertEqual(result.function_instruction_merges[0]['function'],'Shared')
        self.assertEqual(result.function_instruction_merges[0]['owners'],['one','two'])
        self.assertEqual(result.resolution_sources,())
        self.assertEqual(structure(result.source_set.gpl_text),structure(function('a=10; b=20;')))

    def test_no_stock_lookup_when_unneeded_or_explicitly_resolved(self):
        for sources in ({'one':function('a=1;')}, {'one':function('a=1;'),'two':function('a=1;')}):
            loader=Mock(side_effect=AssertionError('unnecessary lookup'))
            self.run_merge(sources,loader)
            loader.assert_not_called()
        loader=Mock(side_effect=AssertionError('unnecessary lookup'))
        self.run_merge({'one':function('a=1;'),'two':function('a=2;')},loader,
                       resolution_owners={(DefinitionKind.FUNCTION,'Shared'):'two'})
        loader.assert_not_called()

    def test_use_available_stock_without_loading_again(self):
        loader=Mock(side_effect=AssertionError('unnecessary lookup'))
        self.run_merge({'one':function('a=5; b=2;'),'two':function('a=1; b=7;')},loader,
                       stock_semantic_sources=(parse_gpl(function('a=1; b=2;')),))
        loader.assert_not_called()

    def test_competing_changes_explain_function_mods_and_instruction(self):
        base=parse_gpl(function('a=1;')).items[0]
        with self.assertRaisesRegex(ComposeError,'(?s)Shared.*one.*two.*a = 5.*a = 7'):
            self.run_merge({'one':function('a=5;'),'two':function('a=7;')},Mock(return_value={base.key:base}))


GAME=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD')


@unittest.skipUnless((GAME/'SDK/Gplbcc.exe').is_file(), 'installed GPL compiler not available')
class InstructionCompilerTests(unittest.TestCase):
    def test_rendered_control_flow_compiles_in_disposable_fixture(self):
        base=function('a=1; if (a==1) b=2; else b=3; while (b>0) do b-=1;', 'integer a,b;')
        left=base.replace('a=1;', 'unit\'s "Value"="Case"; a=1;')
        right=base.replace('b=2;', 'begin b=20; a+=1; end')
        merged=merge_sources([parse_gpl(base)],{'left':[parse_gpl(left)],'right':[parse_gpl(right)]})
        with TemporaryDirectory(prefix='gpl-instruction-fixture-') as tmp:
            compile_gpl(merged.emit_project_source_set('Fixture.gpl','Fixture.dat'),
                        GAME/'SDK/Gplbcc.exe',Path(tmp)/'compiler',stem='Fixture')

    @unittest.skipUnless(os.environ.get('MAJESTY_GPL_MERGE_INTEGRATION') == '1', 'local source integration is opt-in')
    def test_reported_installed_function_fragments(self):
        # Read installed inputs, compose eight isolated functions in memory,
        # and compile a temporary language fixture. Never build a mod/profile.
        from majesty_cam.stock_gpl import load_stock_function_ancestors
        names=('Drain_Life_Hit','attack_object','travel_to_safe','Guild_Title',
               'Purchase_Equipment','damage','gravestone','monster_gravestone')
        ancestors=load_stock_function_ancestors(GAME,names)
        roots={
            'haunt':Path(__file__).resolve().parents[1]/'payload/mods/CustomGuildPhantomsHauntExpanded/GPL',
            'bards':Path(r'C:\Users\bterr\Documents\My Games\MajestyHD\Mods\CustomGuildBards\GPL'),
            'alchemy':GAME.parents[1]/'workshop/content/73230/3793509198/GPL',
            'zoo':GAME.parents[1]/'workshop/content/73230/3796459696/GPL',
        }
        expressions={}
        for path in (GAME/'SDK/OriginalQuests/GPL/defines.gpl',GAME/'SDK/OriginalQuests/GPLMx/mx_defines.gpl'):
            for item in parse_gpl(path.read_text(encoding='cp1252')).items:
                if item.kind is DefinitionKind.EXPRESSION: expressions[item.key]=item
        variants={key:{} for key in ancestors}
        for owner,root in roots.items():
            self.assertTrue(root.is_dir(),root)
            for path in root.rglob('*.gpl'):
                for item in parse_gpl(path.read_text(encoding='cp1252'),str(path)).items:
                    if item.key in variants: variants[item.key][owner]=item.text
                    if item.kind is DefinitionKind.EXPRESSION: expressions[item.key]=item
        output=[]
        for key,base in ancestors.items():
            sides=variants[key]
            self.assertGreaterEqual(len(sides),2,key)
            merged=merge_function(base.text,sides)
            self.assertEqual(merged,merge_function(base.text,dict(reversed(list(sides.items())))))
            output.extend(parse_gpl(merged).items)
        fixture=SemanticMergeResult((*expressions.values(),*output),())
        with TemporaryDirectory(prefix='reported-functions-fixture-') as tmp:
            compile_gpl(fixture.emit_project_source_set('Fixture.gpl','Fixture.dat'),
                        GAME/'SDK/Gplbcc.exe',Path(tmp)/'compiler',stem='Fixture')


if __name__=='__main__':
    unittest.main()
