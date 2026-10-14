from pathlib import Path
from tempfile import TemporaryDirectory
from collections import defaultdict
from dataclasses import replace
import re
import unittest
import os
from majesty_cam.damage_contributions import *
from majesty_cam.compose import _feature_stock_functions, compile_gpl
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from gpl_sampler_harness import SamplerHarness, Agent

GAME=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
if os.environ.get('MAJESTY_REQUIRE_DAMAGE_FIXTURES') == '1' and not (GAME/'SDK/Gplbcc.exe').is_file():
    raise RuntimeError('Required installed damage GPL/compiler fixture is missing')

def declarations(phases):
    features=[]; sources=[]
    for index,phase in enumerate(phases):
        types,returns=SIGNATURES[phase];name='Contributor'+str(index)
        feature=DamageContribution('effect'+str(index),((phase,name),));features.append(feature)
        value=('a2' if phase.startswith('weapon_') else 'a3')
        if phase=='weapon_begin':value='0'
        if returns=='boolean':value='FALSE'
        source=parse_gpl(f'function {name}('+','.join(t+' a'+str(n) for n,t in enumerate(types))+') '+
                         ('is '+returns if returns else '')+' declare begin '+('return '+value+';' if returns else '')+' end')
        sources.append(source)
    return tuple(features),tuple(sources)

def executable_source(items):
    text='\n'.join(i.text for i in items)
    text=re.sub(r'#(?:intelligence_div|strength_div|level_div|armor_magic_mult)\b','1',text,flags=re.I)
    text=re.sub(r'#Deathmatch_Building_Damage_Multiplier\b','3',text,flags=re.I)
    text=re.sub(r'#FireBalmDamageBonus\b','2',text,flags=re.I)
    text=re.sub(r'#(\w+)',lambda m:'"'+m[1].lower()+'"',text)
    text=re.sub(r"'s\s+\"([^\"]+)\"",lambda m:"'s \""+m[1].lower()+'"',text)
    text=re.sub(r'\b(\w+)\s*([*/-])=\s*([^;]+);',lambda m:f'{m[1]} = {m[1]} {m[2]} ({m[3]});',text)
    return text

class DamageDeclarationTests(unittest.TestCase):
    def test_package_roundtrip_and_destination_scoping(self):
        from types import SimpleNamespace
        from majesty_cam.package import parse_mod_definition, mod_definition_mapping
        from majesty_cam.compose import _uses_destination_stock_features
        value={'schema_version':3,'mod_id':'{42ba4603-2b13-446d-a2a4-6cf3a55ddac3}',
               'internal_name':'Example','display_name':'Example','custom_buildings':[],
               'runtime_features':[feature_mapping(declarations(('spell_bonus',))[0][0])]}
        definition=parse_mod_definition(value)
        self.assertEqual(parse_mod_definition(mod_definition_mapping(definition)),definition)
        inventory=SimpleNamespace(selected=SimpleNamespace(package=SimpleNamespace(definition=definition)))
        self.assertTrue(_uses_destination_stock_features((inventory,)))

    def test_schema_and_actual_ownership_not_whole_source_hashes(self):
        features,sources=declarations(('spell_bonus',))
        self.assertEqual(parse_feature(feature_mapping(features[0])),features[0])
        self.assertEqual(validate_bindings((('owner',features,sources),)),features)
        for value in ({'unrecognized':'F'}, {}, {'spell_bonus':'MM_reserved'}):
            with self.assertRaises(ValueError):parse_feature({'type':FEATURE_TYPE,'feature_key':'one','callbacks':value})
        with self.assertRaisesRegex(ValueError,'package-owned'):
            validate_bindings((('owner',features,()),('another',(),sources)))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            validate_bindings((('owner',features+features,sources),))
    def test_no_feature_means_no_stock_lookup_or_change(self):
        result=SemanticMergeResult((),())
        self.assertIs(compose(result,(),None),result)

@unittest.skipUnless((GAME/'SDK/Gplbcc.exe').is_file(),'installed SDK fixture required')
class StockDamageContributionTests(unittest.TestCase):
    def test_periodic_routing_preserves_authored_calls_and_custom_helpers(self):
        from majesty_cam.gpl_function_merge import _Parser
        features, sources = declarations(('spell_bonus', 'after_hp'))
        callbacks = tuple(i for source in sources for i in source.items)
        for scope in ('majesty', 'majestyexpansion'):
            for name in ('Vortex_Active', 'Wind_Storm_Active'):
                text = f'''function {name}(agent caster)
declare
agent victim;
integer power;
begin
power = 37;
if (power > 0) begin
$player_spell_attack(victim,power,2);
$player_spell_attack(caster,11,3);
end else $spell_attack(caster,victim,power + 1);
$CustomAttack(caster,victim,19);
$DebugOut(911,"$spell_attack(caster,victim,20)");
end'''
                original = parse_gpl(text).items[0]
                result = compose(SemanticMergeResult((*callbacks, original), ()), features,
                                 lambda names: self.stock[scope])
                actual = next(i for i in result.items if i.key == original.key)
                expected = text.replace('$player_spell_attack(', '$MM_Damage_PeriodicPlayerSpellAttack(')
                expected = expected.replace('else $spell_attack(', 'else $MM_Damage_PeriodicSpellAttack(')
                self.assertEqual(_Parser(actual.text).function(), _Parser(expected).function())
                custom = parse_gpl(f'function {name}(agent caster) declare begin $CustomAttack(caster); end').items[0]
                result = compose(SemanticMergeResult((*callbacks, custom), ()), features,
                                 lambda names: self.stock[scope])
                self.assertEqual(next(i for i in result.items if i.key == custom.key), custom)

    @classmethod
    def setUpClass(cls):
        cls.stock={scope:_feature_stock_functions(GAME,ROOTS,dataset=scope) for scope in ('majesty','majestyexpansion')}
    def build(self,scope,phases=SIGNATURES):
        features,sources=declarations(phases)
        result=compose(SemanticMergeResult(tuple(i for s in sources for i in s.items),()),features,
                       lambda names:{k:v for k,v in self.stock[scope].items() if k[1] in {n.lower() for n in names}})
        return result,features
    def test_production_source_pipeline_retains_generated_patch_functions(self):
        from types import SimpleNamespace as N
        from majesty_cam.compose import merge_gpl_resources
        features,sources=declarations(('spell_bonus','after_hp'))
        definition=N(runtime_features=features,custom_buildings=(),mod_id='{00000000-0000-0000-0000-000000000001}')
        inventory=N(selected=N(alias='example',package=N(definition=definition,mod_id=definition.mod_id),
                               semantic_passthrough=False),semantic_sources=sources,gpl_loads=(),descriptions=())
        for scope in self.stock:
            result=merge_gpl_resources((inventory,),
                stock_semantic_sources=(parse_gpl('\n'.join(i.text for i in self.stock[scope].values())),),
                stock_function_loader=lambda names:self.stock[scope])
            text=result.source_set.gpl_text.lower()
            for name in ('mm_damage_spell','spell_attack','player_spell_attack','vortex_active','wind_storm_active'):
                self.assertIn('function '+name,text)
            self.assertIn('$contributor0',text)

    def test_both_destination_sources_compile_and_keep_single_debit(self):
        for scope in self.stock:
            result,features=self.build(scope)
            index={i.normalized_name:i for i in result.items}
            for name in ('damage','mm_damage_spell'):
                self.assertEqual(index[name].text.lower().count('$adjustattribute'),1)
            self.assertNotIn('$spelldamage',index['spell_attack'].text.lower())
            self.assertIn('false',index['mm_damage_periodicspellattack'].text.lower())
            with TemporaryDirectory() as directory:
                compile_gpl(result.emit_project_source_set(),GAME/'SDK/Gplbcc.exe',Path(directory)/'compiler',stem='DamageFixture')
    def test_contributions_are_order_independent_inputs_but_fixed_phase_order(self):
        result,features=self.build('majestyexpansion')
        own=tuple(i for i in result.items if i.normalized_name.startswith('contributor'))
        reversed_result=compose(SemanticMergeResult(own,()),tuple(reversed(features)),lambda names:self.stock['majestyexpansion'])
        self.assertEqual({i.key:i.text for i in result.items},{i.key:i.text for i in reversed_result.items})
    def test_real_changed_boundary_fails_but_unrelated_edit_survives(self):
        result,features=self.build('majesty')
        own=tuple(i for i in result.items if i.normalized_name.startswith('contributor'))
        stock=self.stock['majesty'][(DefinitionKind.FUNCTION,'damage')]
        changed=parse_gpl(stock.text.replace('$BuildingDamageModifier','$DifferentBuildingPolicy')).items[0]
        with self.assertRaisesRegex(ValueError,'boundary changed'):
            compose(SemanticMergeResult((*own,changed),()),features,lambda names:self.stock['majesty'])
        changed=parse_gpl(stock.text.replace('"gethit"','"custom_sound"')).items[0]
        out=compose(SemanticMergeResult((*own,changed),()),features,lambda names:self.stock['majesty'])
        self.assertIn('"custom_sound"',next(i.text for i in out.items if i.normalized_name=='damage'))

    def test_generated_weapon_preferences_keep_actual_winner_and_other_spells(self):
        from majesty_cam.damage_contributions import review_weapon
        from majesty_cam.script_review import ScriptCandidate, ScriptReviewSession, group_conflicts
        for scope,stock in self.stock.items():
            key=(DefinitionKind.FUNCTION,'damage')
            # An unnamed mod legitimately replaces armor computation; do not
            # special-case a package ID, helper name or its formula.
            rewritten=parse_gpl(stock[key].text.replace('dmg_stopped = t + t2;',
                                                        'dmg_stopped = t * 2;')).items[0]
            features,sources=declarations(('weapon_blocked','spell_bonus'))
            packages=(('provider','Extra effects',features,sources),)
            review=ScriptReviewSession()
            conflict,providers=review_weapon(scope,packages,
                (ScriptCandidate('Different armor',rewritten,'armor'),),lambda names:stock,review)
            self.assertEqual(len(group_conflicts(review.conflicts)),1)
            identity=group_conflicts(review.conflicts)[0].identity
            for winner in ('armor','provider'):
                chosen_review=ScriptReviewSession({identity:winner})
                chosen=chosen_review.resolve(conflict)
                selected=chosen_review.selected_owners(conflict)
                active=tuple(f for owner in selected for f in providers.get(owner,()))
                callbacks=tuple(i for source in sources for i in source.items)
                output=compose(SemanticMergeResult((*callbacks,chosen),()),features,lambda names:stock,
                               reviewed_weapon=True,weapon_features=active)
                damage=next(i for i in output.items if i.key==key)
                self.assertEqual(damage.text,chosen.text) # not patched again after review
                if winner=='armor':
                    self.assertEqual(damage.text,rewritten.text)
                    self.assertNotIn('$contributor0',damage.text.lower())
                else:self.assertIn('$contributor0',damage.text.lower())
                spell=next(i for i in output.items if i.normalized_name=='mm_damage_spell')
                self.assertIn('$contributor1',spell.text.lower())
                with TemporaryDirectory() as directory:
                    compile_gpl(output.emit_project_source_set(),GAME/'SDK/Gplbcc.exe',
                                Path(directory)/'compiler',stem='ReviewedDamage')

    def test_production_source_review_sees_generated_conflict_before_resume(self):
        from types import SimpleNamespace as N
        from majesty_cam.compose import merge_gpl_resources
        from majesty_cam.script_review import ScriptReviewSession,group_conflicts
        features,sources=declarations(('weapon_blocked',))
        def inventory(alias,features,sources):
            definition=N(runtime_features=features,custom_buildings=(),mod_id=alias)
            return N(selected=N(alias=alias,package=N(definition=definition,mod_id=alias,
                display_name=alias),semantic_passthrough=False),semantic_sources=sources,
                gpl_loads=(),descriptions=())
        for scope,stock in self.stock.items():
            damage=stock[(DefinitionKind.FUNCTION,'damage')]
            rewritten=parse_gpl(damage.text.replace('dmg_stopped = t + t2;', 'dmg_stopped = t * 2;'))
            review=ScriptReviewSession()
            pending=merge_gpl_resources((inventory('effects',features,sources),
                    inventory('armor',(),(rewritten,))),
                stock_semantic_sources=(parse_gpl('\n'.join(i.text for i in stock.values())),),
                stock_function_loader=lambda names:stock,script_review=review,script_dataset=scope)
            self.assertTrue(review.unresolved)
            review.apply({p.identity:'armor' for p in group_conflicts(review.conflicts)})
            result=pending.resume()
            actual=parse_gpl(result.source_set.gpl_text).require(DefinitionKind.FUNCTION,'damage')
            from majesty_cam.gpl_function_merge import _tokens
            self.assertEqual(_tokens(actual.text),_tokens(rewritten.items[0].text))

    def test_generated_providers_combine_and_mixed_preferences_do_not_leak_losers(self):
        from majesty_cam.damage_contributions import review_weapon
        from majesty_cam.script_review import ScriptCandidate, ScriptReviewSession, pair_key
        stock=self.stock['majesty'];key=(DefinitionKind.FUNCTION,'damage')
        features,sources=declarations(('weapon_blocked','weapon_pre_armor'))
        rewritten=parse_gpl(stock[key].text.replace('dmg_stopped = t + t2;',
                                                   'dmg_stopped = t * 2;').replace(
            'if (( defender\'s "type" == "building" ) || ( defender\'s "type" == "lair" ))',
            'if (defender\'s "type" == "building" || defender\'s "type" == "lair")')).items[0]
        packages=tuple((str(i),'Provider '+str(i),(feature,),(source,))
                       for i,(feature,source) in enumerate(zip(features,sources)))
        review=ScriptReviewSession()
        conflict,_=review_weapon('majesty',packages,(),lambda names:stock,review)
        self.assertFalse(review.unresolved)
        self.assertIn('$contributor0',review.resolve(conflict).text.lower())
        self.assertIn('$contributor1',review.resolve(conflict).text.lower())
        # Same owner identities group into the same pair across quest datasets.
        for scope in self.stock:
            review_weapon(scope,packages,(ScriptCandidate('Armor',rewritten,'armor'),),
                          lambda names:self.stock[scope],review)
        from majesty_cam.script_review import group_conflicts
        self.assertEqual(len({p.identity for p in group_conflicts(review.conflicts)}),
                         len(group_conflicts(review.conflicts)))
    def test_inapplicable_weapon_contributions_preserve_stock_results_and_rolls(self):
        for scope in self.stock:
            generated,_=self.build(scope)
            stock_items=[self.stock[scope][(DefinitionKind.FUNCTION,n)] for n in ('damage','buildingdamagemodifier')]
            generated_items=[i for i in generated.items if i.normalized_name in ('damage','mm_damage_building') or i.normalized_name.startswith('contributor')]
            for kind,critical,armor in (('hero',0,0),('hero',100,3),('monster',0,40),('building',0,0)):
                traces=[]
                for items in (stock_items,generated_items):
                    vm=SamplerHarness(executable_source(items));trace=[]
                    attacker=Agent();defender=Agent()
                    attacker.fields=defaultdict(int,{'type':kind,'subtype':kind,'strength':10,'critical_chance':critical,
                        'attrib_weapon_basic_damage':12,'attrib_strength':16,'attrib_experiencelevel':2})
                    defender.fields=defaultdict(int,{'type':'hero','subtype':'hero','attrib_hp':100,'attrib_maxhp':100,'attrib_armor_basic_damage':armor})
                    vm.calls.update({'randomnumber':lambda n:trace.append(('roll',n)) or max(0,n-1),
                        'getattribute':lambda a,k:a[k], 'getunitplayernumber':lambda a:0,
                        'createeffector':lambda *a:trace.append(('effect',a[1])),
                        'playsound':lambda *a:trace.append(('sound',a[1])),
                        'createspellunit':lambda *a:trace.append(('spell',a[1])),
                        'say':lambda *a:trace.append(('say',a[1])),
                        'adjustattribute':lambda a,k,n:trace.append(('hp',n))})
                    vm.call('damage',attacker,defender);traces.append(trace)
                self.assertEqual(*traces,(scope,kind,critical,armor))
    def test_direct_periodic_and_separate_source_order(self):
        phases=('spell_bonus','spell_flat_reduce','spell_percent_reduce','spell_final','after_hp')
        result,features=self.build('majestyexpansion',phases)
        items=[i for i in result.items if i.normalized_name=='mm_damage_spell' or i.normalized_name.startswith('contributor')]
        for direct in (True,False):
            vm=SamplerHarness(executable_source(items));events=[]
            source=Agent();defender=Agent();defender.fields={'subtype':'hero','attrib_armor_magic_bonus':2,'attrib_hp':100}
            vm.calls.update({'randomnumber':lambda n:events.append(('roll',n)) or 9,'getattribute':lambda a,k:a[k],
                'contributor0':lambda s,a,d,n:events.append(('bonus',s is source,a)) or n+3,
                'contributor1':lambda s,a,d,n:events.append(('flat',n)) or n-2,
                'contributor2':lambda s,a,d,n:events.append(('percent',n)) or n//2,
                'contributor3':lambda s,a,d,n:events.append(('final',n)),
                'contributor4':lambda a,d,h:events.append(('after',h)),
                'adjustattribute':lambda a,k,n:events.append(('hp',n))})
            amount=vm.call('mm_damage_spell',source,None,defender,20,1,1,direct)
            self.assertEqual(amount,5 if direct else 12)
            self.assertEqual(events,[('roll',20),('bonus',True,None),*([('flat',12),('percent',10),('final',5)] if direct else []),
                                     ('hp',-5 if direct else -12),*([('after',100)] if direct else [])])

    def test_multiple_providers_compose_flat_then_percentage_with_one_debit(self):
        # Source-owned eligibility helpers are stubs; actual emitted calculation,
        # phase ordering, per-provider local state, and HP ownership execute here.
        result,_=self.build('majestyexpansion',('weapon_begin','weapon_pre_armor',
            'weapon_flat_reduce','weapon_percent_reduce','weapon_final','after_hp'))
        items=[i for i in result.items if i.normalized_name=='damage' or i.normalized_name.startswith('contributor')]
        vm=SamplerHarness(executable_source(items));events=[]
        attacker=Agent();attacker.fields=defaultdict(int,{'type':'hero','subtype':'hero',
            'attrib_weapon_basic_damage':10,'attrib_strength':0,'attrib_experiencelevel':0})
        defender=Agent();defender.fields=defaultdict(int,{'type':'hero','subtype':'hero','attrib_hp':100})
        vm.calls.update({'getattribute':lambda a,k:a[k],'getunitplayernumber':lambda a:0,
            'randomnumber':lambda n:events.append(('roll',n)) or max(0,n-1),
            'contributor0':lambda *args:events.append(('begin',)) or 1,
            'contributor1':lambda a,d,n,s,c:events.append(('bonus',n,s,c)) or n+3,
            'contributor2':lambda a,d,n,s,c:events.append(('flat',n)) or n-3,
            'contributor3':lambda a,d,n,s,c:events.append(('percent',n)) or n//2,
            'contributor4':lambda a,d,n,s,c:events.append(('final',n)),
            'contributor5':lambda a,d,h:events.append(('after',h)),
            'playsound':lambda *args:None,'createeffector':lambda *args:None,
            'createspellunit':lambda *args:None,'say':lambda *args:None,
            'adjustattribute':lambda a,k,n:events.append(('hp',n))})
        vm.call('damage',attacker,defender)
        meaningful=[e for e in events if e[0]!='roll']
        self.assertEqual(meaningful,[('begin',),('bonus',10,0,False),('flat',13),
            ('percent',10),('final',5),('hp',-5),('after',100)])
        self.assertEqual(sum(e==('roll',10) for e in events),1)

    def test_zero_damage_has_no_final_or_post_hit_notifications(self):
        result,_=self.build('majesty',('spell_flat_reduce','spell_final','after_hp'))
        items=[i for i in result.items if i.normalized_name=='mm_damage_spell' or i.normalized_name.startswith('contributor')]
        vm=SamplerHarness(executable_source(items));events=[]
        defender=Agent();defender.fields={'subtype':'hero','attrib_armor_magic_bonus':0,'attrib_hp':100}
        vm.calls.update({'randomnumber':lambda n:0,'getattribute':lambda a,k:a[k],
                         'contributor0':lambda *args:0,'contributor1':lambda *args:events.append('final'),
                         'contributor2':lambda *args:events.append('after'),
                         'adjustattribute':lambda a,k,n:events.append(('hp',n))})
        self.assertEqual(vm.call('mm_damage_spell',None,None,defender,10,1,0,True),0)
        self.assertEqual(events,[('hp',0)])

    def test_building_admission_does_not_bypass_deathmatch(self):
        for scope in self.stock:
            result,_=self.build(scope,('weapon_building_full',))
            items=[i for i in result.items if i.normalized_name in ('mm_damage_building','contributor0')]
            for deathmatch in (False,True):
                vm=SamplerHarness(executable_source(items));calls=[]
                vm.root.fields={'Deathmatch_Rules':deathmatch,'deathmatch_rules':deathmatch}
                attacker=Agent();attacker.fields={'subtype':'hero'}
                defender=Agent()
                vm.calls['contributor0']=lambda *args:calls.append('admission') or True
                self.assertEqual(vm.call('mm_damage_building',attacker,defender,11),33 if deathmatch else 11)
                self.assertEqual(calls,[] if deathmatch else ['admission'])

    def test_generated_periodic_target_transports_source_without_replacing_null_attacker(self):
        from majesty_cam.source_context import parse_feature as parse_context, compose as adapt
        feature=parse_context({'type':'stock.source-context-dispatch.v1','feature_key':'attributed',
            'target_symbol':'MM_Damage_PeriodicPlayerSpellAttack','parameter_types':['agent','integer','integer'],
            'callback_symbol':'Attributed'})
        with self.assertRaises(ValueError):parse_context({**feature_mapping_context(feature),'target_symbol':'MM_Unknown'})
        with self.assertRaises(ValueError):parse_context({**feature_mapping_context(feature),'callback_symbol':'MM_Forbidden'})
        result,_=self.build('majestyexpansion',('spell_bonus',))
        adapter=parse_gpl('function Attributed(agent Source,agent Target,integer Damage,integer Minimum) declare begin '
            '$MM_Damage_Spell(Source,$nullagent(),Target,Damage,Minimum,0,FALSE); end').items
        result=SemanticMergeResult((*result.items,*adapter),())
        result=adapt(result,(feature,),('wind_storm_active',),None)
        wind=next(i.text for i in result.items if i.normalized_name=='wind_storm_active')
        self.assertRegex(wind,r'\$Attributed\s*\(thisagent\s*,')
        self.assertEqual(wind.lower().count('$attributed'),1)

def feature_mapping_context(feature):
    from majesty_cam.source_context import feature_mapping
    return feature_mapping(feature)

if __name__=='__main__':unittest.main()
