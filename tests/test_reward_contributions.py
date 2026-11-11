from dataclasses import replace
from pathlib import Path
import ast
import re
import unittest
from majesty_cam.gpl import parse_gpl,DefinitionKind
from majesty_cam.gpl_function_merge import _tokens,_Parser,FunctionMergeError
from majesty_cam.reward_contributions import parse,mapping,render,equivalent,validate,review,KEY,TYPE,SIGNATURES
from majesty_cam.package import parse_mod_definition,mod_definition_mapping
from majesty_cam.script_review import ScriptReviewSession,ScriptCandidate,pair_key
from gpl_sampler_harness import SamplerHarness,Agent

GAME=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
BASE=GAME/'SDK/OriginalQuests/GPL/DecisionTrees/Modules'
STOCK=parse_gpl((BASE/'check_rewards.gpl').read_text()).require(DefinitionKind.FUNCTION,'check_rewards')
RAID=parse_gpl((BASE/'raid_lair.gpl').read_text()).require(DefinitionKind.FUNCTION,'raid_lair')
OWNER_A='00000000-0000-0000-0000-000000000001'
OWNER_B='00000000-0000-0000-0000-000000000002'


def feature(key,phases,**kwargs):
    return parse({'type':TYPE,'feature_key':key,'callbacks':{p:'Provider_'+p for p in phases},**kwargs})


def helpers(f):
    return parse_gpl('\n'.join('function '+name+'('+','.join(t+' Arg'+str(i) for i,t in enumerate(SIGNATURES[p][0]))+
        ') is '+SIGNATURES[p][1]+' declare '+('list Result;' if SIGNATURES[p][1]=='list' else '')+' begin '+
        ('return True;' if SIGNATURES[p][1]=='boolean' else
        'return Result;' if SIGNATURES[p][1]=='list' else 'return 0;')+' end'
        for p,name in f.callbacks))


class Actor(Agent):
    def __init__(self,**fields):
        super().__init__();self.fields={k.lower():v for k,v in fields.items()}
    def __getitem__(self,key):return self.fields[key.lower()]
    def __setitem__(self,key,value):self.fields[key.lower()]=value


class RewardHarness(SamplerHarness):
    # Source-level integer division, with safe-sized test values. No VM/native
    # integer-overflow, query-order or payout semantics are claimed here.
    def expression(self,tokens):
        class Division(ast.NodeTransformer):
            def visit_BinOp(self,n):
                n=self.generic_visit(n)
                call=ast.Subscript(ast.Name('F',ast.Load()),ast.Constant('__divide'),ast.Load())
                return ast.copy_location(ast.Call(call,[n.left,n.right],[]),n) if isinstance(n.op,ast.Div) else n
        tree=ast.fix_missing_locations(Division().visit(ast.parse(super().expression(tokens))))
        def divide(a,b):return (abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)
        self.calls['__divide']=divide
        return ast.unparse(tree)


def harness(records=(),flags=(),extras=(),helper_source='',stock=STOCK,raid=RAID,**cb):
    item=render(stock,records,raid)
    constants={'greed_div':1,'reward_multiplier':1,'attack_flag_loyalty_mod':1,'attack_flag_mod':1,
        'explore_flag_mod':1,'RewardFlags':9,'ATTRIB_rewardcost':10,'ATTRIB_targetID':11,
        'Intent_Going_To_Explore_Flag':21,'Intent_Going_To_Attack_Flag':22,'Intent_Raiding':23,
        'WHP_DawnfallScoringDistance':100,'NotMyTeam':30}
    source=re.sub(r'#([A-Za-z_][A-Za-z0-9_]*)',lambda m:str(next(v for k,v in constants.items() if k.lower()==m[1].lower())),item.text+'\n'+helper_source)
    vm=RewardHarness(source);hero=Actor(greed=100,loyalty=0,basicscript='basic',type='hero',player=1)
    events=[];eval_calls=[];travel_calls=[]
    vm.calls.update(listobjects=lambda h,kind,radius,out,mask:out.extend(extras if kind.lower()=='lair' else flags),
        getattribute=lambda a,k:a['cost' if k==10 else 'target'],
        distancebetweenagents=lambda h,f:f.fields.get('distance',100),listsize=len,
        agentnumber=lambda a:a,notvalid=lambda a:a is None,isdead=lambda a:not a.alive,
        getunitplayernumber=lambda a:a['player'],getplayerteamnumber=lambda a:a['player'],
        target_eval=lambda h,t:eval_calls.append(t) or 7,debugout=lambda *args:None,
        specifyintent=lambda h,i:events.append(('intent',i)),setparent=lambda h,f:events.append(('parent',f)),
        locationof=lambda f:(1,2),move=lambda *a:events.append(('move',)),say=lambda *a:None,
        attack_object=lambda:None,travel_to=lambda:None)
    vm.calls.update(provider_flag_eligible=lambda h,f:f.fields.get('allowed',True),
        provider_flag_priority=lambda h,f:f.fields.get('priority',False),
        provider_attack_distance=lambda h,t:travel_calls.append(t) or t.fields.get('travel',0),
        provider_target_evaluation=lambda h,t,value,travel:value+3,
        provider_flag_incentive=lambda h,f,t,score,travel:10,
        provider_extra_candidates=lambda h:list(extras),provider_extra_eligible=lambda h,t:True,
        provider_extra_score=lambda h,t,travel:t.fields.get('score',100))
    vm.calls.update(cb)
    return vm,hero,events,eval_calls,travel_calls


def flag(target=None,**values):
    fields=dict(title='flag_attack',heroes=[],cost=100,player=1,target=target or Actor(type='lair',player=2))
    fields.update(values)
    return Actor(**fields)


class RewardTests(unittest.TestCase):
    def test_metadata_roundtrip_and_invalid_phases(self):
        f=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        value={'schema_version':3,'mod_id':'{'+OWNER_A+'}','internal_name':'Test','display_name':'Test',
               'custom_buildings':[],'runtime_features':[],'source_contributions':[mapping(f)]}
        definition=parse_mod_definition(value)
        self.assertEqual(mod_definition_mapping(definition),value)
        for delta in ({'callbacks':{'unknown':'Bad'}},{'priority_multiplier':0},{'unexpected':True}):
            with self.assertRaises(ValueError):parse({**mapping(f),**delta})
        extra=feature('extra',('extra_candidates','extra_eligible','extra_score'),extra_dispatch='stock.raid_lair',suppress_player_attack_flags=True)
        broken=mapping(extra);broken.pop('suppress_player_attack_flags')
        with self.assertRaises(ValueError):parse(broken)

    def test_veto_bonus_priority_and_record_order(self):
        a=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        b=feature('bonus',('flag_incentive',))
        records=((OWNER_A,a),(OWNER_B,b))
        self.assertEqual(_tokens(render(STOCK,records,RAID).text),_tokens(render(STOCK,tuple(reversed(records)),RAID).text))
        rejected=flag(allowed=False,priority=True); allowed=flag()
        vm,hero,events,_,_=harness(records,[rejected,allowed])
        self.assertTrue(vm.call('check_rewards',hero,False))
        self.assertIs(events[-1][1],allowed)
        for alone in ((),((OWNER_A,a),),((OWNER_B,b),),records):
            vm,hero,events,_,_=harness(alone,[flag()])
            self.assertTrue(vm.call('check_rewards',hero,False))

    def test_attack_cache_single_eval_and_no_attack_guard_preservation(self):
        f=feature('travel',('attack_distance','target_evaluation','flag_incentive'))
        target=Actor(type='hero',player=2,travel=100)
        flags=[flag(target,distance=200),flag(target,distance=300)]
        vm,h,_,evals,travel=harness(((OWNER_B,f),),flags)
        self.assertTrue(vm.call('check_rewards',h,False))
        self.assertEqual(evals,[target,target]);self.assertEqual(travel,[target])
        vm,h,events,evals,travel=harness(((OWNER_B,f),),flags)
        self.assertFalse(vm.call('check_rewards',h,True));self.assertFalse(evals or travel or events)
        guard=flag();guard['title']='flag_guard'
        vm,h,events,_,_=harness(((OWNER_B,f),),[guard])
        self.assertTrue(vm.call('check_rewards',h,True));self.assertEqual(events[0],('intent',22))

    def test_extra_suppression_ties_and_stock_dispatch(self):
        extra=feature('extra',('extra_candidates','extra_eligible','extra_score'),extra_dispatch='stock.raid_lair',suppress_player_attack_flags=True)
        membership=feature('membership',('flag_eligible',))
        target=Actor(type='lair',player=2,score=100)
        for allowed in (True,False):
            f=flag(target,allowed=allowed)
            vm,h,events,_,_=harness(((OWNER_A,membership),(OWNER_B,extra)),[f],[target])
            self.assertEqual(vm.call('check_rewards',h,False),allowed)
            self.assertNotIn(('intent',23),events)
        vm,h,events,_,_=harness(((OWNER_B,extra),),[],[target])
        self.assertTrue(vm.call('check_rewards',h,False));self.assertEqual(events,[('intent',23)])
        self.assertIs(h['target'],target)
        winner=flag()
        vm,h,events,_,_=harness(((OWNER_B,extra),),[winner],[target])
        self.assertTrue(vm.call('check_rewards',h,False));self.assertEqual(events[-1],('parent',winner))
        vm,h,events,_,_=harness(((OWNER_B,extra),),[],[target])
        self.assertFalse(vm.call('check_rewards',h,True));self.assertFalse(events)

    def test_eligible_flag_suppression_keeps_independent_nonmember_incentive(self):
        extra=feature('extra',('extra_candidates','extra_eligible','extra_score'),
            extra_dispatch='stock.raid_lair',suppress_player_attack_flags='eligible')
        membership=feature('membership',('flag_eligible',))
        records=((OWNER_A,membership),(OWNER_B,extra))
        for allowed in (False,True):
            target=Actor(type='lair',player=2,score=1000)
            marked=flag(target,allowed=allowed)
            observed=[]
            vm,h,events,_,_=harness(records,[marked],[target],
                provider_flag_eligible=lambda h,f:observed.append(f) or f['allowed'])
            self.assertTrue(vm.call('check_rewards',h,False))
            self.assertEqual(observed,[marked])
            self.assertEqual(events, [('intent',22),('parent',marked)] if allowed else [('intent',23)])
            self.assertEqual(len(marked['heroes']),1 if allowed else 0)
        # Unrelated flag titles never suppress the independent lair candidate.
        for title in ('flag_explore','flag_guard'):
            target=Actor(type='lair',player=2,score=1000)
            vm,h,events,_,_=harness(records,[flag(target,title=title,allowed=True)],[target])
            self.assertTrue(vm.call('check_rewards',h,False));self.assertEqual(events,[('intent',23)])

    def test_declaration_proof_and_exact_preferred_body(self):
        a=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        b=feature('bonus',('flag_incentive',))
        packages=[];candidates=[]
        for owner,f in ((OWNER_A,a),(OWNER_B,b)):
            item=render(STOCK,((owner,f),),RAID)
            source=parse_gpl(item.text+'\n'+helpers(f).text)
            packages.append((owner,owner,(f,),(source,)))
            candidates.append(ScriptCandidate(owner,item,owner))
        loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID}
        session=ScriptReviewSession();c=review('majesty',packages,candidates,loader,session)
        self.assertIsNotNone(session.resolve(c))
        changed=replace(candidates[1],item=parse_gpl('function check_rewards(agent thisagent,boolean no_attack) is boolean declare begin return False; end').require(*KEY))
        # A single preference retains the entire current function, even if its
        # declaration no longer accounts for it. No losing hooks are reinserted.
        session=ScriptReviewSession({pair_key(OWNER_A,OWNER_B):OWNER_B})
        c=review('majesty',packages,(candidates[0],changed),loader,session)
        self.assertEqual(session.resolve(c).text,changed.item.text)

    def test_callback_ownership_and_dispatch_source_guard(self):
        f=feature('membership',('flag_eligible',))
        with self.assertRaisesRegex(ValueError,'package-owned'):
            validate(((OWNER_A,'a',(f,),()),(OWNER_B,'b',(),(helpers(f),))))
        extra=feature('extra',('extra_candidates','extra_eligible','extra_score'),extra_dispatch='stock.raid_lair',suppress_player_attack_flags=True)
        with self.assertRaises(FunctionMergeError):render(STOCK,((OWNER_A,extra),),replace(RAID,text=RAID.text.replace('#Intent_Raiding','#Intent_Other')))

    def test_bound_local_proof_accepts_renaming_but_rejects_behavior_changes(self):
        f=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        expected=render(STOCK,((OWNER_A,f),),RAID)
        self.assertEqual(expected.text,render(STOCK,(('{'+OWNER_A.upper()+'}',f),),RAID).text)
        # Author-local names and formal spellings are not semantic dependencies.
        renamed=replace(expected,text=re.sub(r'\bMM_RS_Allowed\b','AuthorAllowed',expected.text).replace('thisagent','Hero'))
        self.assertTrue(equivalent(expected,renamed))
        self.assertFalse(equivalent(expected,replace(renamed,text=renamed.text.replace('score * 2','score * 3'))))
        self.assertFalse(equivalent(expected,replace(renamed,text=renamed.text.replace('$provider_flag_eligible','$Other_Query'))))

    def test_competing_target_replacements_require_preference(self):
        packages=[];candidates=[]
        for owner,prefix in ((OWNER_A,'First'),(OWNER_B,'Second')):
            f=parse({'type':TYPE,'feature_key':prefix,'callbacks':{'target_evaluation':prefix+'_Evaluation'}})
            item=render(STOCK,((owner,f),),RAID)
            packages.append((owner,owner,(f,),(parse_gpl(item.text+'\n'+helpers(f).text),)))
            candidates.append(ScriptCandidate(owner,item,owner))
        loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID}
        session=ScriptReviewSession()
        conflict=review('majesty',packages,candidates,loader,session)
        self.assertIsNone(session.resolve(conflict))
        self.assertTrue(session.unresolved)
        for candidate in candidates:
            selected=ScriptReviewSession({pair_key(OWNER_A,OWNER_B):candidate.owner})
            conflict=review('majesty',packages,candidates,loader,selected)
            self.assertEqual(selected.resolve(conflict).text,candidate.item.text)

    def test_marked_guard_priority_and_zero_threshold(self):
        f=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        guard=flag(title='flag_guard',cost=10,priority=True)
        alternative=flag(cost=15)
        vm,h,events,_,_=harness(((OWNER_A,f),),[guard,alternative])
        self.assertTrue(vm.call('check_rewards',h,False));self.assertIs(events[-1][1],guard)
        for cost in (-1,0,1):
            vm,h,events,_,_=harness((),[flag(cost=cost)])
            self.assertFalse(vm.call('check_rewards',h,False));self.assertFalse(events)

    def test_stock_dispatch_is_literal_and_extra_dead_targets_decline(self):
        f=feature('extra',('extra_candidates','extra_eligible','extra_score'),extra_dispatch='stock.raid_lair',suppress_player_attack_flags=True)
        result=render(STOCK,((OWNER_A,f),),RAID)
        self.assertEqual(_Parser(result.text).function()[2][-2:],_Parser(STOCK.text).function()[2][-2:])
        target=Actor(type='lair',player=2,score=1000);target.alive=False
        vm,h,events,_,_=harness(((OWNER_A,f),),[],[target])
        self.assertFalse(vm.call('check_rewards',h,False));self.assertFalse(events)

    def test_production_review_source_path_no_profile_build(self):
        from types import SimpleNamespace as N
        from majesty_cam.compose import merge_gpl_resources
        a=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        b=feature('bonus',('flag_incentive',))
        def inventory(owner,f):
            root=render(STOCK,((owner,f),),RAID)
            source=parse_gpl(root.text+'\n'+helpers(f).text)
            definition=N(runtime_features=(),custom_buildings=(),mod_id=owner,source_contributions=(f,))
            return N(selected=N(alias=owner,package=N(definition=definition,mod_id=owner,display_name=owner),semantic_passthrough=False),
                     semantic_sources=(source,),gpl_loads=(),descriptions=())
        session=ScriptReviewSession()
        result=merge_gpl_resources((inventory(OWNER_A,a),inventory(OWNER_B,b)),script_review=session,script_dataset='majesty',
            stock_function_loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID})
        output=result.resume() if hasattr(result,'resume') else result
        actual=parse_gpl(output.source_set.gpl_text).require(*KEY)
        expected=render(STOCK,((OWNER_A,a),(OWNER_B,b)),RAID)
        self.assertEqual(_tokens(actual.text),_tokens(expected.text))

    def test_production_preference_does_not_reinsert_losing_contributions(self):
        from types import SimpleNamespace as N
        from majesty_cam.compose import merge_gpl_resources
        f=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        declared=render(STOCK,((OWNER_A,f),),RAID)
        opaque=parse_gpl('function check_rewards(agent thisagent,boolean no_attack) is boolean declare begin return False; end').require(*KEY)
        inventories=[]
        for owner,root,features,extra in ((OWNER_A,declared,(f,),helpers(f).text),(OWNER_B,opaque,(),'')):
            source=parse_gpl(root.text+'\n'+extra)
            definition=N(runtime_features=(),custom_buildings=(),mod_id=owner,source_contributions=features)
            inventories.append(N(selected=N(alias=owner,package=N(definition=definition,mod_id=owner,display_name=owner),semantic_passthrough=False),
                semantic_sources=(source,),gpl_loads=(),descriptions=()))
        for winner,expected in ((OWNER_A,declared),(OWNER_B,opaque)):
            with self.subTest(winner=winner):
                session=ScriptReviewSession({pair_key(OWNER_A,OWNER_B):winner})
                result=merge_gpl_resources(tuple(inventories),script_review=session,script_dataset='majesty',
                    stock_function_loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID})
                output=result.resume() if hasattr(result,'resume') else result
                session.require_resolved()
                actual=parse_gpl(output.source_set.gpl_text).require(*KEY)
                self.assertEqual(_tokens(actual.text),_tokens(expected.text))

    def test_native_standard_component_keeps_expansion_scope_all_three_sources(self):
        from types import SimpleNamespace as N
        from tempfile import TemporaryDirectory
        from majesty_cam.compose import merge_gpl_resources
        from majesty_cam.standard_scripts import StandardScripts,Providers
        a=feature('membership',('flag_eligible','flag_priority'),priority_multiplier=2)
        b=feature('bonus',('flag_incentive',))
        gog=Path('C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD')
        for branch,game in (('public',GAME),('beta2',GAME),('gog',gog)):
            for scope,folder,prefix in (('majesty','GPL',''),('majestyexpansion','GPLMx','mx_')):
                with self.subTest(branch=branch,scope=scope),TemporaryDirectory() as tmp:
                    modules=game/'SDK/OriginalQuests'/folder/'DecisionTrees/Modules'
                    stock=parse_gpl((modules/(prefix+'check_rewards.gpl')).read_text(encoding='cp1252')).require(*KEY)
                    raid=parse_gpl((modules/(prefix+'raid_lair.gpl')).read_text(encoding='cp1252')).require(DefinitionKind.FUNCTION,'raid_lair')
                    loader=lambda names:{KEY:stock,(DefinitionKind.FUNCTION,'raid_lair'):raid}
                    native_source=parse_gpl(render(stock,((OWNER_A,a),),raid).text+'\n'+helpers(a).text)
                    package=N(root=Path(tmp),mod_id=OWNER_A,definition=N(source_contributions=()))
                    native=StandardScripts('Native guild',package,(),(native_source,),(),(),bases=('majestyexpansion',),source_contributions=(a,))
                    providers=Providers((native,),loader,GAME/'SDK/Gplbcc.exe',scope)
                    source=parse_gpl(render(stock,((OWNER_B,b),),raid).text+'\n'+helpers(b).text)
                    definition=N(runtime_features=(),custom_buildings=(),mod_id=OWNER_B,source_contributions=(b,))
                    inventory=N(selected=N(alias=OWNER_B,package=N(definition=definition,mod_id=OWNER_B,display_name=OWNER_B),semantic_passthrough=False),
                        semantic_sources=(source,),gpl_loads=(),descriptions=())
                    session=ScriptReviewSession()
                    result=merge_gpl_resources((inventory,),script_review=session,script_dataset=scope,
                        stock_function_loader=loader,standard_providers=providers)
                    output=result.resume() if hasattr(result,'resume') else result
                    actual=parse_gpl(output.source_set.gpl_text).require(*KEY)
                    contributions=((OWNER_A,a),(OWNER_B,b)) if scope=='majestyexpansion' else ((OWNER_B,b),)
                    self.assertEqual(_tokens(actual.text),_tokens(render(stock,contributions,raid).text))


if __name__=='__main__':unittest.main()
