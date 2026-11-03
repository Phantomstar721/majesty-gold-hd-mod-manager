from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
from types import SimpleNamespace as N
import re
import unittest
from majesty_cam.hero_combat_policy import *
from majesty_cam.gpl_function_merge import _Parser, _tokens, _render
from majesty_cam.compose import _feature_stock_functions, compile_gpl
from majesty_cam.package import parse_mod_definition, mod_definition_mapping
from majesty_cam.script_review import ScriptReviewSession as ScriptReview, pair_key
from gpl_sampler_harness import Agent, SamplerHarness

GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')

def feature(**changes):
    return parse_feature({**dict(type=TYPE, feature_key='fixture.combat', hero_title='PrivateHero',
        marker_attribute='PrivateMarker', paired_accuracy=True, level_callback_symbol='LevelChanged',
        confidence_callback_symbol='Confidence', hostile_multiplier_callback_symbol='HostileMultiplier'), **changes})

class CombatPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = {scope: _feature_stock_functions(GAME,ROOTS,dataset=scope)
                     for scope in ('majesty','majestyexpansion')}

    def test_schema_roundtrip_and_dataset_selection(self):
        from majesty_cam.compose import _uses_destination_stock_features
        f = feature()
        self.assertEqual(parse_feature(feature_mapping(f)),f)
        raw = dict(schema_version=3,mod_id='00000000-0000-0000-0000-000000000001',
            internal_name='Fixture',display_name='Fixture',custom_buildings=[],runtime_features=[feature_mapping(f)])
        parsed = parse_mod_definition(raw)
        self.assertEqual(parse_mod_definition(mod_definition_mapping(parsed)),parsed)
        self.assertTrue(_uses_destination_stock_features((N(selected=N(package=N(definition=parsed))),)))
        for delta in ({'paired_accuracy':1},{'marker_attribute':'MM_Bad'},{'confidence_callback_symbol':'x);'},
                      {'melee_accuracy_per_level':True},{'melee_accuracy_per_level':0},
                      {'ranged_accuracy_per_level':99},{'ranged_accuracy_per_level':1.5},
                      {'paired_accuracy':False,'melee_accuracy_per_level':2}):
            with self.assertRaises(ValueError):parse_feature({**feature_mapping(f),**delta})

    def generated(self, scope, f=None):
        f = f or feature()
        return tuple(transform(i,(f,)) for i in self.stock[scope].values()), helper(f)

    def test_both_datasets_compile_without_replacing_callers_or_adding_load_code(self):
        for scope in self.stock:
            items, guard = self.generated(scope,feature(melee_accuracy_per_level=2,ranged_accuracy_per_level=1))
            text = '\n'.join(i.text for i in (*items,guard))
            for forbidden in ('$RunThread','$SetAttribute','$AddAttribute','function give_exp','function drain_level','function target_eval','function should_I_run'):
                if forbidden == '$SetAttribute': continue # unchanged stock HP setter
                self.assertNotIn(forbidden.casefold(),text.casefold())
            callbacks = parse_gpl('''
function LevelChanged(agent Hero, integer Direction) declare begin end
function Confidence(agent Hero) is integer declare begin return 10; end
function HostileMultiplier(agent Hero, agent Hostile) is float declare begin return 0.6; end
''').items
            with TemporaryDirectory() as temporary:
                compile_gpl(SemanticMergeResult((*items,guard,*callbacks),()).emit_project_source_set(),
                    GAME/'SDK/Gplbcc.exe',Path(temporary)/'compiler',stem='CombatPolicy')

    def test_custom_accuracy_adjustments_caps_and_mode_without_replay(self):
        self.check_accuracy(2,1)
        self.check_accuracy(1,3)

    def test_ordinary_accuracy_adjustments_caps_and_mode_without_replay(self):
        self.check_accuracy(1,1)

    def check_accuracy(self,melee,ranged):
        for scope in self.stock:
            f = feature(melee_accuracy_per_level=melee,ranged_accuracy_per_level=ranged); items, guard = self.generated(scope,f)
            for name,direction in zip(FUNCTIONS,(1,-1)):
                item = next(i for i in items if i.normalized_name==name)
                body = _Parser(item.text).function()[2]
                # Execute exactly the transformed accuracy clauses, not a Python reimplementation.
                branches = [n for n in body if any('attrib_htoh' in t or 'attrib_ranged' in t for t in _tokens('\n'.join(_render((n,)))))]
                code = 'function Probe(agent thisagent) declare begin '+ '\n'.join(_render(branches))+' end\n'+guard.text
                code = re.sub(r'#(\w+)',lambda m:'"'+m[1].lower()+'"',code)
                vm = SamplerHarness(code.lower())
                vm.calls.update({'isvalidgamepiece':lambda h:h.alive,'isdead':lambda h:not h.alive,
                    'hasattribute':lambda k,h:k in h.fields,'getattribute':lambda h,k:h[k],
                    'adjustattribute':lambda h,k,v:h.fields.__setitem__(k,h[k]+v)})
                for private in (False,True):
                    for mode in (1,2):
                        for accuracy in (0,1,2,3,50,96,97,98,99):
                            hero=Agent(); hero.fields={'title':'privatehero' if private else 'ranger',
                                'privatemarker':True,'attacktype':mode,'attrib_htoh':accuracy,'attrib_ranged':accuracy}
                            vm.call('Probe',hero)
                            delta=direction if (accuracy<98 if direction==1 else accuracy>1) else 0
                            for attr,step,active in (('attrib_htoh',melee,mode==1),('attrib_ranged',ranged,mode==2)):
                                expected=accuracy+(delta if active else 0)
                                if private:
                                    expected=(min(98,accuracy+step) if direction==1 else max(1,accuracy-step)) if delta else accuracy
                                self.assertEqual(hero[attr],expected,(scope,name,private,mode,accuracy,attr))

    def test_scoring_retains_stock_group_calculation_and_uses_each_hostile(self):
        for scope in self.stock:
            base = self.stock[scope][(DefinitionKind.FUNCTION,'list_eval')]
            changed = transform(base,(feature(),))
            self.assertEqual(_tokens(changed.text).count('$hostilemultiplier'),1)
            self.assertIn(_tokens('hitstokill = (thisagent\'s "enemy_estimation") * hitstokill;'),
                          [n.head for n in _Parser(changed.text).function()[2]])
            self.assertNotIn('setattribute',changed.text.lower())
            self.assertEqual(changed.text.lower().count('enemy_total_hp +='),2) # opted-in branch + literal stock else

    def test_preferred_mod_keeps_actual_conflicts_and_suppresses_losing_policy(self):
        f=feature(); records=(('policy','Private policy',f),)
        stock=self.stock['majesty']; key=(DefinitionKind.FUNCTION,FUNCTIONS[0])
        altered=replace(stock[key],text=stock[key].text.replace('< 98','< 80'))
        # A conflicting cap is genuinely incompatible; both choices remain usable.
        for winner in ('other','policy'):
            review=ScriptReview({pair_key('other','policy'):winner})
            plans=review_policies('majesty',records,{key:(ScriptCandidate('Other',altered,'other'),)},lambda n:stock,review)
            output=apply(SemanticMergeResult((),()),records,plans,review)
            selected=next(i for i in output.items if i.key==key)
            if winner=='other': self.assertEqual(selected.text,altered.text)
            else: self.assertIn(gate(f).lower(),selected.text.lower())

    def test_lifecycle_callback_is_terminal_once_and_opt_in_guard_handles_stale_actors(self):
        for scope in self.stock:
            for name,direction in zip(FUNCTIONS,(1,-1)):
                original=self.stock[scope][(DefinitionKind.FUNCTION,name)]
                f=feature(paired_accuracy=False)
                changed=transform(original,(f,))
                before=_Parser(original.text).function()[2]
                after=_Parser(changed.text).function()[2]
                self.assertEqual(after[:-1],before)
                self.assertEqual(_tokens(changed.text).count('$levelchanged'),1)
                self.assertEqual(after[-1].body[0].head, _tokens(f'$LevelChanged(thisagent,{direction});'))
        f=feature(); vm=SamplerHarness(helper(f).text)
        for title,marker,alive,expected in [('PrivateHero',True,True,True),('PrivateHero',False,True,False),
                ('PrivateHero',True,False,False),('Ranger',True,True,False),('PrivateHero',None,True,False)]:
            hero=Agent();hero.fields={'Title':title};hero.alive=alive
            if marker is not None:hero.fields['PrivateMarker']=marker
            self.assertEqual(vm.call(gate(f),hero),expected)
        self.assertFalse(vm.call(gate(f),None))

    def test_production_review_preserves_preferred_source_without_reapplying_policy(self):
        from majesty_cam.compose import merge_gpl_resources
        from majesty_cam.script_review import group_conflicts
        f=feature(paired_accuracy=True,level_callback_symbol=None,
                  confidence_callback_symbol=None,hostile_multiplier_callback_symbol=None)
        with TemporaryDirectory() as temporary:
            path=Path(temporary)/'hero.xml'
            path.write_text('<Majesty><Description type="Unit" subType="Character" ID="HCP1" Name="PrivateHero"/></Majesty>')
            def inventory(alias,features,sources):
                return N(selected=N(alias=alias,package=N(definition=N(runtime_features=features,
                    custom_buildings=(),mod_id=alias),mod_id=alias,display_name=alias),semantic_passthrough=False),
                    semantic_sources=sources,gpl_loads=(),descriptions=(path,))
            for scope,stock in self.stock.items():
                key=(DefinitionKind.FUNCTION,FUNCTIONS[0])
                altered=parse_gpl(stock[key].text.replace('< 98','< 80'))
                for winner in ('other','policy'):
                    review=ScriptReview()
                    result=merge_gpl_resources((inventory('policy',(f,),()),inventory('other',(),(altered,))),
                        stock_function_loader=lambda names:stock,script_review=review,script_dataset=scope)
                    self.assertTrue(review.unresolved)
                    review.apply({p.identity:winner for p in group_conflicts(review.conflicts)})
                    output=result.resume()
                    actual=parse_gpl(output.source_set.gpl_text).require(*key)
                    if winner=='other':self.assertEqual(_tokens(actual.text),_tokens(altered.items[0].text))
                    else:self.assertIn(gate(f).lower(),actual.text.lower())


if __name__ == '__main__':unittest.main()
