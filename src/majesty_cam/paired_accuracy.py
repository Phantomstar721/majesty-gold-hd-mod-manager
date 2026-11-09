"""Paired progression through ordinary stock GPL adjustments.

No replay, absolute setter, new native capability or owned-stat projection is
required by this source path. Native save/load acceptance is a feature test.
"""
from dataclasses import dataclass, replace
import re
from .gpl import DefinitionKind, parse_gpl
from .gpl_function_merge import _Parser, _tokens, _code, _render, merge_function

FUNCTIONS = ('level_up_stats_increase', 'level_down_stats_decrease')
OWNER = 'manager-paired-accuracy'


@dataclass(frozen=True)
class SourceCandidate:
    helper: str
    functions: tuple
    runtime_ready: bool = False
    integration_kind: str = 'ordinary-gpl-source'
    load_policy: str = 'stock-save-load-no-replay'


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', value):
        raise ValueError('paired accuracy requires bounded GPL identifiers')
    return value


def _guard(mode, attribute, direction):
    op, limit = ('<', 98) if direction == 1 else ('>', 1)
    source = f'''function probe(agent thisagent)
begin
if (thisagent's "attacktype" == {mode})
    if ($getattribute(thisagent,#ATTRIB_{attribute}) {op} {limit})
        $adjustattribute(thisagent,#ATTRIB_{attribute},{direction});
end'''
    return _Parser(source).function()[2][0]


def compose_candidate(stock_text, *, marker, helper_symbol, other_variants=None):
    """Widen only the two literal stock accuracy guards, in BOTH functions.

    Other providers use the existing structural merger and cannot replace this
    provider's side. Altered caps, deltas, signatures or branch bodies reject.
    This does not instrument or commit a persistent contribution ledger.
    """
    marker, helper_symbol = _identifier(marker), _identifier(helper_symbol)
    items = parse_gpl(stock_text).items
    names = [item.name.casefold() for item in items]
    if helper_symbol.casefold() in names:
        raise ValueError('paired accuracy helper collides with an existing symbol')
    if any(names.count(name) != 1 for name in FUNCTIONS):
        raise ValueError('paired accuracy requires exactly both stock stat functions')
    others = other_variants or {}
    if set(others)-set(FUNCTIONS):
        raise ValueError('unknown paired accuracy function side')
    helper = f'''function {helper_symbol}(agent Hero, integer Mode) is boolean
declare
begin
    if ($HasAttribute("{marker}", Hero))
        if (Hero's "{marker}") return TRUE;
    return (Hero's "attacktype" == Mode);
end
'''
    result = []
    for name, direction in zip(FUNCTIONS, (1, -1)):
        original = next(item.text for item in items if item.name.casefold() == name)
        signature, declarations, body = _Parser(original).function()
        if signature != _tokens(f'function {name}(agent thisagent)'):
            raise ValueError('paired accuracy stat signature changed')
        nodes = list(body)
        checks = []
        for mode, attribute in ((1, 'HtoH'), (2, 'Ranged')):
            stock = _guard(mode, attribute, direction)
            positions = [i for i, node in enumerate(nodes) if node.head == stock.head]
            if len(positions) != 1 or nodes[positions[0]] != stock:
                raise ValueError('stock accuracy guard/body changed')
            head = _tokens(f'if (${helper_symbol}(thisagent, {mode}))')
            replacement = replace(stock, head=head)
            nodes[positions[0]] = replacement
            checks.append(replacement)
        lines = [_code(signature), 'declare']
        lines.extend(f'{kind} {var};' for var, kind in declarations.items())
        lines.extend(['begin', *_render(nodes), 'end'])
        sides = dict(others.get(name, {}))
        if any(str(owner).casefold() == OWNER for owner in sides):
            raise ValueError('external side cannot replace paired accuracy provider')
        sides[OWNER] = '\n'.join(lines)
        merged = merge_function(original, sides)
        merged_body = _Parser(merged).function()[2]
        for expected in checks:
            matches = [node for node in merged_body if node.head == expected.head]
            if matches != [expected]:
                raise ValueError('composed output changed paired accuracy operation')
        result.append((name, merged))
    return SourceCandidate(helper, tuple(result))


def compose_source(stock_text, *, marker, helper_symbol, other_variants=None):
    """Return a complete source file, retaining every unrelated byte.

    This is an offline source adapter, not a registered Manager recipe. Both
    progression functions must be in the supplied source. No load callback or
    initialization-time award is generated.
    """
    candidate = compose_candidate(stock_text, marker=marker,
                                  helper_symbol=helper_symbol,
                                  other_variants=other_variants)
    replacements = dict(candidate.functions)
    items = [item for item in parse_gpl(stock_text).items
             if item.kind == DefinitionKind.FUNCTION
             and item.normalized_name in replacements]
    result = stock_text
    for item in sorted(items, key=lambda item: item.span.start, reverse=True):
        result = (result[:item.span.start] + replacements[item.normalized_name] + '\n'
                  + result[item.span.end:])
    return candidate.helper + '\n' + result
