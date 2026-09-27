from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import os
from unittest.mock import Mock, patch

from majesty_cam.gpl import (DefinitionKind, SemanticItem, SemanticMergeResult, merge_sources,
                             parse_gpl, require_complete_semantic_coverage)
from majesty_cam.gpl_function_merge import (
    FunctionMergeError, _Node, _Parser, _tokens, merge_function, same_function_instructions,
)
from majesty_cam.compose import ComposeError, compile_gpl, merge_gpl_resources


def function(body, locals="integer a,b,c;", signature="function Shared(agent unit)"):
    return f"{signature}\ndeclare\n{locals}\nbegin\n{body}\nend\n"


def structure(text):
    return _Parser(text).function()


def decision(order, tail='a=1; b=2;'):
    return function(' '.join(f'if (${name}(unit) == False)' for name in order) + ' begin ' + tail + ' end')


class InstructionMergeTests(unittest.TestCase):
    def test_stock_postfix_operators_survive_rendered_merge_as_single_tokens(self):
        base = function('a=1; b=2; (unit\'s "Count")++; (unit\'s "Other")--;')
        merged = merge_function(base, {
            'first': base.replace('a=1;', 'a=3;'),
            'second': base.replace('b=2;', 'b=4;'),
        })
        self.assertEqual(_tokens(merged).count('++'), 1)
        self.assertEqual(_tokens(merged).count('--'), 1)
        self.assertNotIn('+ +', merged)
        self.assertNotIn('- -', merged)
        self.assertNotEqual(_tokens('value++;'), _tokens('value + +;'))
        self.assertNotEqual(_tokens('value--;'), _tokens('value - -;'))
        self.assertEqual(structure(merged), structure(base.replace('a=1;', 'a=3;').replace('b=2;', 'b=4;')))

    def test_exact_function_proof_ignores_only_layout(self):
        source = function('if (a) if(b) $Keep(unit, "Value"); else $Other(unit);')
        explicit = function('if (a) begin if(b) begin $Keep(unit, "Value"); end else begin $Other(unit); end end')
        self.assertTrue(same_function_instructions(source, explicit))
        for changed in (
            function('if (a) begin if(b) $Keep(unit, "Value"); end else $Other(unit);'),
            source.replace('"Value"', '"value"'),
            source.replace('if (a)', 'if (a==True)'),
            source.replace('$Keep(unit', '$Replacement(unit'),
            source.replace('integer a,b,c;', 'integer a,b; boolean c;'),
            source.replace('function Shared', 'function Other'),
            source.replace('if (a)', 'while (a) do'),
        ):
            with self.subTest(changed=changed):
                self.assertFalse(same_function_instructions(source, changed))

    def test_exact_function_proof_fails_closed_on_unsupported_difference(self):
        opaque = 'function Opaque() declare integer a=1; begin return; end'
        self.assertTrue(same_function_instructions(opaque, opaque + '// identical instructions'))
        self.assertFalse(same_function_instructions(opaque, opaque.replace('return;', 'begin return; end')))

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

    def test_return_else_and_fallthrough_keep_independent_edits(self):
        base = function('a=1; if ($Blocked(unit)) return; else begin b=2; c=3; end $Finish(unit);')
        flat = function('a=1; if ($Blocked(unit)) return; b=20; c=3; $Finish(unit);')
        self.merged(base, {'flat':flat, 'branch':base.replace('c=3','c=30'),
                           'prefix':base.replace('a=1','a=10'), 'unchanged':base},
                    flat.replace('c=3','c=30').replace('a=1','a=10'))

    def test_return_fallthrough_can_gain_else_without_losing_edits(self):
        base = function('if (a) return; b=2; c=3;')
        self.merged(base, {'branch':function('if(a) return; else b=20; c=3;'),
                           'tail':base.replace('c=3','c=30')},
                    base.replace('b=2','b=20').replace('c=3','c=30'))

    def test_return_alignment_preserves_enclosing_loop_and_outer_else(self):
        original = 'if (b) begin $Observe(unit); return $Stop(unit); end else begin a=1; c=3; end'
        flat = 'if (b) begin $Observe(unit); return $Stop(unit); end a=1; c=30;'
        for wrapper in ('while (a) do begin %s $Finish(unit); end',
                        'if (a) begin %s $Finish(unit); end else $Outer(unit);'):
            base = function(wrapper % original)
            self.merged(base, {'layout':function(wrapper % flat),
                               'edit':base.replace('a=1','a=10')},
                        function(wrapper % flat.replace('a=1','a=10')))

    def test_return_alignment_retains_real_deletion_conflicts(self):
        base = function('if(a) return; else begin b=2; c=3; end $Finish(unit);')
        removed = function('if(a) return; c=3; $Finish(unit);')
        with self.assertRaises(FunctionMergeError):
            merge_function(base, {'remove':removed, 'edit':base.replace('b=2','b=20')})

    def test_return_alignment_keeps_return_expression_conflicts(self):
        base = function('if(a) return 1; else b=2; c=3;')
        flat = function('if(a) return 2; b=2; c=3;')
        with self.assertRaisesRegex(FunctionMergeError, 'competing edits'):
            merge_function(base, {'flat':flat, 'other':base.replace('return 1', 'return 3')})

    def test_return_alignment_keeps_work_before_return_and_after_else(self):
        base = function('if(a) begin $Observe(unit); return $Stop(unit); end else b=2; $Finish(unit);')
        flat = function('if(a) begin $Observe(unit); return $Stop(unit); end b=20; $Finish(unit);')
        self.merged(base, {'flat':flat, 'true_path':base.replace('$Observe(unit);', '$Observe(unit); c=3;'),
                           'tail':base.replace('$Finish(unit);', '$Finish(unit); $Cleanup(unit);')},
                    flat.replace('$Observe(unit);', '$Observe(unit); c=3;')
                        .replace('$Finish(unit);', '$Finish(unit); $Cleanup(unit);'))

    def test_return_alignment_cannot_hide_changed_termination(self):
        from majesty_cam.gpl_function_merge import _align_return_fallthrough
        base = function('if(a) return; else begin b=2; c=3; end $Finish(unit);')
        flat = function('if(a) return; b=20; c=3; $Finish(unit);')
        for replacement in ('$Observe(unit);', 'if(c) return;',
                            'while (c) do return;', '$Exit(unit);', 'break;', 'continue;'):
            changed = base.replace('return;', replacement)
            bodies = [('flat', structure(flat)[2]), ('changed', structure(changed)[2])]
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(FunctionMergeError, 'incompatible termination'):
                    _align_return_fallthrough(structure(base)[2], bodies)
                with self.assertRaisesRegex(FunctionMergeError, 'incompatible termination'):
                    merge_function(base, {'flat':flat, 'changed':changed})

    def test_return_alignment_requires_unique_unchanged_guard_identity(self):
        from majesty_cam.gpl_function_merge import _align_return_fallthrough
        base = function('if(a) return; else b=2; c=3;')
        flat = function('if(a) return; b=20; c=3;')
        for change in (base.replace('if(a)', 'if(b)'),
                       base.replace('c=3;', 'if(a) return; c=3;'),
                       function('b=2; c=3;')):
            bodies = [('flat', structure(flat)[2]), ('changed', structure(change)[2])]
            self.assertEqual(_align_return_fallthrough(structure(base)[2], bodies),
                             (structure(base)[2], bodies))

    def test_return_alignment_does_not_rewrite_matching_layouts(self):
        base = function('if(a) return; else begin b=2; c=3; end')
        self.merged(base, {'one':base.replace('b=2','b=20'),
                           'two':base.replace('c=3','c=30')},
                    base.replace('b=2','b=20').replace('c=3','c=30'))

    def test_declared_locals_merge_by_name_not_comma_position(self):
        base = function('a=1; b=2;', 'integer a,b;')
        left = function('a=1; b=2; x=3;', 'integer a,b,x;')
        right = function('z=$LocationOf(unit); a=1; b=2;', 'integer b,a; location z;')
        self.merged(base, {'left':left,'right':right},
                    function('z=$LocationOf(unit); a=1; b=2; x=3;', 'integer a,b,x; location z;'))

    def test_independently_added_same_local_cannot_share_storage(self):
        base = function('a=1; b=2; c=3;')
        sides = {'first':function('a=1; saved=a; b=2; c=3; $First(saved);',
                                  'integer a,b,c,saved;'),
                 'second':function('a=1; b=2; SAVED=b; $Second(SAVED); c=3;',
                                   'integer a,b,c,SAVED;')}
        for order in permutations(sides.items()):
            with self.assertRaisesRegex(FunctionMergeError, 'local saved: independently introduced.*explicit resolution'):
                merge_function(base, dict(order))

    def test_identical_added_local_variant_is_not_independent_ownership(self):
        base = function('a=1; b=2; c=3;')
        added = function('a=1; saved=a; b=2; c=3; $First(saved);', 'integer a,b,c,saved;')
        self.merged(base, {'first':added, 'duplicate':added, 'stock':base,
                           'other':base.replace('c=3','c=30')},
                    added.replace('c=3','c=30'))

    def test_preexisting_local_remains_shared_by_the_stock_contract(self):
        base = function('a=1; saved=a; b=2; c=3; $First(saved);', 'integer a,b,c,saved;')
        self.merged(base, {'first':base.replace('saved=a','saved=b'),
                           'second':base.replace('c=3','c=30')},
                    base.replace('saved=a','saved=b').replace('c=3','c=30'))

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

    def test_moved_and_edited_sibling_branches_are_not_paired_by_position(self):
        base = function('if(a==1) $Act(); if(b==1) $Act();')
        sides = {'reordered':function('if(b==2) $Act(); if(a==2) $Act();'),
                 'body':function('if(a==1) $Different(); if(b==1) $Act();')}
        for order in permutations(sides.items()):
            with self.assertRaisesRegex(FunctionMergeError, 'ambiguous branch identity.*explicit resolution'):
                merge_function(base, dict(order))

    def test_ambiguous_repeated_branch_heads_do_not_identify_body_edits(self):
        base = function('if(a) $First(); if(a) $Second();')
        sides = {'rewritten':function('if(a) $SecondChanged(); if(a) $FirstChanged();'),
                 'other':function('if(a) begin $First(); $Credit(); end if(a) $Second();')}
        with self.assertRaisesRegex(FunctionMergeError, 'ambiguous branch identity'):
            merge_function(base, sides)

    def test_unique_sibling_branch_heads_keep_body_edit_ownership(self):
        base = function('if(a) begin a=1; b=2; end if(b) begin a=1; b=2; end')
        self.merged(base, {'first':base.replace('a=1','a=10'),
                           'second':base.replace('b=2','b=20')},
                    base.replace('a=1','a=10').replace('b=2','b=20'))

    def test_one_condition_replacement_bounded_by_unique_identity_is_allowed(self):
        base = function('if(a) begin a=1; b=2; end if(b) c=3;')
        self.merged(base, {'conditions':base.replace('if(a)','if(c)').replace('c=3','c=30'),
                           'body':base.replace('b=2','b=20')},
                    base.replace('if(a)','if(c)').replace('c=3','c=30').replace('b=2','b=20'))

    def test_literal_whole_region_replacement_does_not_guess_branch_identity(self):
        base = function('if(a==1) $Act(); if(b==1) $Act(); c=3;')
        rewritten = function('if(b==2) $Act(); if(a==2) $Act(); c=3;')
        self.merged(base, {'first':rewritten, 'duplicate':rewritten,
                           'other':base.replace('c=3','c=30')},
                    rewritten.replace('c=3','c=30'))

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

    def test_decision_chain_reordering_with_independent_insertion_replacement_and_tail_edit(self):
        base = decision(('A','B','C','D','E','F'))
        self.merged(base, {'priority':decision(('A','B','E','C','D','F')),
                           'custom':decision(('A','X','B','PrivateC','D','E','F'), 'a=1; b=20;')},
                    decision(('A','X','B','E','PrivateC','D','F'), 'a=1; b=20;'))

    def test_edited_decision_moves_with_its_original_identity(self):
        base = decision(('A','B','C','D','E','F'))
        self.merged(base, {'priority':decision(('A','B','E','C','D','F')),
                           'changed':decision(('A','B','C','D','PrivateE','F'))},
                    decision(('A','B','PrivateE','C','D','F')))

    def test_decision_chain_distinct_gaps_and_identical_insertions(self):
        base = decision(('A','B','C','D'))
        self.merged(base, {'one':decision(('X','A','B','C','D')),
                           'same':decision(('X','A','B','C','D'), 'a=10; b=2;'),
                           'two':decision(('A','B','C','D','Y'), 'a=1; b=20;')},
                    decision(('X','A','B','C','D','Y'), 'a=10; b=20;'))

    def test_same_explicit_decision_order_is_not_a_conflict(self):
        base = decision(('A','B','C','D'))
        self.merged(base, {'one':decision(('A','C','B','D'), 'a=10; b=2;'),
                           'two':decision(('A','C','B','D'), 'a=1; b=20;')},
                    decision(('A','C','B','D'), 'a=10; b=20;'))

    def test_decision_chain_keeps_one_short_circuit_gate_for_each_check(self):
        from majesty_cam.gpl_function_merge import _guard_chain
        merged = merge_function(decision(('A','B','C','D')),
            {'priority':decision(('A','C','B','D')),
             'addition':decision(('A','B','C','D','X'))})
        heads, tail = _guard_chain(structure(merged)[2][0])
        calls = [head[2] for head in heads]
        self.assertEqual(calls, ['$a','$c','$b','$d','$x'])
        self.assertEqual(tail, structure(function('a=1; b=2;'))[2])
        # Literal nested ifs preserve the same stop point for every outcome;
        # no boolean-expression reordering or extra callback invocation.
        for stop in range(len(calls) + 1):
            node = structure(merged)[2][0]
            seen = []
            while node.kind == 'if':
                self.assertEqual(node.otherwise, ())
                seen.append(node.head[2])
                if len(seen) == stop + 1:
                    break
                node = node.body[0]
            self.assertEqual(seen, calls[:stop + 1])

    def test_ambiguous_or_competing_decision_edits_remain_conflicts(self):
        base = decision(('A','B','C','D','E'))
        cases = (
            (('A','X','B','C','D','E'), ('A','Y','B','C','D','E'), 'insertion gap'),
            (('A','C','B','D','E'), ('A','B','D','C','E'), 'priority'),
            (('A','B','PrivateC','D','E'), ('A','B','OtherC','D','E'), 'condition'),
            (('A','X','B','C','D','E'), ('A','C','B','D','E'), 'anchors were moved'),
            (('A','X','B','C','D','E'), ('A','B','C','X','D','E'), 'duplicated'),
            (('A','B','C','E'), ('A','B','C','PrivateD','E'), 'removed or ambiguously'),
            (('A','X','Y','D','E'), ('A','B','C','D','E','Z'), 'removed or ambiguously'),
            (('A','B','B','C','D','E'), ('A','B','C','D','E','Z'), 'repeated/ambiguous'),
        )
        for left, right, error in cases:
            with self.subTest(left=left, right=right), self.assertRaisesRegex(FunctionMergeError, error):
                merge_function(base, {'one':decision(left), 'two':decision(right)})

    def test_repeated_unchanged_decision_guards_allow_independent_tail_edits(self):
        base = decision(('A','A','B'))
        self.merged(base, {'one':decision(('A','A','B'), 'a=10; b=2;'),
                           'two':decision(('A','A','B'), 'a=1; b=20;')},
                    decision(('A','A','B'), 'a=10; b=20;'))

    def test_same_shape_condition_edits_keep_existing_structural_merge(self):
        base = decision(('A','B','C','D'))
        self.merged(base, {'conditions':decision(('A','PrivateB','PrivateC','D')),
                           'body':decision(('A','B','C','D'), 'a=10; b=2;')},
                    decision(('A','PrivateB','PrivateC','D'), 'a=10; b=2;'))


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

    def test_destination_stock_is_not_used_as_authored_source_ancestry(self):
        base = parse_gpl(function('a=1; b=2;')).items[0]
        sdk = parse_gpl(function('a=1; $StockAddition(); b=2;')).items[0]
        sources = {'one': function('a=1; $One(); $StockAddition(); b=2;'),
                   'two': function('a=1; $StockAddition(); $Two(); b=2;')}
        with self.assertRaisesRegex(ComposeError, 'competing edits'):
            self.run_merge(sources, Mock(return_value={base.key: base}))
        destination = Mock(side_effect=AssertionError('destination used for authored comparison'))
        ancestry = Mock(return_value={sdk.key: sdk})
        merged = self.run_merge(sources, destination, source_ancestor_loader=ancestry)
        ancestry.assert_called_once_with(('Shared',))
        destination.assert_not_called()
        self.assertEqual(structure(merged.source_set.gpl_text),
                         structure(function('a=1; $One(); $StockAddition(); $Two(); b=2;')))

    def test_correct_source_ancestry_does_not_hide_real_competing_edits(self):
        sdk = parse_gpl(function('a=1; $StockAddition(); b=2;')).items[0]
        with self.assertRaisesRegex(ComposeError, 'competing edits'):
            self.run_merge({'one': function('a=10; $StockAddition(); b=2;'),
                            'two': function('a=20; $StockAddition(); b=2;')},
                           Mock(), source_ancestor_loader=Mock(return_value={sdk.key: sdk}))

    def test_competing_changes_explain_function_mods_and_instruction(self):
        base=parse_gpl(function('a=1;')).items[0]
        with self.assertRaisesRegex(ComposeError,'(?s)Shared.*one.*two.*a = 5.*a = 7'):
            self.run_merge({'one':function('a=5;'),'two':function('a=7;')},Mock(return_value={base.key:base}))


GAME=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD')


@unittest.skipUnless((GAME/'SDK/Gplbcc.exe').is_file(), 'installed GPL compiler not available')
class InstructionCompilerTests(unittest.TestCase):
    def test_reported_potion_function_in_both_dataset_views(self):
        # Reconcile only this function and compile a disposable language fixture.
        # This must never publish or prepare the user's merged profile.
        from majesty_cam.standard_scripts import Providers
        from test_standard_scripts import provider
        native_path = GAME.parents[1]/'workshop/content/73230/1965892371/GPL/Vitality.gpl'
        authored_path = Path(__file__).resolve().parents[1]/'payload/mods/CustomGuildPhantomsHauntExpanded/GPL/Phantom.gpl'
        if not native_path.is_file() or not authored_path.is_file():
            self.skipTest('installed potion-source fixture not available')

        def item(path):
            return next(i for i in parse_gpl(path.read_text(encoding='cp1252'), str(path)).items
                        if i.normalized_name == 'potion_check')

        native, authored = item(native_path), item(authored_path)
        signature, declarations, native_body = structure(native.text)
        guard = structure(authored.text)[2][0]
        # The installed Standard version changes the limit and adds diagnostics.
        # Keep it literally, with only the authored initial exclusion and the
        # equivalent early-return layout; no shopping instructions disappear.
        expected = [guard]
        for node in native_body:
            if node.otherwise and node.body[-1].head[0] == 'return':
                expected.append(_Node(node.kind, node.head, node.body))
                expected.extend(node.otherwise)
            else:
                expected.append(node)
        for game in (GAME, Path('C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD')):
            if not (game/'SDK/Gplbcc.exe').is_file():
                continue
            root = game/'SDK/OriginalQuests'
            stock = item(root/'GPL/DecisionTrees/Modules/Purchase_Equipment.gpl')
            sdk = item(root/'GPLMx/DecisionTrees/Modules/mx_Purchase_Equipment.gpl')
            for scope, baseline in (('majesty', stock), ('majestyexpansion', sdk)):
                context = Providers((provider(native.text),), lambda _: {baseline.key:baseline},
                    game/'SDK/Gplbcc.exe', scope, source_ancestor_loader=lambda _: {sdk.key:sdk})
                with self.subTest(game=game, scope=scope), patch('majesty_cam.standard_scripts.verify'):
                    result = context.reconcile(SemanticMergeResult((authored,), ()))
                    self.assertEqual(structure(result.items[0].text), (signature, declarations, tuple(expected)))
                    with TemporaryDirectory(prefix='return-layout-fixture-') as temp:
                        compile_gpl(result.emit_project_source_set('Fixture.gpl','Fixture.dat'),
                                    game/'SDK/Gplbcc.exe', Path(temp)/'compiler', stem='Fixture')

    def test_reported_decision_function_in_both_dataset_views(self):
        # Isolated source comparison/compiler fixture, never a prepared profile.
        from majesty_cam.gpl_function_merge import _guard_chain
        from majesty_cam.gpl import add_hero_quest_lifecycle_callbacks
        from majesty_cam.standard_scripts import Providers
        from test_standard_scripts import provider
        native_path = GAME.parents[1]/'workshop/content/73230/1965892371/GPL/AI_Heroes.gpl'
        authored_path = Path(__file__).resolve().parents[1]/'payload/mods/CustomGuildPhantomsHauntExpanded/GPL/Phantom.gpl'
        if not native_path.is_file() or not authored_path.is_file():
            self.skipTest('installed decision-source fixture not available')
        def item(path, name='priestess_tree'):
            return next(i for i in parse_gpl(path.read_text(encoding='cp1252'), str(path)).items
                        if i.normalized_name == name)
        native, authored = item(native_path), item(authored_path)
        original_heads, _ = _guard_chain(structure(native.text)[2][-1])
        authored_heads, authored_tail = _guard_chain(structure(authored.text)[2][-1])
        private = {head[2]: head for head in authored_heads if head[2].startswith('$phantom_')}
        expected_heads = list(original_heads)
        expected_heads.insert(1, private['$phantom_priestess_follow_check'])
        expected_heads = tuple(private.get({'$purchase_bazaar':'$phantom_priestess_bazaar_check',
            '$hall_champs_check':'$phantom_priestess_champs_check'}.get(head[2]), head) for head in expected_heads)
        installs = (GAME, Path('C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD'))
        for game in installs:
            if not (game/'SDK/Gplbcc.exe').is_file():
                continue
            root = game/'SDK/OriginalQuests'
            stock = item(root/'GPL/DecisionTrees/Priestess.gpl')
            sdk = item(root/'GPLMx/DecisionTrees/mx_Priestess.gpl')
            for scope, baseline in (('majesty', stock), ('majestyexpansion', sdk)):
                context = Providers((provider(native.text),), lambda _: {baseline.key:baseline},
                    game/'SDK/Gplbcc.exe', scope, source_ancestor_loader=lambda _: {sdk.key:sdk})
                with self.subTest(game=game, scope=scope), patch('majesty_cam.standard_scripts.verify'):
                    result = context.reconcile(SemanticMergeResult((authored,), ()))
                    body = structure(result.items[0].text)[2]
                    self.assertEqual(body[:-1], structure(authored.text)[2][:-1])
                    self.assertEqual(_guard_chain(body[-1]), (expected_heads, authored_tail))
                    callbacks = parse_gpl(''.join(
                        f'function {name}(agent ThisAgent){returns}\ndeclare\nbegin\n{action}\nend\n'
                        for name, returns, action in (
                            ('Quest_Resume', ' is boolean', 'return FALSE;'),
                            ('Quest_Consider', ' is boolean', 'return FALSE;'),
                            ('Quest_Reset', '', ''), ('Quest_Death', '', ''))))
                    dataset, prefix = ('GPL', '') if scope == 'majesty' else ('GPLMx', 'mx_')
                    result = add_hero_quest_lifecycle_callbacks(
                        SemanticMergeResult((*result.items, *callbacks.items), ()),
                        [(('mx_priestess',), 'Quest_Resume', 'Quest_Consider', 'Quest_Reset', 'Quest_Death')],
                        stock_hero_trees={'mx_priestess': baseline},
                        stock_reset_tasks=item(root/dataset/(prefix+'LowLevel.gpl'), 'reset_tasks'),
                        stock_unit_death=item(root/dataset/(prefix+'Hero_Deaths.gpl'), 'unit_call_deathscript'))
                    tree = next(i for i in result.items if i.normalized_name == 'priestess_tree')
                    guarded_heads, guarded_tail = _guard_chain(structure(tree.text)[2][-1])
                    names = [head[2] for head in guarded_heads]
                    self.assertEqual(names.index('$quest_resume'), names.index('$check_rewards') - 1)
                    self.assertEqual(names.index('$quest_consider'), names.index('$pursue_entertainment') + 1)
                    self.assertEqual(tuple(h for h in guarded_heads
                                           if h[2] not in ('$quest_resume', '$quest_consider')), expected_heads)
                    self.assertEqual(guarded_tail, authored_tail)
                    with TemporaryDirectory(prefix='decision-chain-fixture-') as temp:
                        compile_gpl(result.emit_project_source_set('Fixture.gpl','Fixture.dat'),
                                    game/'SDK/Gplbcc.exe', Path(temp)/'compiler', stem='Fixture')

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
