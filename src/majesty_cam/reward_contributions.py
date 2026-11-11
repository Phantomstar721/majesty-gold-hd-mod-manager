"""Declared source composition at stock check_rewards; no runtime service."""
from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib
import re
from .gpl import DefinitionKind
from .gpl_function_merge import _tokens, _Parser, FunctionMergeError
from .damage_contributions import _Function, _nodes
from .spell_policy import signature

TYPE='stock.reward-selection.v1'
KEY=(DefinitionKind.FUNCTION,'check_rewards')
SIGNATURES={
    'flag_eligible': (('agent','agent'),'boolean'),
    'attack_distance': (('agent','agent'),'integer'),
    'target_evaluation': (('agent','agent','integer','integer'),'integer'),
    'flag_incentive': (('agent','agent','agent','integer','integer'),'integer'),
    'flag_priority': (('agent','agent'),'boolean'),
    'extra_candidates': (('agent',),'list'),
    'extra_eligible': (('agent','agent'),'boolean'),
    'extra_score': (('agent','agent','integer'),'integer'),
}
EXTRAS={'extra_candidates','extra_eligible','extra_score'}


@dataclass(frozen=True)
class RewardContribution:
    feature_key: str
    callbacks: tuple[tuple[str,str],...]
    priority_multiplier: int=1
    extra_dispatch: str | None=None
    suppress_player_attack_flags: bool | str=True


def parse(value):
    required={'type','feature_key','callbacks'}
    optional={'priority_multiplier','extra_dispatch','suppress_player_attack_flags'}
    if not isinstance(value,dict) or not required<=value.keys() or value.keys()-required-optional or value['type']!=TYPE:
        raise ValueError('invalid reward source contribution fields/type')
    key=value['feature_key']; callbacks=value['callbacks']
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}',key):
        raise ValueError('invalid reward contribution feature_key')
    if not isinstance(callbacks,dict) or not callbacks or callbacks.keys()-SIGNATURES.keys():
        raise ValueError('unknown or empty reward contribution callbacks')
    for symbol in callbacks.values():
        if not isinstance(symbol,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,47}',symbol) or symbol.lower().startswith('mm_'):
            raise ValueError('reward callback must be an unreserved GPL symbol')
    multiplier=value.get('priority_multiplier',1)
    if type(multiplier)is not int or not 1<=multiplier<=32767 or multiplier!=1 and 'flag_priority' not in callbacks:
        raise ValueError('reward priority needs a predicate and positive constant multiplier')
    extra=callbacks.keys()&EXTRAS
    dispatch=value.get('extra_dispatch')
    suppression=value.get('suppress_player_attack_flags',True)
    if extra and (extra!=EXTRAS or dispatch!='stock.raid_lair' or 'suppress_player_attack_flags' not in value) or not extra and dispatch is not None:
        raise ValueError('extra candidates require all three callbacks and stock.raid_lair dispatch')
    if not (type(suppression)is bool or suppression=='eligible') or 'suppress_player_attack_flags' in value and not extra:
        raise ValueError('attack flag suppression belongs to an extra candidate contribution')
    return RewardContribution(key,tuple(sorted(callbacks.items())),multiplier,dispatch,suppression)


def mapping(feature):
    value={'type':TYPE,'feature_key':feature.feature_key,'callbacks':dict(feature.callbacks)}
    if feature.priority_multiplier!=1:value['priority_multiplier']=feature.priority_multiplier
    if feature.extra_dispatch:
        value.update(extra_dispatch=feature.extra_dispatch,suppress_player_attack_flags=feature.suppress_player_attack_flags)
    if parse(value)!=feature:raise ValueError('reward contribution does not round-trip')
    return value


def equivalent(expected,actual):
    """Compare complete bound-local ASTs, not private variable spellings."""
    from .standard_scripts import _align_parameters
    aligned=_align_parameters(expected.text,actual.text)
    def canonical(text):
        header,locals_,body=_Parser(text).function()
        names={name:'<local:'+str(i)+'>' for i,name in enumerate(locals_)}
        def nodes(values):
            return tuple((tuple(names.get(t,t) if i==0 or n.head[i-1] not in ('$', '#') else t
                for i,t in enumerate(n.head)),nodes(n.body),nodes(n.otherwise)) for n in values)
        return header,tuple(locals_.values()),nodes(body)
    return canonical(expected.text)==canonical(aligned)


def validate(packages):
    """One package-owned helper per symbol; sources must already be admitted."""
    records=[]; functions={}; identities=set()
    for owner,label,features,sources in packages:
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    functions.setdefault(item.normalized_name,[]).append((owner,item))
        for f in features:
            mapping(f)
            identity=(owner,f.feature_key.casefold())
            if identity in identities:raise ValueError('duplicate reward contribution: '+str(identity))
            identities.add(identity);records.append((owner,f))
    for owner,f in records:
        for phase,name in f.callbacks:
            rows=functions.get(name.casefold(),())
            if len(rows)!=1 or rows[0][0]!=owner:
                raise ValueError(owner+': reward callback needs exactly one package-owned function: '+name)
            signature(rows[0][1],*SIGNATURES[phase])
    return tuple(sorted(records,key=lambda r:(r[0],r[1].feature_key.casefold())))


def render(stock, records, raid_lair=None):
    """Preserve stock nodes; insert only explicitly declared scoring phases."""
    from .reward_factoring import FactoredReward
    from .gpl_function_merge import _code
    if not records:return stock
    records=tuple(sorted(((owner.strip('{}').casefold(),f) for owner,f in records),key=lambda r:(r[0],r[1].feature_key.casefold())))
    fn=_Function(stock)
    signature(stock,('agent','boolean'),'boolean')
    if _tokens('function check_rewards(agent thisagent,boolean no_attack) is boolean')!=fn.header:
        raise FunctionMergeError('reward selector needs the stock parameter contract')
    def once(head,**kw):
        try:fn.once(head,**kw)
        except ValueError as e:raise FunctionMergeError(str(e).replace('damage calculation','reward selection')) from e
    def local(name,kind='integer'):fn.local(name,kind)
    local('MM_RS_Allowed','boolean');local('MM_RS_AttackValid','boolean')
    local('MM_RS_Evaluation'); local('MM_RS_Distance')
    states=[]
    eligible_suppression=any(f.suppress_player_attack_flags=='eligible' for _,f in records)
    if eligible_suppression:local('MM_RS_EligibleFlags','list')
    for owner,f in records:
        tag=hashlib.sha256((owner+':'+f.feature_key.casefold()).encode()).hexdigest()[:12]
        p='MM_RS_'+tag
        cb=dict(f.callbacks);states.append((f,p,cb))
        local(p+'_Travel')
        if isinstance(f,FactoredReward):
            local(p+'_Marked','boolean');local(p+'_Factor')
        if 'attack_distance' in cb:
            for n in ('_Targets','_Distances'):local(p+n,'list')
            local(p+'_Index');local(p+'_Found','boolean')
    def travel(p,cb,target):
        if 'attack_distance' not in cb:return p+'_Travel = 0;'
        return f'''
{p}_Travel = 0; {p}_Found = False; {p}_Index = 1;
while ({p}_Index <= $ListSize({p}_Targets)) do
    begin
        if ($ListMember({p}_Targets,{p}_Index) == {target})
            begin {p}_Travel = $ListMember({p}_Distances,{p}_Index); {p}_Found = True; end
        {p}_Index += 1;
    end
if ({p}_Found == False)
    begin
        {p}_Travel = ${cb['attack_distance']}(thisagent,{target});
        if ({p}_Travel < 0) {p}_Travel = 0;
        {p}_Targets << {target}; {p}_Distances << {p}_Travel;
    end
'''
    context=['MM_RS_AttackValid = (target != thisagent);','if (MM_RS_AttackValid) begin',
             'MM_RS_Distance = distance;']
    for _,p,cb in states:
        context.append(travel(p,cb,'target'))
        if 'attack_distance' in cb:
            context.append(f'if (({p}_Travel > 0) && ({p}_Travel < MM_RS_Distance)) MM_RS_Distance = {p}_Travel;')
    context += ['if (MM_RS_Distance < 100) MM_RS_Distance = 100;',
                'if (MM_RS_Distance != distance) score = (rewardcost * greedmod) / MM_RS_Distance;','end']
    once('foreach flag in flags do',inside='MM_RS_AttackValid = False; MM_RS_Allowed = True;')
    once('target = $agentnumber($getattribute(flag,#ATTRIB_targetID));',after='\n'.join(context))
    modifiers=[(p,cb['target_evaluation']) for _,p,cb in states if 'target_evaluation' in cb]
    if len(modifiers)>1:raise FunctionMergeError('overlapping reward target-evaluation replacements need a preferred provider')
    if modifiers:
        p,callback=modifiers[0]
        once('score += $target_eval(thisagent,target);',replacement=f'''
MM_RS_Evaluation = $target_eval(thisagent,target);
MM_RS_Evaluation = ${callback}(thisagent,target,MM_RS_Evaluation,{p}_Travel);
score += MM_RS_Evaluation;
''')
    phases=[]
    for f,p,cb in states:
        if isinstance(f,FactoredReward):
            phases.append(f'''{p}_Marked = False; {p}_Factor = 1;
if ({_code(f.condition)})
begin
    {p}_Marked = True;
    {p}_Factor = ${f.helper.name}(thisagent,flag,score);
    if ({p}_Factor == 0) begin MM_RS_Allowed = False; score = 0; end
end''')
        if 'flag_eligible' in cb:phases.append(f'if (${cb["flag_eligible"]}(thisagent,flag) == False) MM_RS_Allowed = False;')
    if eligible_suppression:
        phases.append('if (MM_RS_Allowed) MM_RS_EligibleFlags << flag;')
    for _,p,cb in states:
        if 'flag_incentive' in cb:
            phases.append(f'if (MM_RS_Allowed && MM_RS_AttackValid) score += ${cb["flag_incentive"]}(thisagent,flag,target,score,{p}_Travel);')
    for f,p,cb in states:
        if isinstance(f,FactoredReward):
            phases.append(f'if (MM_RS_Allowed && {p}_Marked) score = score * {p}_Factor;')
        if 'flag_priority' in cb:
            phases.append(f'if (MM_RS_Allowed) if (${cb["flag_priority"]}(thisagent,flag)) score = score * {f.priority_multiplier};')
    once('$debugout(score);',before='\n'.join(phases))
    count=0
    def guard(nodes):
        nonlocal count
        out=[]
        for n in nodes:
            n=replace(n,body=guard(n.body),otherwise=guard(n.otherwise))
            if n.head==_tokens('if (score > bestscore)'):
                count+=1;n=replace(_nodes('if (MM_RS_Allowed) begin end')[0],body=(n,))
            out.append(n)
        return tuple(out)
    fn.body=guard(fn.body)
    if count!=1:raise FunctionMergeError('stock reward winner comparison changed or ambiguous')
    extras=[s for s in states if s[0].extra_dispatch]
    if extras:
        if raid_lair is None:raise FunctionMergeError('extra candidates need the destination stock raid_lair source')
        clone='thisagent\'s "ActiveScript" = $Attack_object; thisagent\'s "Target" = easiest_lair; $SpecifyIntent(ThisAgent,#Intent_Raiding);'
        tokens=_tokens(raid_lair.text); fragment=_tokens(clone)
        if sum(tokens[i:i+len(fragment)]==fragment for i in range(len(tokens)-len(fragment)+1))!=1:
            raise FunctionMergeError('stock raid_lair dispatch changed or ambiguous')
        for n in ('MM_RS_Candidates',):local(n,'list')
        for n in ('MM_RS_Extra','MM_RS_BestExtra','MM_RS_RawFlag'):local(n,'agent')
        local('MM_RS_Suppressed','boolean');local('MM_RS_ExtraScore')
        once('bestscore = 1;',after='MM_RS_BestExtra = $NullAgent();')
        code=[]
        for f,p,cb in extras:
            suppression=''
            if f.suppress_player_attack_flags:
                flags='MM_RS_EligibleFlags' if f.suppress_player_attack_flags=='eligible' else 'flags'
                suppression='foreach MM_RS_RawFlag in '+flags+''' do
begin
    if (MM_RS_RawFlag's "title" == "flag_attack")
        if ($GetAttribute(MM_RS_RawFlag,#ATTRIB_rewardcost) > 0)
            if ($GetUnitPlayerNumber(MM_RS_RawFlag) == $GetUnitPlayerNumber(thisagent))
                if ($AgentNumber($GetAttribute(MM_RS_RawFlag,#ATTRIB_TargetID)) == MM_RS_Extra)
                    MM_RS_Suppressed = True;
end'''
            code.append(f'''if (no_attack == False)
begin
    MM_RS_Candidates = ${cb['extra_candidates']}(thisagent);
    foreach MM_RS_Extra in MM_RS_Candidates do
        if ($NotValid(MM_RS_Extra) == False)
            if ($IsDead(MM_RS_Extra) == False)
                if ((MM_RS_Extra != thisagent) && (MM_RS_Extra's "type" == "lair"))
                    if (${cb['extra_eligible']}(thisagent,MM_RS_Extra))
                    begin
                        MM_RS_Suppressed = False;
                        {suppression}
                        if (MM_RS_Suppressed == False)
                        begin
                            {travel(p,cb,'MM_RS_Extra')}
                            MM_RS_ExtraScore = ${cb['extra_score']}(thisagent,MM_RS_Extra,{p}_Travel);
                            if (MM_RS_ExtraScore > bestscore)
                            begin bestscore = MM_RS_ExtraScore; MM_RS_BestExtra = MM_RS_Extra; end
                        end
                    end
end''')
        code.append('''if (MM_RS_BestExtra != $NullAgent())
begin
    thisagent's "ActiveScript" = $Attack_object;
    thisagent's "Target" = MM_RS_BestExtra;
    $SpecifyIntent(ThisAgent,#Intent_Raiding);
    return True;
end''')
        once('if (bestscore > 1)',before='\n'.join(code))
    return fn.emit()


def review(dataset, packages, candidates, stock_loader, session, *, inference=None):
    """Compose proven declarations; opaque edits retain exact preferred bodies."""
    from .script_review import ScriptCandidate, ScriptConflict, _combine
    packages=tuple(packages)
    if not any(features for _,_,features,_ in packages):return None
    records=validate(packages)
    stock=stock_loader(('check_rewards','raid_lair')); base=stock[KEY]
    authored={}
    for c in candidates:
        if c.item.key!=KEY:continue
        if c.owner in authored and _tokens(authored[c.owner].item.text)!=_tokens(c.item.text):
            raise ValueError('one reward provider supplies competing effective definitions: '+c.label)
        authored[c.owner]=c
    by_owner={}
    for owner,f in records:by_owner.setdefault(owner,[]).append((owner,f))
    proven={}
    for owner,features in by_owner.items():
        if owner not in authored:raise ValueError('reward declaration needs its standalone check_rewards definition: '+owner)
        try:
            expected=render(base,features,stock.get((DefinitionKind.FUNCTION,'raid_lair')))
            if equivalent(expected,authored[owner].item):proven[owner]=features
        except FunctionMergeError:
            pass  # unsupported shapes remain ordinary preferred-mod choices
    if inference is not None:
        for owner,candidate in authored.items():
            if owner in by_owner:
                continue  # An explicit author declaration must prove itself.
            factored=inference.factor(owner,candidate.item,base)
            if factored is not None:
                proven[owner]=((owner,factored),)
    def combine(owners):
        if len(owners)==1:return authored[owners[0]].item
        declared=tuple(r for o in owners for r in proven.get(o,()))
        plain=tuple(authored[o] for o in owners if o not in proven)
        generated=render(base,declared,stock.get((DefinitionKind.FUNCTION,'raid_lair')))
        if not plain:return generated
        # Disjoint ordinary changes still use the existing instruction merger.
        # An opaque insertion in a competing phase remains a real conflict.
        variants=(*plain,ScriptCandidate('Declared reward contributions',generated,'<declared>')) if declared else plain
        conflict=ScriptConflict(dataset,KEY,'check_rewards','Reward target selection',base,variants)
        return _combine(conflict,tuple(c.owner for c in variants))
    conflict=ScriptConflict(dataset,KEY,'check_rewards',
        'Reward eligibility, incentives and target priority. Undeclared overlapping rules use the preferred mod.',
        base,tuple(authored[o] for o in sorted(authored)),combine_candidates=combine)
    session.resolve(conflict)
    return conflict
