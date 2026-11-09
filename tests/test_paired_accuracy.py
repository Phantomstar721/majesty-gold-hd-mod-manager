from dataclasses import replace
import unittest
from majesty_cam.paired_accuracy import compose_candidate, compose_source, FUNCTIONS, OWNER
from majesty_cam.gpl import parse_gpl
from majesty_cam.gpl_function_merge import _Parser


def stock():
    parts=[]
    for name,delta,op,cap in ((FUNCTIONS[0],1,'<',98),(FUNCTIONS[1],-1,'>',1)):
        parts.append(f'''function {name}(agent thisagent)
declare integer hp;
begin
$StockBefore(thisagent);
if (thisagent's "attacktype" == 1)
 if ($getattribute(thisagent,#ATTRIB_HtoH) {op} {cap}) $adjustattribute(thisagent,#ATTRIB_HtoH,{delta});
$StockDodgeAndParry(thisagent);
if (thisagent's "attacktype" == 2)
 if ($getattribute(thisagent,#ATTRIB_Ranged) {op} {cap}) $adjustattribute(thisagent,#ATTRIB_Ranged,{delta});
$StockAfter(thisagent);
end''')
    return '\n'.join(parts)


class PairedAccuracyTests(unittest.TestCase):
    def test_complete_source_preserves_unrelated_functions_and_comments(self):
        untouched = 'function unrelated(agent hero) begin $Other(hero); end'
        source = '// leading comment\n' + stock() + '\n// trailing comment\n' + untouched
        output = compose_source(source, marker='PrivateMarker', helper_symbol='PrivateMode')
        self.assertIn('// leading comment', output)
        self.assertIn('// trailing comment\n' + untouched, output)
        names = [item.normalized_name for item in parse_gpl(output).items]
        self.assertEqual(names.count('privatemode'), 1)
        for name in FUNCTIONS:
            self.assertEqual(names.count(name), 1)
        self.assertNotIn('restore', output.casefold())

    def test_expansion_leading_decimal_remains_one_compiler_token(self):
        source = stock().replace('$StockBefore(thisagent);',
                                 'thisagent\'s "enemy_estimation" = .9;')
        output = compose_source(source, marker='PrivateMarker', helper_symbol='PrivateMode')
        self.assertIn('= .9 ;', output)
        self.assertNotIn('. 9', output)

    def compose(self, text=None, **kwargs):
        return compose_candidate(stock() if text is None else text,
                                 marker='PrivateMarker', helper_symbol='PrivateMode', **kwargs)

    def test_only_mode_guards_change_and_persistence_is_not_advertised(self):
        candidate=self.compose()
        self.assertFalse(candidate.runtime_ready)
        source=stock().split('function ')[1:]
        for raw,(_,new) in zip(source,candidate.functions):
            before=_Parser('function '+raw).function()
            after=_Parser(new).function()
            self.assertEqual(before[:2],after[:2])
            restored=tuple(replace(n,head=old.head) if '$privatemode' in n.head else n
                           for old,n in zip(before[2],after[2]))
            self.assertEqual(before[2],restored)
        helper=_Parser(candidate.helper).function()[2]
        self.assertIn('$hasattribute',helper[0].head)
        self.assertEqual(helper[0].body[0].kind,'if')

    def test_changed_cap_delta_missing_pair_duplicate_and_symbol_collision_refuse(self):
        variants=[stock().replace('< 98','< 97'),stock().replace('#ATTRIB_HtoH,1','#ATTRIB_HtoH,2'),
                  stock().split('function '+FUNCTIONS[1])[0],stock()+stock(),
                  stock()+'\nfunction PrivateMode(agent h) begin end']
        for raw in variants:
            with self.subTest(raw=raw),self.assertRaises(ValueError): self.compose(raw)

    def test_independent_provider_composes_but_cannot_change_accuracy_body(self):
        base=stock().split('function '+FUNCTIONS[1])[0]
        candidate=self.compose(other_variants={FUNCTIONS[0]:{'other':base.replace('$StockBefore','$OtherBefore')}})
        self.assertIn('$otherbefore',candidate.functions[0][1])
        bad=base.replace('#ATTRIB_HtoH,1','#ATTRIB_HtoH,2')
        with self.assertRaises(ValueError):self.compose(other_variants={FUNCTIONS[0]:{'other':bad}})
        with self.assertRaises(ValueError):self.compose(other_variants={FUNCTIONS[0]:{OWNER:base}})

    def test_identifier_injection_and_unknown_function_rejected(self):
        with self.assertRaises(ValueError):
            compose_candidate(stock(),marker='x";',helper_symbol='PrivateMode')
        with self.assertRaises(ValueError):self.compose(other_variants={'unknown':{}})
