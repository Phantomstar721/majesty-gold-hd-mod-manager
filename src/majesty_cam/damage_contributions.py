"""Opt-in source contributions around the destination game's damage lifecycle."""
from dataclasses import dataclass, replace
import re
import hashlib
from .gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from .gpl_function_merge import _Parser, _tokens, _code, _render
from .spell_policy import signature

FEATURE_TYPE = 'stock.damage-contribution.v1'
W = ('agent', 'agent', 'integer', 'integer', 'boolean')
S = ('agent', 'agent', 'agent', 'integer')
SIGNATURES = {
    'weapon_begin': (('agent', 'agent'), 'integer'),
    **{phase: (W, 'integer') for phase in ('weapon_roll', 'weapon_hero_bonus',
        'weapon_pre_armor', 'weapon_armor', 'weapon_blocked', 'weapon_flat_reduce', 'weapon_percent_reduce')},
    'weapon_building_full': (('agent', 'agent'), 'boolean'),
    'weapon_final': (W, ''),
    **{phase: (S, 'integer') for phase in ('spell_bonus', 'spell_flat_reduce', 'spell_percent_reduce')},
    'spell_final': (S, ''),
    'after_hp': (('agent', 'agent', 'integer'), ''),
}
ROOTS = ('damage', 'spelldamage', 'spell_attack', 'player_spell_attack',
         'vortex_active', 'wind_storm_active', 'BuildingDamageModifier')
EXPORTS = ('MM_Damage_Spell', 'MM_Damage_PeriodicSpellAttack',
           'MM_Damage_PeriodicPlayerSpellAttack', 'MM_Damage_Building')

@dataclass(frozen=True)
class DamageContribution:
    feature_key: str
    callbacks: tuple[tuple[str, str], ...]
    type: str = FEATURE_TYPE

def parse_feature(value):
    if not isinstance(value, dict) or set(value) != {'type','feature_key','callbacks'} or value.get('type') != FEATURE_TYPE:
        raise ValueError('damage contribution requires type, feature_key and callbacks')
    key=value['feature_key']; callbacks=value['callbacks']
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}',key):
        raise ValueError('invalid damage contribution feature_key')
    if not isinstance(callbacks,dict) or not callbacks or set(callbacks)-SIGNATURES.keys():
        raise ValueError('unknown or empty damage contribution phases')
    for symbol in callbacks.values():
        if not isinstance(symbol,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',symbol) or symbol.lower().startswith('mm_'):
            raise ValueError('damage callback must be an unreserved GPL symbol')
    return DamageContribution(key,tuple(sorted(callbacks.items())))

def feature_mapping(feature):
    value={'type':FEATURE_TYPE,'feature_key':feature.feature_key,'callbacks':dict(feature.callbacks)}
    parse_feature(value)
    return value

def selected(inventories):
    return any(isinstance(f,DamageContribution) for i in inventories
               for f in getattr(getattr(getattr(i.selected,'package',None),'definition',None),'runtime_features',()))

def validate_bindings(packages):
    """(owner, features, parsed sources); current declarations, never source pins."""
    found={}; features=[]; keys=set()
    for owner, declarations, sources in packages:
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    found.setdefault(item.normalized_name,[]).append((owner,item))
        features.extend((owner,f) for f in declarations if isinstance(f,DamageContribution))
    for owner,feature in features:
        feature_mapping(feature)
        key=feature.feature_key.casefold()
        if key in keys:raise ValueError('duplicate damage feature_key: '+key)
        keys.add(key)
        for phase,symbol in feature.callbacks:
            rows=found.get(symbol.casefold(),())
            if len(rows)!=1 or rows[0][0]!=owner:
                raise ValueError(owner+': damage callback requires one package-owned function: '+symbol)
            signature(rows[0][1],*SIGNATURES[phase])
    for name in EXPORTS:
        if name.casefold() in found:raise ValueError('generated damage symbol collision: '+name)
    return tuple(f for _,f in sorted(features,key=lambda row:row[1].feature_key.casefold()))

def _nodes(code):
    return _Parser('function Fragment() declare begin '+code+' end').function()[2]

class _Function:
    def __init__(self,item):
        self.header,self.locals,self.body=_Parser(item.text).function()
        self.name=item.name
    def local(self,name,kind='integer'):
        if name.casefold() in self.locals:raise ValueError(self.name+': generated damage local collision: '+name)
        self.locals[name.casefold()]=kind
    def once(self,head,*,before='',after='',replacement=None,inside=''):
        wanted=_tokens(head); count=0
        def visit(nodes):
            nonlocal count
            result=[]
            for node in nodes:
                node=replace(node,body=visit(node.body),otherwise=visit(node.otherwise))
                if node.head==wanted:
                    count+=1
                    if inside:node=replace(node,body=(*_nodes(inside),*node.body))
                    result.extend(_nodes(before))
                    result.extend((node,) if replacement is None else _nodes(replacement))
                    result.extend(_nodes(after))
                else:result.append(node)
            return tuple(result)
        self.body=visit(self.body)
        if count!=1:raise ValueError(self.name+': damage calculation boundary changed or ambiguous: '+head)
    def rename(self,name):
        self.header=(self.header[0],name.casefold(),*self.header[2:]);self.name=name
    def redirect_calls(self, mapping):
        """Change only known call tokens; preserve arguments and control flow."""
        count = 0
        def visit(nodes):
            nonlocal count
            result = []
            for node in nodes:
                head = list(node.head)
                for index, token in enumerate(head[:-1]):
                    if token in mapping and head[index + 1] == '(':
                        head[index] = mapping[token]
                        count += 1
                result.append(replace(node, head=tuple(head), body=visit(node.body),
                                      otherwise=visit(node.otherwise)))
            return tuple(result)
        self.body = visit(self.body)
        return count
    def emit(self):
        text='\n'.join((_code(self.header),'declare',*(f'{kind} {name};' for name,kind in self.locals.items()),
                         'begin',*_render(self.body),'end'))+'\n'
        item=parse_gpl(text).require(DefinitionKind.FUNCTION,self.name)
        if _Parser(item.text).function()!=(self.header,self.locals,self.body):raise ValueError('damage emitter changed structure')
        return item

def compose(result,features,stock_loader, *, reviewed_weapon=False, weapon_features=None):
    if not features:return result
    result.require_clean()
    features=tuple(sorted(features,key=lambda f:f.feature_key.casefold()))
    weapon_keys = None if weapon_features is None else {f.feature_key for f in weapon_features}
    items={i.key:i for i in result.items}
    for name in EXPORTS:
        if (DefinitionKind.FUNCTION,name.casefold()) in items:raise ValueError('generated damage symbol collision: '+name)
    missing=tuple(n for n in ROOTS if (DefinitionKind.FUNCTION,n.casefold()) not in items)
    loaded=stock_loader(missing) if missing else {}
    originals={**loaded,**items}
    def get(name):
        key=(DefinitionKind.FUNCTION,name.casefold())
        item=originals.get(key)
        if item is None:raise ValueError('missing effective damage source: '+name)
        return _Function(item)
    for f in features:
        for phase,name in f.callbacks:
            item=items.get((DefinitionKind.FUNCTION,name.casefold()))
            if item is None:raise ValueError('missing effective damage callback: '+name)
            signature(item,*SIGNATURES[phase])
    def callbacks(phase):
        return [(hashlib.sha256(f.feature_key.casefold().encode('ascii')).hexdigest()[:12],dict(f.callbacks)[phase])
                for f in features if phase in dict(f.callbacks) and
                (weapon_keys is None or not (phase.startswith('weapon_') or phase == 'after_hp')
                 or f.feature_key in weapon_keys)]
    def weapon(phase,amount='dmg',notify=False):
        return '\n'.join((('' if notify else amount+' = ')+f'${name}(attacker,defender,{amount},MM_Damage_State{index},critical_effect);')
                         for index,name in callbacks(phase))
    def spell(phase,notify=False):
        return '\n'.join(('' if notify else 'dmg = ')+f'${name}(MM_Damage_Source,attacker,defender,dmg);'
                         for _,name in callbacks(phase))
    after='\n'.join(f'${name}(attacker,defender,MM_Damage_BeforeHP);' for _,name in callbacks('after_hp'))
    before='MM_Damage_BeforeHP = $GetAttribute(defender,#ATTRIB_HP);' if after else ''
    hp='$adjustattribute(defender,#ATTRIB_HP,-dmg);'

    weapon_fn=get('damage')
    init=[]
    for feature in (() if reviewed_weapon else features):
        index=hashlib.sha256(feature.feature_key.casefold().encode('ascii')).hexdigest()[:12]
        state=f'MM_Damage_State{index}';weapon_fn.local(state)
        callback=dict(feature.callbacks).get('weapon_begin')
        init.append(f'{state} = ${callback}(attacker,defender);' if callback else f'{state} = 0;')
    weapon_fn.body=(*_nodes('\n'.join(init)),*weapon_fn.body)
    for phase,anchor in (
        ('weapon_roll','dmg = $randomnumber($GetAttribute(attacker,#ATTRIB_weapon_basic_damage)) + 1;'),
        ('weapon_hero_bonus','dmg += $GetAttribute(attacker,#ATTRIB_weapon_magic_bonus);')):
        if callbacks(phase) and not reviewed_weapon:weapon_fn.once(anchor,after=weapon(phase))
    if callbacks('weapon_pre_armor') and not reviewed_weapon:
        weapon_fn.once('if ((defender\'s "type" == "building") || (defender\'s "type" == "lair"))',before=weapon('weapon_pre_armor'))
    if callbacks('weapon_armor') and not reviewed_weapon:
        weapon_fn.once('t = dmg_stopped / 4;',before=weapon('weapon_armor','dmg_stopped'))
    if callbacks('weapon_blocked') and not reviewed_weapon:
        weapon_fn.once('dmg_stopped = t + t2;',after=weapon('weapon_blocked','dmg_stopped'))
    reductions=weapon('weapon_flat_reduce')+'\n'+weapon('weapon_percent_reduce')
    if reductions.strip() and not reviewed_weapon:weapon_fn.once('if (dmg < 0)',before=reductions)
    if callbacks('weapon_final') and not reviewed_weapon:weapon_fn.once('if (dmg > 0)',inside=weapon('weapon_final',notify=True))
    if after and not reviewed_weapon:
        weapon_fn.local('MM_Damage_BeforeHP');weapon_fn.once(hp,before=before,after=after)
    if callbacks('weapon_building_full'):
        building=get('BuildingDamageModifier');building.rename('MM_Damage_Building')
        admission='\n'.join(f'if (${name}(attacker,defender)) return dmg;' for _,name in callbacks('weapon_building_full'))
        building.once('dmg /= 2;',before=admission)
        emitted=building.emit();items[emitted.key]=emitted
        if not reviewed_weapon:weapon_fn.once('dmg = $BuildingDamageModifier(attacker,defender,dmg);',
                       replacement='dmg = $MM_Damage_Building(attacker,defender,dmg);')
    if not reviewed_weapon:
        emitted=weapon_fn.emit();items[emitted.key]=emitted

    # A weapon preference never removes unrelated spell contributions.
    weapon_keys = None
    after='\n'.join(f'${name}(attacker,defender,MM_Damage_BeforeHP);' for _,name in callbacks('after_hp'))
    before='MM_Damage_BeforeHP = $GetAttribute(defender,#ATTRIB_HP);' if after else ''

    calculation=get('spelldamage')
    calculation.name='MM_Damage_Spell'
    calculation.header=_tokens('function MM_Damage_Spell(agent MM_Damage_Source,agent attacker,agent defender,integer damage,integer damage_minimum,integer MM_Damage_Bonus,boolean MM_Damage_Direct) is integer')
    # Magic-armor conditional is after the stock roll/minimum/Intelligence.
    calculation.once('if (defender != $nullagent())',before='dmg += MM_Damage_Bonus;\n'+spell('spell_bonus'))
    direct=spell('spell_flat_reduce')+'\n'+spell('spell_percent_reduce')
    final=spell('spell_final',notify=True)
    if direct.strip():direct+='\nif (dmg < 0) dmg = 0;'
    if final:direct+='\nif (dmg > 0) begin '+final+' end'
    if after:calculation.local('MM_Damage_BeforeHP')
    calculation.once(hp,before=('if (MM_Damage_Direct) begin '+direct+' end\n' if direct.strip() else '')+
                     ('if (MM_Damage_Direct && dmg > 0) '+before if before else ''),
                     after=('if (MM_Damage_Direct && dmg > 0) begin '+after+' end' if after else ''))
    calculation.body=(*calculation.body,*_nodes('return dmg;'))
    emitted=calculation.emit();items[emitted.key]=emitted
    def wrapper(name,params,call):
        item=parse_gpl(f'function {name}({params}) declare begin {call}; end').items[0];items[item.key]=item
    wrapper('spelldamage','agent attacker,agent defender,integer damage,integer damage_minimum',
            '$MM_Damage_Spell(attacker,attacker,defender,damage,damage_minimum,0,FALSE)')
    for name,source,attacker,minimum,periodic in (
        ('spell_attack','thisagent','thisagent','1','MM_Damage_PeriodicSpellAttack'),
        ('player_spell_attack','$nullagent()','$nullagent()','damage_minimum','MM_Damage_PeriodicPlayerSpellAttack')):
        for direct in (True,False):
            function=get(name)
            if not direct:function.rename(periodic)
            function.once(f'$spelldamage({attacker},target,damage,{minimum});',
                replacement=f'$MM_Damage_Spell({source},{attacker},target,damage,{minimum},0,{str(direct)});')
            emitted=function.emit();items[emitted.key]=emitted
    for name in ('vortex_active', 'wind_storm_active'):
        function = get(name)
        # These stock periodic roots may legitimately change targets, damage,
        # call count, or choose the player-spell path. Route the known APIs,
        # not one stock statement. Unknown mod helpers remain authored behavior.
        if function.redirect_calls({
            '$spell_attack': '$mm_damage_periodicspellattack',
            '$player_spell_attack': '$mm_damage_periodicplayerspellattack',
        }):
            emitted = function.emit(); items[emitted.key] = emitted
    return SemanticMergeResult(tuple(items.values()),())


def review_weapon(dataset, packages, candidates, stock_loader, review):
    """Review generated weapon edits with their real mod owners, before emission.

    The bounded damage transform proves compatibility, not a mod name or an
    assumption that a stock-relative insertion is safe inside a rewritten roll.
    Losing a weapon implementation does not disable that mod or its spells.
    """
    from .script_review import ScriptCandidate, ScriptConflict, _combine
    from .gpl_function_merge import FunctionMergeError
    key=(DefinitionKind.FUNCTION,'damage')
    stock=stock_loader(ROOTS)
    base=stock[key]
    providers={}
    callback_items=[]
    labels={}
    for owner,label,features,sources in packages:
        owned=tuple(f for f in features if isinstance(f,DamageContribution)
                    and any(p.startswith('weapon_') or p=='after_hp' for p,_ in f.callbacks))
        if owned:providers[owner]=owned;labels[owner]=label
        callback_items.extend(i for s in sources for i in s.items if i.key not in stock)
    if not providers:return None
    authored={}
    for candidate in candidates:
        if candidate.item.key!=key:continue
        if _tokens(candidate.item.text)==_tokens(base.text):continue
        previous=authored.get(candidate.owner)
        if previous is not None and _tokens(previous.item.text)!=_tokens(candidate.item.text):
            raise ValueError('ambiguous authored damage owner: '+candidate.label)
        authored[candidate.owner]=candidate
    def combine(owners):
        sources=tuple(authored[o] for o in owners if o in authored)
        item=base
        if sources:
            plain=ScriptConflict(dataset,key,'damage','Weapon damage calculation',base,sources)
            item=_combine(plain,tuple(c.owner for c in sources))
        features=tuple(f for o in owners for f in providers.get(o,()))
        if not features:return item
        try:
            generated=compose(SemanticMergeResult((*callback_items,item),()),features,
                              lambda names:{k:v for k,v in stock.items() if k[1] in {n.casefold() for n in names}})
        except ValueError as exc:
            raise FunctionMergeError(str(exc)) from exc
        return next(i for i in generated.items if i.key==key)
    variants=[]
    for owner in sorted(set(authored)|set(providers)):
        # Each contender must be valid alone. A broken provider declaration is
        # not a preference and must not be silently suppressed.
        item=combine((owner,))
        label=labels.get(owner,authored[owner].label if owner in authored else owner)
        variants.append(ScriptCandidate(label,item,owner))
    conflict=ScriptConflict(dataset,key,'damage',
        'Weapon damage, armor and on-hit effects. The preferred mod supplies the '
        'conflicting calculation; incompatible weapon effects from the other mod are not applied.',
        base,tuple(variants),combine_candidates=combine)
    review.resolve(conflict)
    return conflict,providers
