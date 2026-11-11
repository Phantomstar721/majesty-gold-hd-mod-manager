"""Bounded SDK-contract proof for stock-relative terminal reward multipliers.

No author identity or private symbol is recognized. A declined proof leaves the
ordinary complete-function preference path intact. Native implementations are
not discovered here; these are the stock SDK query contracts, with any selected
GPL definition of those names explicitly disqualifying inference.
"""
from dataclasses import dataclass, replace
import hashlib
import re

from .gpl import DefinitionKind
from .gpl_function_merge import _Parser, _tokens, FunctionMergeError
from .damage_contributions import _Function
from .spell_policy import signature

KEY = (DefinitionKind.FUNCTION, 'check_rewards')
# Original SDK GPL Reference.pdf: p27, p28 and p32 respectively. The saved-field
# existence/required-read boundary is independently guarded for all three builds
# in SavedAttributeProfiles.h. These annotations are source API contracts, not
# a new claim of complete native-handler recovery.
QUERIES = {
    'getunitplayernumber': (('agent',), 'integer'),
    'hasattribute': (('string', 'agent'), 'boolean'),
    'isvalidgamepiece': (('agent',), 'boolean'),
}


def _require(condition, reason):
    if not condition:
        raise FunctionMergeError('reward factor proof: ' + reason)


class _Reads:
    """Small typed expression grammar; no arithmetic or dynamic invocation."""
    def __init__(self, values, variables, claimed):
        self.values, self.variables, self.claimed = tuple(values), variables, claimed
        self.position = 0
        _require(len(self.values) <= 128, 'predicate exceeds budget')

    def take(self, value=None):
        _require(self.position < len(self.values), 'incomplete predicate')
        token = self.values[self.position]
        _require(value is None or token == value, 'unsupported predicate grammar')
        self.position += 1
        return token

    def peek(self):
        return self.values[self.position] if self.position < len(self.values) else ''

    @staticmethod
    def fits(actual, expected):
        # Named GPL properties are dynamically typed; the original proven GPL
        # and its guarded access order are retained in the cloned helper.
        return actual in (expected, 'property')

    def expression(self, depth=0):
        _require(depth < 16, 'predicate nesting exceeds budget')
        value = self.comparison(depth + 1)
        while self.peek() in ('&&', '||'):
            self.take()
            other = self.comparison(depth + 1)
            _require(self.fits(value, 'boolean') and self.fits(other, 'boolean'), 'nonboolean condition')
            value = 'boolean'
        return value

    def comparison(self, depth):
        value = self.atom(depth)
        if self.peek() in ('==', '!=', '<', '>', '<=', '>='):
            operation = self.take()
            other = self.atom(depth)
            _require(value == other or 'property' in (value, other), 'comparison type changed')
            _require(operation in ('==', '!=') or value in ('integer', 'property'), 'unsupported comparison')
            value = 'boolean'
        return value

    def atom(self, depth):
        _require(depth < 16, 'predicate nesting exceeds budget')
        token = self.take()
        if token == '(':
            value = self.expression(depth + 1)
            self.take(')')
            return value
        if token.startswith('$'):
            name = token[1:]
            _require(name in QUERIES, 'unknown query: ' + name)
            _require(not self.claimed.get((DefinitionKind.FUNCTION, name)), 'selected query override: ' + name)
            arguments, result = QUERIES[name]
            self.take('(')
            for n, expected in enumerate(arguments):
                if n: self.take(',')
                _require(self.fits(self.expression(depth + 1), expected), 'query argument type: ' + name)
            self.take(')')
            return result
        if token in ('true', 'false'):
            return 'boolean'
        if re.fullmatch(r'[0-9]+', token):
            _require(int(token) <= 2147483647, 'integer literal outside supported range')
            return 'integer'
        if token.startswith('"'):
            return 'string'
        _require(token in self.variables, 'unbound or score-dependent read: ' + token)
        value = self.variables[token]
        if self.peek() == "'s":
            _require(value == 'agent', 'property receiver is not an agent')
            self.take()
            _require(self.take().startswith('"'), 'property key must be literal')
            return 'property'
        return value

    def prove(self, expected=None):
        value = self.expression()
        _require(self.position == len(self.values), 'unsupported arithmetic, mutation or invocation')
        _require(expected is None or self.fits(value, expected), 'expression type changed')
        return value


@dataclass(frozen=True)
class FactoredReward:
    feature_key: str
    condition: tuple
    multiplier: int
    helper: object
    original_helper: str
    callbacks: tuple = ()
    priority_multiplier: int = 1
    extra_dispatch: object = None
    suppress_player_attack_flags: bool = True


class InferenceScope:
    """Effective compiled ownership, independent of offered source text."""
    def __init__(self, providers, inventories):
        from .standard_scripts import for_dataset
        from .bcd import definition_keys
        self.providers = {p.package.mod_id.strip('{}').casefold(): p
                          for p in for_dataset(providers.inputs, providers.dataset)}
        self.compiler = providers.compiler
        self.claimed, self.accepted, self.declined = {}, {}, {}
        self.complete = True
        try:
            for owner, provider in self.providers.items():
                for key in provider.compiled_keys:
                    self.claimed.setdefault(key, set()).add(owner)
            for inventory in inventories:
                owner = inventory.selected.package.mod_id.strip('{}').casefold()
                for load in inventory.gpl_loads:
                    for key in definition_keys(load.target.absolute_path.read_bytes()):
                        self.claimed.setdefault(key, set()).add(owner)
        except (OSError, ValueError):
            self.complete = False

    def factor(self, owner, caller, stock):
        provider = self.providers.get(owner)
        if provider is None:
            return None
        try:
            _require(self.complete, 'selected compiled ownership is incomplete')
            value = infer(provider, caller, stock, self.claimed, self.compiler)
        except (OSError, ValueError) as exc:
            self.declined[owner] = str(exc)
            return None
        self.accepted[owner] = value
        return value


def _bound_caller(caller, stock):
    ah, al, ab = _Parser(caller.text).function()
    sh, sl, sb = _Parser(stock.text).function()
    def parameters(header):
        return tuple(zip(header[3:header.index(')'):3], header[4:header.index(')'):3]))
    ap, sp = parameters(ah), parameters(sh)
    _require(tuple(t for t, _ in ap) == tuple(t for t, _ in sp), 'caller parameter types changed')
    _require(tuple(al.values()) == tuple(sl.values()), 'caller locals changed')
    names = dict(zip((n for _, n in ap), (n for _, n in sp)))
    names.update(zip(al, sl))
    def nodes(values):
        return tuple(replace(n, head=tuple(names.get(t, t) for t in n.head),
                             body=nodes(n.body), otherwise=nodes(n.otherwise)) for n in values)
    _require(tuple(names.get(t, t) for t in ah) == sh, 'caller signature changed')
    return nodes(ab), sb


def _insertions(actual, stock, budget):
    budget[0] -= len(actual)
    _require(budget[0] >= 0, 'selector exceeds node budget')
    for index, node in enumerate(actual):
        if actual[:index] + actual[index + 1:] == stock:
            after = actual[index + 1:]
            if (len(after) >= 2 and after[0].head == _tokens('$debugout(score);')
                    and after[1].head == _tokens('if (score > bestscore)')):
                yield node
        if len(actual) != len(stock) or index >= len(stock):
            continue
        other = stock[index]
        if node.kind != other.kind or node.head != other.head:
            continue
        if actual[:index] != stock[:index] or actual[index + 1:] != stock[index + 1:]:
            continue
        if node.otherwise == other.otherwise:
            yield from _insertions(node.body, other.body, budget)
        if node.body == other.body:
            yield from _insertions(node.otherwise, other.otherwise, budget)


def infer(provider, caller, stock, claimed, compiler):
    """Prove one source-owned scoring shape; never guess an absent contract."""
    from .standard_scripts import verify
    owner = provider.package.mod_id.strip('{}').casefold()
    actual, baseline = _bound_caller(caller, stock)
    matches = tuple(_insertions(actual, baseline, [2048]))
    _require(len(matches) == 1, 'not one complete stock-relative terminal insertion')
    insertion = matches[0]
    _require(insertion.kind == 'if' and not insertion.otherwise and len(insertion.body) == 1,
             'unsupported insertion')
    _Reads(insertion.head[2:-1], {'thisagent': 'agent', 'flag': 'agent'}, claimed).prove('boolean')
    assignment = insertion.body[0].head
    _require(len(assignment) == 11 and assignment[:2] == ('score', '=')
             and assignment[2].startswith('$') and assignment[3:] ==
             ('(', 'thisagent', ',', 'flag', ',', 'score', ')', ';'), 'score call changed')
    helper_name = assignment[2][1:]
    key = (DefinitionKind.FUNCTION, helper_name)
    _require(claimed.get(key) == {owner}, 'helper has a selected competing owner')
    owned = provider.owner(key)
    _require(owned is not None and owned[1] is not None, 'helper source unavailable')
    helper = owned[1]
    signature(helper, ('agent', 'agent', 'integer'), 'integer')
    header, locals_, body = _Parser(helper.text).function()
    parameters = tuple(header[4:header.index(')'):3])
    _require(len(parameters) == 3 and not set(parameters) & set(locals_), 'helper bindings changed')
    _require(0 < len(body) <= 64, 'helper exceeds budget')
    score = parameters[2]
    tail = body[-1].head
    _require(body[-1].kind == 'statement' and len(tail) == 5 and tail[:3] == ('return', score, '*')
             and tail[-1] == ';', 'terminal product changed')
    operand = tail[3]
    prefix = body[:-1]
    if operand in locals_:
        _require(locals_[operand] == 'integer' and prefix and prefix[-1].kind == 'statement', 'priority type changed')
        last = prefix[-1].head
        _require(len(last) == 4 and last[:2] == (operand, '=') and last[-1] == ';', 'priority assignment changed')
        literal = last[2]
        prefix = prefix[:-1]
    else:
        literal = operand
    proof_blocks = {owned[0]}
    caller_owned = provider.owner(KEY)
    _require(caller_owned is not None and caller_owned[1] is not None
             and _tokens(caller_owned[1].text) == _tokens(caller.text), 'caller is not the effective source')
    _require(claimed.get(KEY) == {owner} or owner in claimed.get(KEY, ()), 'caller owner unavailable')
    proof_blocks.add(caller_owned[0])
    if literal.startswith('#'):
        constant_key = (DefinitionKind.EXPRESSION, literal)
        _require(claimed.get(constant_key) == {owner}, 'multiplier has a selected competing owner')
        constant = provider.owner(constant_key)
        _require(constant is not None and constant[1] is not None, 'multiplier source unavailable')
        tokens = _tokens(constant[1].text)
        _require(len(tokens) == 3 and tokens[:2] == ('expression', literal), 'multiplier is not a literal')
        literal = tokens[2]
        proof_blocks.add(constant[0])
    _require(re.fullmatch(r'[0-9]+', literal) is not None and 1 <= int(literal) <= 32767,
             'multiplier outside the supported positive-integer contract')
    variables = {parameters[0]: 'agent', parameters[1]: 'agent'}
    for node in prefix:
        _require(score not in node.head, 'score-dependent eligibility')
        if node.kind == 'if':
            _require(not node.otherwise and len(node.body) == 1
                     and node.body[0].head == ('return', '0', ';'), 'not an early literal-zero guard')
            _Reads(node.head[2:-1], variables, claimed).prove('boolean')
        else:
            head = node.head
            _require(node.kind == 'statement' and len(head) >= 4 and head[0] in locals_
                     and head[1] == '=' and head[-1] == ';', 'nonlocal write or unsupported statement')
            _Reads(head[2:-1], variables, claimed).prove(locals_[head[0]])
            variables[head[0]] = locals_[head[0]]
    # An operand local is assigned only by the final proven literal statement.
    _require(operand not in variables or operand not in locals_, 'priority is also used as an earlier mutable local')
    for block in sorted(proof_blocks):
        verify(provider, compiler, block)
    digest = hashlib.sha256((owner + repr(insertion) + helper.text).encode()).hexdigest()[:20]
    private = 'MM_RewardFactor_' + digest
    _require(not claimed.get((DefinitionKind.FUNCTION, private.casefold())), 'private helper symbol collision')
    clone = _Function(helper)
    clone.rename(private)
    # #expressions are compiler-project bindings, not independently loaded GPL
    # functions. Keep the proven value self-contained in the clone instead of
    # accidentally relying on the original Standard project's compiler inputs.
    # This changes no local reference/guard lifetime or multiplication order.
    cloned=list(clone.body)
    if operand in locals_:
        cloned[-2]=replace(cloned[-2],head=(operand,'=',str(int(literal)),';'))
        returned=operand
    else:
        returned=str(int(literal))
    cloned[-1]=replace(cloned[-1],head=('return',returned,';'))
    clone.body=tuple(cloned)
    emitted = clone.emit()
    return FactoredReward('inferred.reward.' + digest, insertion.head[2:-1], int(literal), emitted, helper_name)
