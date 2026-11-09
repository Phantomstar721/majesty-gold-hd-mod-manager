"""Opt-in stock GPL progression and combat scoring; no load-time replay."""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
import hashlib
import re
from .gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from .gpl_function_merge import _Parser, _tokens, _code, _render, FunctionMergeError
from .paired_accuracy import _guard, FUNCTIONS
from .spell_policy import signature
from .script_review import ScriptCandidate, ScriptConflict, _combine

TYPE = 'stock.hero-combat-policy.v1'
ROOTS = (*FUNCTIONS, 'spell_extra_value', 'list_eval')
INCREMENTS = ('melee_accuracy_per_level', 'ranged_accuracy_per_level')
CALLBACKS = {
    'level_callback_symbol': (('agent', 'integer'), ''),
    'confidence_callback_symbol': (('agent',), 'integer'),
    'hostile_multiplier_callback_symbol': (('agent', 'agent'), 'float'),
}


@dataclass(frozen=True)
class HeroCombatPolicy:
    feature_key: str
    hero_title: str
    marker_attribute: str
    paired_accuracy: bool
    level_callback_symbol: str | None = None
    confidence_callback_symbol: str | None = None
    hostile_multiplier_callback_symbol: str | None = None
    type: str = TYPE
    melee_accuracy_per_level: int = 1
    ranged_accuracy_per_level: int = 1


def parse_feature(value):
    required = {'type', 'feature_key', 'hero_title', 'marker_attribute', 'paired_accuracy'}
    if not isinstance(value, dict) or not required <= value.keys() or set(value)-required-CALLBACKS.keys()-set(INCREMENTS):
        raise ValueError('hero combat policy requires its typed identity and progression fields')
    if value['type'] != TYPE or type(value['paired_accuracy']) is not bool:
        raise ValueError('invalid hero combat policy type/paired_accuracy')
    for key in ('feature_key', 'hero_title', 'marker_attribute', *CALLBACKS):
        item = value.get(key)
        if key in CALLBACKS and item is None:
            continue
        pattern = r'[A-Za-z][A-Za-z0-9_.-]{0,63}' if key == 'feature_key' else r'[A-Za-z_][A-Za-z_0-9]{0,63}'
        if not isinstance(item, str) or not re.fullmatch(pattern, item) or item.lower().startswith('mm_'):
            raise ValueError('invalid or reserved hero combat policy '+key)
    for key in INCREMENTS:
        amount = value.get(key, 1)
        if type(amount) is not int or not 1 <= amount <= 98:
            raise ValueError('hero combat accuracy increment must be an integer from 1 to 98: '+key)
        if amount != 1 and not value['paired_accuracy']:
            raise ValueError('custom accuracy increments require paired_accuracy')
    if not value['paired_accuracy'] and not any(value.get(k) for k in CALLBACKS):
        raise ValueError('hero combat policy has no enabled behavior')
    return HeroCombatPolicy(**value)


def feature_mapping(feature):
    value = {k: v for k, v in asdict(feature).items() if v is not None}
    parse_feature(value)
    for key in INCREMENTS:
        if value[key] == 1:
            del value[key]
    return value


def gate(feature):
    return 'MM_HCP_Is_' + hashlib.sha256(feature.feature_key.casefold().encode()).hexdigest()[:16]


def helper(feature):
    return parse_gpl(f'''function {gate(feature)}(agent Hero) is boolean
declare
begin
    if ($IsValidGamePiece(Hero) == FALSE) return FALSE;
    if ($IsDead(Hero)) return FALSE;
    if (Hero's "Title" != "{feature.hero_title}") return FALSE;
    if ($HasAttribute("{feature.marker_attribute}", Hero))
        if (Hero's "{feature.marker_attribute}") return TRUE;
    return FALSE;
end
''').items[0]


def relevant(feature, name):
    if name in FUNCTIONS:
        return feature.paired_accuracy or feature.level_callback_symbol is not None
    return bool(feature.confidence_callback_symbol if name == 'spell_extra_value'
                else feature.hostile_multiplier_callback_symbol)


def validate(packages):
    """Current package-owned callbacks and private character identity, not hashes."""
    records = []; keys = set()
    for owner, label, features, sources, descriptions in packages:
        functions = [i for s in sources for i in s.items if i.kind is DefinitionKind.FUNCTION]
        for feature in features:
            if not isinstance(feature, HeroCombatPolicy):
                continue
            feature_mapping(feature)
            key = feature.feature_key.casefold()
            if key in keys:
                raise ValueError('duplicate hero combat policy key: '+key)
            keys.add(key)
            chars = [d for d in descriptions if d.get('type') == 'Unit' and d.get('subType') == 'Character'
                     and d.get('Name', '').casefold() == feature.hero_title.casefold()]
            if len(chars) != 1:
                raise ValueError(owner+': hero combat policy requires one owned Character Description')
            for field, shape in CALLBACKS.items():
                symbol = getattr(feature, field)
                if symbol:
                    matches = [i for i in functions if i.normalized_name == symbol.casefold()]
                    if len(matches) != 1:
                        raise ValueError(owner+': hero combat callback requires one owned function: '+symbol)
                    signature(matches[0], *shape)
            records.append((owner, label, feature))
    return tuple(records)


def transform(item, features):
    features = tuple(sorted((f for f in features if relevant(f, item.normalized_name)),
                            key=lambda f: f.feature_key.casefold()))
    if not features:
        return item
    if len({f.hero_title.casefold() for f in features}) != len(features):
        raise ValueError('overlapping hero combat policies require a preferred mod')
    name = item.normalized_name
    header, locals_, body = _Parser(item.text).function()
    def nodes(code):
        return _Parser('function fragment() declare begin '+code+' end').function()[2]
    if name in FUNCTIONS:
        signature(item, ('agent',), '')
        direction = 1 if name == FUNCTIONS[0] else -1
        paired = [f for f in features if f.paired_accuracy]
        if paired:
            body = list(body)
            for mode, attribute in ((1, 'HtoH'), (2, 'Ranged')):
                expected = _guard(mode, attribute, direction)
                positions = [n for n, node in enumerate(body) if node.head == expected.head]
                if len(positions) != 1 or body[positions[0]] != expected:
                    raise ValueError(name+': stock accuracy guard/body changed')
                condition = f'(thisagent\'s "attacktype" == {mode})' + ''.join(
                    f' || (${gate(f)}(thisagent))' for f in paired)
                ordinary = replace(expected, head=_tokens('if ('+condition+')'))
                code = '\n'.join(_render((ordinary,)))
                field = INCREMENTS[mode-1]
                for feature in reversed(paired):
                    amount = getattr(feature, field)
                    if amount == 1:
                        continue
                    current = f'$getattribute(thisagent,#ATTRIB_{attribute})'
                    compare, bound = ('<',98) if direction == 1 else ('>',1)
                    fits = f'{current} + {amount} <= 98' if direction == 1 else f'{current} - {amount} >= 1'
                    code = f'''if (${gate(feature)}(thisagent))
                        begin
                            if ({current} {compare} {bound})
                                begin
                                    if ({fits})
                                        $adjustattribute(thisagent,#ATTRIB_{attribute},{direction*amount});
                                    else
                                        $adjustattribute(thisagent,#ATTRIB_{attribute},{bound} - {current});
                                end
                        end
                        else {code}'''
                body[positions[0]] = nodes(code)[0]
            body = tuple(body)
        # One terminal notification after the ordinary stat routine, never load.
        if any(n == 'return' for n in _tokens(item.text)):
            raise ValueError(name+': early return changes level-boundary coverage')
        body = (*body, *nodes('\n'.join(
            f'if (${gate(f)}(thisagent)) ${f.level_callback_symbol}(thisagent,{direction});'
            for f in features if f.level_callback_symbol)))
    elif name == 'spell_extra_value':
        signature(item, ('agent',), 'integer')
        if locals_.get('value') != 'integer' or not body or body[-1].head != ('return','value',';') or _tokens(item.text).count('return') != 1:
            raise ValueError('spell confidence contribution requires the stock terminal value return')
        body = (*body[:-1], *nodes('\n'.join(
            f'if (${gate(f)}(thisagent)) value += ${f.confidence_callback_symbol}(thisagent);'
            for f in features)), body[-1])
    else:
        signature(item, ('agent','list'), 'integer')
        anchor = _tokens('enemy_total_HP += (enemy_HP * (100.0 / (ta_mod_tohit)));')
        matches = 0
        def visit(sequence, in_hostiles=False):
            nonlocal matches
            result = []
            for node in sequence:
                inside = in_hostiles or node.head == _tokens('foreach hostile in thislist do')
                if node.head == anchor:
                    if not in_hostiles:
                        raise ValueError('hostile contribution moved outside stock hostile loop')
                    matches += 1
                    code = ''.join(f'if (${gate(f)}(thisagent)) enemy_total_HP += '
                        f'(enemy_HP * (100.0 / (ta_mod_tohit))) * ${f.hostile_multiplier_callback_symbol}(thisagent,hostile); else '
                        for f in features) + _code(anchor)
                    result.extend(nodes(code))
                else:
                    result.append(replace(node, body=visit(node.body, inside), otherwise=visit(node.otherwise, inside)))
            return tuple(result)
        body = visit(body)
        if matches != 1:
            raise ValueError('stock per-hostile HP contribution changed or ambiguous')
    text = '\n'.join((_code(header), 'declare', *(f'{kind} {var};' for var,kind in locals_.items()),
                      'begin', *_render(body), 'end'))+'\n'
    return replace(item, text=text, span=None, source_name='<stock hero combat policy>')


def review_policies(dataset, records, candidates, stock_loader, review):
    """Generate owner-attributed contenders before preferred-mod review."""
    if not records:
        return ()
    names = tuple(n for n in ROOTS if any(relevant(f,n) for _,_,f in records))
    stock = stock_loader(names)
    plans = []
    for name in names:
        key = (DefinitionKind.FUNCTION,name)
        base = stock.get(key)
        if base is None:
            raise ValueError('missing destination stock combat policy source: '+name)
        providers = {}
        labels = {}
        for owner,label,feature in records:
            if relevant(feature,name):
                providers.setdefault(owner,[]).append(feature); labels[owner] = label
        authored = {}
        for candidate in candidates.get(key, ()):
            if _tokens(candidate.item.text) == _tokens(base.text): continue
            if candidate.owner in authored and _tokens(authored[candidate.owner].item.text) != _tokens(candidate.item.text):
                raise ValueError('ambiguous authored combat policy source: '+candidate.label)
            authored[candidate.owner] = candidate
        def make_combine(base, key, name, authored, providers):
            def combine(owners):
                sides = tuple(authored[o] for o in owners if o in authored)
                root = _combine(ScriptConflict(dataset,key,name,'Hero combat policy',base,sides),
                                tuple(c.owner for c in sides)) if sides else base
                try:
                    return transform(root, tuple(f for o in owners for f in providers.get(o,())))
                except ValueError as exc:
                    raise FunctionMergeError(str(exc)) from exc
            return combine
        combine = make_combine(base,key,name,authored,providers)
        variants = tuple(ScriptCandidate(labels.get(o,authored[o].label if o in authored else o),combine((o,)),o)
                         for o in sorted(set(authored)|set(providers)))
        conflict = ScriptConflict(dataset,key,name,
            'Hero progression or combat scoring. The preferred mod supplies conflicting behavior; '
            'incompatible contributions from the other mod are not added afterward.',
            base,variants,combine_candidates=combine)
        if review is not None:
            review.resolve(conflict)
        else:
            combine(tuple(v.owner for v in variants))
        plans.append(conflict)
    return tuple(plans)


def apply(result, records, plans, review):
    if not records: return result
    items = {i.key:i for i in result.items}
    for conflict in plans:
        owners = review.selected_owners(conflict) if review is not None else tuple(v.owner for v in conflict.candidates)
        if owners is None: review.require_resolved()
        items[conflict.key] = conflict.combine_candidates(owners)
    for _,_,feature in records:
        item = helper(feature)
        if item.key in items:
            raise ValueError('generated hero combat policy helper collides: '+item.name)
        items[item.key] = item
    return SemanticMergeResult(tuple(items.values()), result.conflicts)
