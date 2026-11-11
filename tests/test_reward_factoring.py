from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from majesty_cam.gpl import parse_gpl,DefinitionKind
from majesty_cam.damage_contributions import _Function
from majesty_cam.gpl_function_merge import FunctionMergeError,_Parser,_tokens
from majesty_cam.reward_factoring import infer,InferenceScope,KEY,QUERIES
from majesty_cam.reward_contributions import render,review
from majesty_cam.standard_scripts import StandardScripts,Providers
from majesty_cam.script_review import ScriptCandidate,ScriptReviewSession,pair_key
from test_reward_contributions import STOCK,RAID,OWNER_A,OWNER_B,feature,helpers,harness,Actor,flag


HELPER='''function OfferWeight(agent Actor, agent Offer, integer Value) is integer
declare agent Home; integer Priority;
begin
    if ($HasAttribute("home",Actor) == False) return 0;
    Home = Actor's "home";
    if ($IsValidGamePiece(Home) == False) return 0;
    if (Home's "title" != "TestHome") return 0;
    if ($GetUnitPlayerNumber(Home) != $GetUnitPlayerNumber(Offer)) return 0;
    Priority = #ExamplePriority;
    return Value * Priority;
end
'''


def fixture(helper=HELPER,constant=2,insertion=None,extra=''):
    fn=_Function(STOCK)
    insertion=insertion or 'if ($HasAttribute("OfferMarker",flag)) score = $OfferWeight(thisagent,flag,score);'
    fn.once('$debugout(score);',before=insertion)
    caller=fn.emit()
    source=parse_gpl(caller.text+'\n'+helper+f'\nexpression #ExamplePriority {constant}\n'+extra)
    provider=StandardScripts('Unchanged native source',NS(mod_id=OWNER_A,root=Path('.')),(),(source,),(),())
    return provider,caller


def context(provider,others=()):
    loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID}
    native=Providers((provider,*others),loader,Path('compiler'),'majestyexpansion')
    return InferenceScope(native,())


def factor(provider,caller):
    scope=context(provider)
    with patch('majesty_cam.standard_scripts.verify',return_value=True):
        result=scope.factor(OWNER_A,caller,STOCK)
    return result,scope


class RewardFactoringTests(unittest.TestCase):
    def test_generic_names_constants_and_complete_helper_clone(self):
        for value in (1,2,3,32767):
            provider,caller=fixture(constant=value)
            result,scope=factor(provider,caller)
            self.assertIsNotNone(result,scope.declined)
            self.assertEqual(result.multiplier,value)
            old=_Parser(provider.items[(DefinitionKind.FUNCTION,'offerweight')].text).function()
            new=_Parser(result.helper.text).function()
            self.assertEqual(old[0][2:],new[0][2:])
            self.assertEqual(old[1],new[1])
            self.assertEqual(old[2][:-2],new[2][:-2])
            self.assertEqual(new[2][-2].head,('priority','=',str(value),';'))
            self.assertEqual(new[2][-1].head,('return','priority',';'))
        renamed=HELPER.replace('OfferWeight','AnotherFormula').replace('Actor','Subject').replace('Offer','Candidate').replace('Home','Residence')
        provider,caller=fixture(helper=renamed,insertion='if ($HasAttribute("DifferentMarker",flag)) score = $AnotherFormula(thisagent,flag,score);')
        result,scope=factor(provider,caller)
        self.assertIsNotNone(result,scope.declined)

    def test_mutation_unknown_calls_score_guards_and_hidden_edits_decline(self):
        changes=(HELPER.replace('"home",Actor','"home",Value'),
                 HELPER.replace('Home = Actor\'s "home";','Actor\'s "changed" = 1;'),
                 HELPER.replace('$IsValidGamePiece(Home)','$UnknownPredicate(Home)'),
                 HELPER.replace('return Value * Priority;','return Value + Priority;'),
                 HELPER.replace('return Value * Priority;','return Priority * Value;'),
                 HELPER.replace('Home = Actor\'s "home";','Home = Other;'),
                 HELPER.replace('Home = Actor\'s "home";','Home = Actor\'s "home"; $GiveGold(Actor,1);'))
        for text in changes:
            with self.subTest(text=text):
                provider,caller=fixture(helper=text)
                result,scope=factor(provider,caller)
                self.assertIsNone(result)
                self.assertIn(OWNER_A,scope.declined)
        provider,caller=fixture()
        changed=replace(caller,text=caller.text.replace('bestscore = 1','bestscore = 2'))
        self.assertIsNone(factor(provider,changed)[0])
        for value in (0,-1,32768):
            provider,caller=fixture(constant=value)
            self.assertIsNone(factor(provider,caller)[0])

    def test_query_helper_and_constant_overrides_even_opaque_decline(self):
        provider,caller=fixture()
        keys=[(DefinitionKind.FUNCTION,n) for n in (*QUERIES,'offerweight')]
        keys.append((DefinitionKind.EXPRESSION,'#examplepriority'))
        for key in keys:
            opaque=NS(package=NS(mod_id=OWNER_B),bases=('any',),compiled_keys={key})
            scope=context(provider,(opaque,))
            with patch('majesty_cam.standard_scripts.verify',return_value=True):
                self.assertIsNone(scope.factor(OWNER_A,caller,STOCK),key)
        scope=context(provider)
        with patch('majesty_cam.standard_scripts.verify',side_effect=ValueError('source/BCD differ')):
            self.assertIsNone(scope.factor(OWNER_A,caller,STOCK))

    def test_standalone_behavior_and_queries_match_for_all_marked_titles(self):
        provider,caller=fixture();proof,scope=factor(provider,caller)
        self.assertIsNotNone(proof,scope.declined)
        for title in ('flag_attack','flag_guard','flag_explore'):
            for home_state in ('missing','null','dead','wrong','foreign','member'):
                for marked in (False,True):
                    snapshots=[]
                    for factored in (False,True):
                        reward=flag(title=title,cost=30)
                        if marked:reward.fields['offermarker']=1
                        text=proof.helper.text if factored else HELPER
                        text=text.replace('#examplepriority','2').replace('#ExamplePriority','2')
                        vm,hero,events,_,_=harness(((OWNER_A,proof),) if factored else (),[reward],
                            helper_source=text,stock=STOCK if factored else caller)
                        if home_state!='missing':
                            home=None if home_state=='null' else Actor(title='Other' if home_state=='wrong' else 'TestHome',
                                player=2 if home_state=='foreign' else 1)
                            if home is not None and home_state=='dead':home.alive=False
                            hero.fields['home']=home
                        reads=[]
                        vm.calls.update(hasattribute=lambda name,actor:reads.append(('has',name.lower())) or name.lower() in actor.fields,
                            isvalidgamepiece=lambda actor:reads.append(('valid',)) or bool(actor is not None and actor.alive))
                        stock_owner=vm.calls['getunitplayernumber']
                        vm.calls['getunitplayernumber']=lambda actor:reads.append(('owner',)) or stock_owner(actor)
                        chosen=vm.call('check_rewards',hero,False)
                        snapshots.append((chosen,[e[0:2] for e in events if e[0]!='parent'],reads))
                    self.assertEqual(*snapshots,(title,home_state,marked))

    def test_combines_before_priority_and_reversed_order_with_exact_fallback(self):
        provider,caller=fixture()
        extra=feature('incentive',('flag_incentive',))
        authored=render(STOCK,((OWNER_B,extra),),RAID)
        packages=((OWNER_B,'Declared',(extra,),(helpers(extra),parse_gpl(authored.text))),)
        candidates=(ScriptCandidate('Original',caller,OWNER_A),ScriptCandidate('Declared',authored,OWNER_B))
        loader=lambda names:{KEY:STOCK,(DefinitionKind.FUNCTION,'raid_lair'):RAID}
        outputs=[]
        for values in (candidates,tuple(reversed(candidates))):
            scope=context(provider);session=ScriptReviewSession()
            with patch('majesty_cam.standard_scripts.verify',return_value=True):
                conflict=review('majestyexpansion',packages,values,loader,session,inference=scope)
                outputs.append(session.resolve(conflict).text)
            self.assertFalse(session.unresolved)
            self.assertEqual(len(scope.accepted),1)
        self.assertEqual(*outputs)
        bad,caller=fixture(helper=HELPER.replace('$IsValidGamePiece(Home)','$OpaqueQuery(Home)'))
        for winner in (OWNER_A,OWNER_B):
            scope=context(bad);session=ScriptReviewSession({pair_key(OWNER_A,OWNER_B):winner})
            with patch('majesty_cam.standard_scripts.verify',return_value=True):
                conflict=review('majestyexpansion',packages,candidates,loader,session,inference=scope)
                self.assertEqual(session.resolve(conflict).text,caller.text if winner==OWNER_A else authored.text)
            self.assertFalse(scope.accepted)

    def test_zero_stock_score_is_not_an_eligibility_veto(self):
        provider,caller=fixture();proof,scope=factor(provider,caller)
        self.assertIsNotNone(proof,scope.declined)
        incentive=feature('incentive',('flag_incentive',))
        for member in (False,True):
            reward=flag(cost=1,distance=100000,OfferMarker=1)
            source=proof.helper.text.replace('#examplepriority','2').replace('#ExamplePriority','2')
            vm,hero,events,_,_=harness(((OWNER_A,proof),(OWNER_B,incentive)),[reward],helper_source=source)
            if member:hero.fields['home']=Actor(title='TestHome',player=1)
            vm.calls.update(hasattribute=lambda name,a:name.lower() in a.fields,
                            isvalidgamepiece=lambda a:a is not None and a.alive)
            calls=[];original=vm.calls[proof.helper.normalized_name]
            vm.calls[proof.helper.normalized_name]=lambda *args:calls.append(args[1]) or original(*args)
            self.assertEqual(vm.call('check_rewards',hero,False),member)
            self.assertEqual(calls,[reward])
            self.assertEqual(any(e[0]=='parent' for e in events),member)
