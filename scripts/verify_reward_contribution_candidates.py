"""Actual candidate GPL/BCD/source-review checks, not a Manager profile build."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace as N
from tempfile import TemporaryDirectory
from majesty_cam.package import load_package,GplLoad
from majesty_cam.gpl import DefinitionKind,SemanticMergeResult,parse_gpl
from majesty_cam.gpl_function_merge import _tokens
from majesty_cam.compose import merge_gpl_resources,_parse_inventory_gpl_sources,compile_gpl
from majesty_cam.standard_scripts import read,Providers,StandardScripts,verify as verify_sources,for_dataset
from majesty_cam.reward_contributions import KEY,render,equivalent
from majesty_cam.script_review import ScriptReviewSession


def behavior(stock,raid,records,items):
    """Execute actual thin adapters; world/native queries remain explicit doubles."""
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
    from test_reward_contributions import harness,Actor,flag
    names={name.casefold() for _,feature in records for _,name in feature.callbacks}
    from majesty_cam.reward_factoring import FactoredReward
    factors=[f for _,f in records if isinstance(f,FactoredReward)]
    names.update(f.helper.normalized_name for f in factors)
    names.add('whp_breachincentivescore')
    source='\n'.join(items[(DefinitionKind.FUNCTION,name)].text for name in sorted(names))
    # Only substitute the proven literal in the source-execution double; the
    # production compiler fixture below keeps its real source-owned expression.
    for f in factors:
        original=items[(DefinitionKind.FUNCTION,f.original_helper)]
        constants=re.findall(r'#[A-Za-z_][A-Za-z0-9_]*',original.text)
        for name in constants:
            item=items.get((DefinitionKind.EXPRESSION,name.casefold()))
            if item is not None:
                from majesty_cam.gpl_function_merge import _tokens
                tokens=_tokens(item.text)
                if len(tokens)==3 and tokens[-1]==str(f.multiplier):
                    source=re.sub(re.escape(name)+r'\b',str(f.multiplier),source,flags=re.I)
    results=[]
    def run(label,flags,extras=(),home='member',no_attack=False,expected=True,winner=None,raid_target=None):
        queries=[]
        vm,hero,events,evaluations,_=harness(records,flags,extras,helper_source=source,stock=stock,raid=raid,
            hasattribute=lambda key,a:isinstance(a,Actor) and key.lower() in a.fields,
            isvalidgamepiece=lambda a:isinstance(a,Actor) and a.alive,
            whp_dawnfallcanreach=lambda h,t:queries.append(t) or t.fields.get('ready',False),
            whp_breachallows=lambda h,t:t.fields.get('breached',False))
        if home!='missing':
            hero['home']=None if home=='null' else Actor(title='Other' if home=='wrong' else 'Adventurers_Guild',player=2 if home=='foreign' else 1)
            if home=='dead':hero['home'].alive=False
        assert vm.call('check_rewards',hero,no_attack)==expected,label
        if winner is not None:assert events[-1]==('parent',winner),label
        if raid_target is not None:
            assert events==[('intent',23)] and hero['target'] is raid_target,label
        # Same target is queried once even when represented by repeated flags.
        assert len(queries)==len({id(q) for q in queries}),label
        results.append({'case':label,'reachabilityQueries':len(queries),'stockEvaluations':len(evaluations)})
    target=Actor(type='lair',player=2,breached=True,distance=1000,ready=True)
    eligible_suppression=any(f.suppress_player_attack_flags=='eligible' for _,f in records)
    for home in ('missing','null','wrong','foreign','dead','member'):
        marked=flag(target,WE_AG_Flag_Guild=1)
        independent=eligible_suppression and home!='member'
        run('marked-'+home,[marked],[target],home=home,expected=home=='member' or independent,
            winner=marked if home=='member' else None,raid_target=target if independent else None)
    marked=flag(title='flag_guard',cost=10,WE_AG_Flag_Guild=1)
    run('guard-priority-before-alternative',[marked,flag(cost=15)],winner=marked,no_attack=True)
    run('breach-without-flag',[],[target],raid_target=target)
    plain=flag(target)
    run('player-flag-remains-stock-dispatch',[plain],[target],winner=plain)
    plain=flag(target)
    repeat=flag(target,distance=900)
    run('repeated-target-readiness-cache',[plain,repeat],[target],winner=plain)
    run('no-attack-blocks-extra',[],[target],no_attack=True,expected=False)
    expired=Actor(type='lair',player=2,breached=False)
    run('expired-effect-declines',[],[expired],expected=False)
    target.fields['ready']=False
    run('unready-caster-keeps-breach-incentive',[],[target],raid_target=target)
    return {'cases':results,'actualHelpers':sorted(names),
        'limits':'Source execution with supplied world/native/readiness/expiry doubles and safe-sized integer inputs; not native gameplay or payout acceptance.'}


def verify(merge_root,native_root,work,*,infer=False,input_receipt=None):
    merge_root,native_root=Path(merge_root).resolve(),Path(native_root).resolve()
    repo=Path(__file__).resolve().parents[1]
    work=Path(work).resolve()
    if repo/'local' not in work.parents:raise ValueError('Evidence must remain under private local/')
    work.mkdir(parents=True,exist_ok=True)
    def files(root):
        return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.rglob('*')) if p.is_file()}
    frozen={str(p):files(p) for p in (merge_root,native_root)}
    if infer:
        assert input_receipt is not None,'Unchanged-input proof requires the owning candidate pins'
        pins=json.loads(Path(input_receipt).read_text())
        assert frozen[str(merge_root)]==pins['records']['witch_candidate']['files']
        native_pins=pins.get('native_candidate') or pins['unchanged_alpha_candidate']
        assert frozen[str(native_root)]==native_pins['files']
    implementation={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (repo/'src').rglob('*.py')}
    package=load_package(merge_root)
    manifest=next(Path(native_root).glob('*.mmxml'))
    from majesty_cam.manager.catalog import scan_catalog,CatalogKind
    native_entry,=scan_catalog(workshop_roots=[native_root]).entries
    assert native_entry.kind==CatalogKind.STANDARD and native_entry.selectable
    native=read(native_entry)
    assert bool(native.source_contributions)!=infer
    if not infer:assert not native.package.definition.runtime_features
    loads=tuple(g for d in package.datasets for load in d.loads for g in load.gpl)
    source_paths=tuple(dict.fromkeys(p.absolute_path for g in loads for p in g.sources))
    targets=tuple((g.target.absolute_path,g.target.absolute_path.read_bytes()) for g in loads)
    payloads=tuple((p,p.read_bytes()) for p in source_paths)
    digests=tuple((str(p),hashlib.sha256(b).hexdigest()) for p,b in (*payloads,*targets))
    proof=StandardScripts(package.display_name,package,loads,(),(),source_paths,
        bases=('any',),digests=digests,payloads=payloads,compiled_payloads=targets)
    # Isolate the source contribution boundary. Other unchanged runtime features
    # belong to existing native/composition tests; this is not a full mod Prepare.
    definition=replace(package.definition,runtime_features=(),runtime_capabilities=(),custom_buildings=())
    fixture_package=replace(package,definition=definition)
    owner=package.mod_id.strip('{}').casefold()
    native_owner=native.package.mod_id.strip('{}').casefold()
    inventory=N(selected=N(alias=owner,package=fixture_package,semantic_passthrough=False),
        gpl_loads=loads,descriptions=())
    cases=[]
    for branch,game_var in (('public','MAJESTY_BCD_GAME'),('beta2','MAJESTY_BCD_GAME'),('gog','MAJESTY_BCD_GOG_GAME')):
        game=Path(os.environ[game_var]);compiler=game/'SDK/Gplbcc.exe'
        verify_sources(proof,compiler)
        for scope,folder,prefix in (('majesty','GPL',''),('majestyexpansion','GPLMx','mx_')):
            modules=game/'SDK/OriginalQuests'/folder/'DecisionTrees/Modules'
            stock=parse_gpl((modules/(prefix+'check_rewards.gpl')).read_text(encoding='cp1252')).require(*KEY)
            raid=parse_gpl((modules/(prefix+'raid_lair.gpl')).read_text(encoding='cp1252')).require(DefinitionKind.FUNCTION,'raid_lair')
            loader=lambda names:{KEY:stock,(DefinitionKind.FUNCTION,'raid_lair'):raid}
            providers=Providers((native,),loader,compiler,scope)
            session=ScriptReviewSession()
            result=merge_gpl_resources((inventory,),stock_function_loader=loader,
                standard_providers=providers,script_review=session,script_dataset=scope,
                infer_reward_factors=infer)
            session.require_resolved()
            output=result.resume() if hasattr(result,'resume') else result
            parsed=parse_gpl(output.source_set.gpl_text)
            actual=parsed.require(*KEY)
            records=[(owner,f) for f in definition.source_contributions]
            active=for_dataset((native,),scope)
            if active:records.extend((native_owner,f) for f in native.source_contributions)
            factored=None
            if infer and active:
                from majesty_cam.reward_factoring import InferenceScope
                inference=InferenceScope(providers,(inventory,))
                factored=inference.factor(native_owner,native.owner(KEY)[1],stock)
                assert factored is not None,inference.declined
                records.append((native_owner,factored))
            expected=render(stock,records,raid)
            if not equivalent(expected,actual):
                (work/'actual-selector.gpl').write_text(actual.text,encoding='utf8')
                (work/'expected-selector.gpl').write_text(expected.text,encoding='utf8')
                raise AssertionError('production output differs from declared expansion: '+branch+'/'+scope+' owners='+str(
                    [(c.name,session.selected_owners(c)) for c in session.observed]))
            for f in native.source_contributions:
                for _,symbol in f.callbacks:
                    assert (symbol.casefold() in actual.text.casefold())==bool(active), 'Standard scope leaked'
            # Native helper definitions are added only to this disposable language
            # compiler fixture; the real Standard component remains independently loaded.
            items={i.key:i for i in parsed.items}
            for provider in active:
                for key,item in provider.items.items():
                    if key!=KEY and key not in items:items[key]=item
            if factored:
                assert parsed.require(*factored.helper.key).text==factored.helper.text
                assert not re.search(r'#[A-Za-z_]',factored.helper.text),'Private factor must not need a native project expression'
                automatic=[r for r in output.function_instruction_merges if r.get('automatic_reward_factor')]
                assert len(automatic)==1 and automatic[0]['helper']==factored.helper.name
                # Reverse the actual two candidate definitions at the same
                # production review boundary; Standard/Merge are distinct
                # categories, not a single input tuple that can be reversed.
                from majesty_cam.reward_contributions import review
                from majesty_cam.script_review import ScriptCandidate,pair_key
                owned={i.key:i for source in _parse_inventory_gpl_sources(inventory) for i in source.items}
                candidates=(ScriptCandidate(package.display_name,owned[KEY],owner),
                            ScriptCandidate(native.name,native.owner(KEY)[1],native_owner))
                reverse_session=ScriptReviewSession()
                reverse_scope=InferenceScope(providers,(inventory,))
                conflict=review(scope,((owner,package.display_name,definition.source_contributions,
                    _parse_inventory_gpl_sources(inventory)),),tuple(reversed(candidates)),loader,
                    reverse_session,inference=reverse_scope)
                reverse_session.require_resolved()
                assert equivalent(reverse_session.resolve(conflict),actual)
                # With no proven factor admitted, this exact pair must retain
                # either chosen whole authored body and emit no losing helper.
                for winner in (owner,native_owner):
                    fallback_session=ScriptReviewSession({pair_key(owner,native_owner):winner})
                    fallback=merge_gpl_resources((inventory,),stock_function_loader=loader,
                        standard_providers=Providers((native,),loader,compiler,scope),
                        script_review=fallback_session,script_dataset=scope,infer_reward_factors=False)
                    fallback_session.require_resolved()
                    fallback=fallback.resume() if hasattr(fallback,'resume') else fallback
                    fallback_source=parse_gpl(fallback.source_set.gpl_text)
                    chosen=owned[KEY] if winner==owner else native.owner(KEY)[1]
                    decision=next(c for c in fallback_session.observed if c.key==KEY)
                    assert fallback_session.resolve(decision).text.replace('\r','')==chosen.text.replace('\r','')
                    emitted={i.key:i for i in fallback_source.items}.get(KEY)
                    # An exact native winner is deliberately pruned: its BCD
                    # remains loaded by the Standard package, without a clone.
                    assert emitted is not None or winner==native_owner
                    if emitted is not None and emitted.text.replace('\r','')!=chosen.text.replace('\r',''):
                        (work/'fallback-actual.gpl').write_text(emitted.text)
                        (work/'fallback-expected.gpl').write_text(chosen.text)
                        raise AssertionError('Preferred body differs: '+winner)
                    assert not any(i.name.startswith('MM_RewardFactor_') for i in fallback_source.items)
            behavior_receipt=behavior(stock,raid,records,items) if active else None
            source=SemanticMergeResult(tuple(items.values()),()).emit_project_source_set('RewardLanguage.gpl','RewardLanguage.dat')
            with TemporaryDirectory(prefix=branch+'-'+scope+'-',dir=work) as temporary:
                generated=compile_gpl(output.source_set,compiler,Path(temporary)/'generated',stem='GeneratedReward')
                generated_hash=hashlib.sha256(generated.target.read_bytes()).hexdigest()
                target=compile_gpl(source,compiler,Path(temporary)/'language',stem='RewardLanguage')
                target_hash=hashlib.sha256(target.target.read_bytes()).hexdigest()
            cases.append({'branch':branch,'scope':scope,'nativeContributionsActive':bool(active),
                'nativeScope':list(native.bases),'selectorSha256':hashlib.sha256(actual.text.encode()).hexdigest(),
                'languageTargetSha256':target_hash,
                'productionGeneratedTargetSha256':generated_hash,
                'adapterBehavior':behavior_receipt,
                'unresolvedChoices':len(session.unresolved),'standardSourceVerified':bool(active)})
    receipt={'schema':1,'mergeCandidate':str(Path(merge_root).resolve()),'standardCandidate':str(Path(native_root).resolve()),
        'mergeInputDigests':digests,'nativeInputDigests':native.digests,'cases':cases,
        'compiledMergeSourceVerified':True,'automaticFactoring':infer,'profileConstructed':False,'deployed':False,
        'limits':'Actual source declarations, full standalone source/BCD proof, production source-review and isolated language compilation. Other runtime features are isolated out; no complete profile or native gameplay/save-load acceptance.'}
    assert frozen=={str(p):files(p) for p in (merge_root,native_root)},'Candidate input changed during verification'
    assert implementation=={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (repo/'src').rglob('*.py')},'Manager implementation changed during verification'
    from verify_regression import fixture_evidence
    receipt.update(inputFiles=frozen,implementation=implementation,fixtures=fixture_evidence(),
                   inputReceiptSha256=hashlib.sha256(Path(input_receipt).read_bytes()).hexdigest() if input_receipt else None,
                   reversedActualCandidates=True if infer else None,
                   exactPreferredBodiesWithoutLosingAdapters=True if infer else None)
    (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--merge-root',type=Path,required=True);p.add_argument('--native-root',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--infer',action='store_true',help='Prove an unchanged Standard selector instead of author declarations')
    p.add_argument('--input-receipt',type=Path)
    a=p.parse_args();verify(a.merge_root,a.native_root,a.work,infer=a.infer,input_receipt=a.input_receipt)
