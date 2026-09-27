"""One explicit mod preference per conflicting pair, with no source editing.

The structural merger supplies only definitions it cannot combine safely. A
preference replaces an incompatible contender's complete authored definition,
not individual instructions. Compatible contenders are still merged through the
existing structural merger. Each pair's choice applies across all datasets.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from functools import cached_property
import hashlib
import json
import re

from .gpl import (DefinitionKind, SemanticItem, parse_dat, parse_gpl,
                  require_complete_semantic_coverage, find_foreach_return_violations)
from .gpl_function_merge import FunctionMergeError, _Parser, _tokens, merge_function


@dataclass(frozen=True)
class ScriptCandidate:
    label: str
    item: SemanticItem
    owner: str = ''

    def __post_init__(self):
        owner = self.label if self.owner == '' else self.owner
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError('a script candidate must identify its owning mod')
        object.__setattr__(self, 'owner', owner)


def pair_key(left_owner, right_owner):
    """A collision-safe identity independent of display names and definitions."""
    if any(not isinstance(owner, str) or not owner.strip()
           for owner in (left_owner, right_owner)) or left_owner == right_owner:
        raise ValueError('a mod preference must identify two different mods')
    return json.dumps(sorted((left_owner, right_owner)), ensure_ascii=True,
                      separators=(',', ':'))


def _pair_owners(identity):
    try:
        owners = json.loads(identity)
        if (not isinstance(owners, list) or len(owners) != 2
                or pair_key(*owners) != identity):
            raise ValueError
        return tuple(owners)
    except (TypeError, ValueError):
        raise ValueError('invalid mod preference identity') from None


def validate_preferences(preferences):
    """Validate a preference mapping without needing to read any mod source."""
    choices = dict(preferences)
    edges = {}
    for identity, winner in choices.items():
        owners = _pair_owners(identity)
        if not isinstance(winner, str) or winner not in owners:
            raise ValueError('a mod preference must choose one of the two mods')
        loser = owners[1] if winner == owners[0] else owners[0]
        edges.setdefault(winner, set()).add(loser)
    incoming = {owner: 0 for owner in edges}
    for losers in edges.values():
        for owner in losers:
            incoming[owner] = incoming.get(owner, 0) + 1
    ready = deque(owner for owner, count in incoming.items() if count == 0)
    visited = 0
    while ready:
        owner = ready.popleft()
        visited += 1
        for loser in edges.get(owner, ()):
            incoming[loser] -= 1
            if incoming[loser] == 0:
                ready.append(loser)
    if visited != len(incoming):
        raise ValueError('These preferences contradict each other. '
                         'Choose a consistent order of preferred mods.')
    return choices


def _item_identity(item):
    if item is None:
        return None
    return [item.kind.value, item.name, item.source_name, item.text]


def _signature(text):
    """Compare the ABI, not the spelling of bound argument variables."""
    tokens = _tokens(text)
    right = tokens.index(')') if ')' in tokens else -1
    # Stock GPL uses both omitted and bare `is` for a void function. The
    # structural parser expects an actual return type after `is`; normalize
    # only this header spelling for validation, never the chosen source body.
    if right >= 0 and tokens[right + 1:right + 3] in (('is', 'begin'), ('is', 'declare')):
        text = ' '.join((*tokens[:right + 1], *tokens[right + 2:]))
    signature, _, _ = _Parser(text).function()
    left, right = signature.index('('), signature.index(')')
    arguments = signature[left + 1:right]
    groups = ' '.join(arguments).split(',') if arguments else []
    parameters = [group.split() for group in groups]
    types = {'agent', 'integer', 'boolean', 'string', 'list', 'location', 'function', 'float'}
    if any(len(parameter) != 2 or parameter[0] not in types
           or not re.fullmatch(r'[a-z_][a-z_0-9]*', parameter[1]) for parameter in parameters):
        raise ValueError('resolution has an unsupported function parameter declaration')
    if len({parameter[1] for parameter in parameters}) != len(parameters):
        raise ValueError('resolution has duplicate function parameter names')
    suffix = signature[right + 1:]
    if suffix and (len(suffix) != 2 or suffix[0] != 'is' or suffix[1] not in types):
        raise ValueError('resolution has an unsupported function return type')
    return tuple(parameter[0] for parameter in parameters), suffix


@dataclass(frozen=True)
class ScriptConflict:
    dataset: str
    key: tuple
    name: str
    detail: str
    base: SemanticItem | None
    candidates: tuple[ScriptCandidate, ...]
    compatibility_groups: tuple[tuple[str, ...], ...] = ()

    @cached_property
    def identity(self):
        value = [self.dataset, [self.key[0].value, self.key[1]],
                 _item_identity(self.base),
                 [[candidate.owner, candidate.label, _item_identity(candidate.item)]
                  for candidate in self.candidates], self.compatibility_groups]
        return hashlib.sha256(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii')).hexdigest()

    def validate_choice(self, owner):
        candidates = _candidate_map(self)
        if owner not in candidates:
            raise ValueError('a script choice must identify a contributing mod')
        return self._validate_item(candidates[owner].item)

    def _validate_item(self, chosen):
        text = chosen.text
        try:
            text.encode('cp1252')
        except UnicodeEncodeError as exc:
            raise ValueError('chosen mod contains text the GPL compiler cannot encode (Windows-1252)') from exc
        parser = parse_dat if self.key[0] is DefinitionKind.DAT_BLOCK else parse_gpl
        parsed = parser(text, chosen.source_name)
        require_complete_semantic_coverage(parsed)
        if len(parsed.items) != 1 or parsed.items[0].key != self.key:
            raise ValueError(f'chosen mod must supply exactly one {self.key[0].value}:{self.name} definition')
        item = parsed.items[0]
        if item.kind is DefinitionKind.FUNCTION:
            violations = find_foreach_return_violations(text, parsed.source_name)
            if violations:
                raise ValueError('chosen mod returns from inside foreach; this source is unsafe to combine')
            signature = _signature(item.text)
            references = ((self.base,) if self.base is not None else ()) + tuple(c.item for c in self.candidates)
            if any(reference.key != self.key or _signature(reference.text) != signature for reference in references):
                raise ValueError(f'chosen mods disagree on the parameter or return types of function:{self.name}')
        return chosen

    @cached_property
    def _analysis(self):
        candidates = _candidate_map(self)
        owners = tuple(sorted(candidates))
        all_pairs = tuple((left, right) for index, left in enumerate(owners)
                          for right in owners[index + 1:]
                          if not _same_instructions(candidates[left].item, candidates[right].item))
        try:
            combined = _combine(self, owners)
        except FunctionMergeError:
            pass
        else:
            return _ConflictAnalysis((), combined, False)
        incompatible = []
        for pair in all_pairs:
            try:
                _combine(self, pair)
            except FunctionMergeError:
                incompatible.append(pair)
        # A genuine higher-order conflict has no incompatible pair to explain
        # individually. Explicit whole-definition priority is the conservative
        # fallback; it never invents an automatic source-order winner.
        return _ConflictAnalysis(tuple(incompatible) if incompatible else all_pairs,
                                 None, not incompatible)

    @property
    def whole_definition_priority(self):
        return self._analysis.whole_definition_priority


@dataclass(frozen=True)
class _ConflictAnalysis:
    pairs: tuple[tuple[str, str], ...]
    combined: SemanticItem | None
    whole_definition_priority: bool


def _same_instructions(left, right):
    if left.kind is DefinitionKind.DAT_BLOCK:
        return left.text == right.text
    return _tokens(left.text) == _tokens(right.text)


def _candidate_map(conflict):
    candidates = {}
    for candidate in conflict.candidates:
        if candidate.item.key != conflict.key:
            raise ValueError('a script candidate does not match the conflicting definition')
        previous = candidates.get(candidate.owner)
        if previous is not None and not _same_instructions(previous.item, candidate.item):
            raise ValueError('one mod supplies competing versions of the same definition')
        candidates.setdefault(candidate.owner, candidate)
    if not candidates:
        raise ValueError('a script conflict must contain at least one contributing mod')
    for group in conflict.compatibility_groups:
        if len(group) < 2 or len(set(group)) != len(group) or not set(group) <= candidates.keys():
            raise ValueError('a compatibility group must identify its contributing mods')
        if any(not _same_instructions(candidates[group[0]].item, candidates[owner].item)
               for owner in group[1:]):
            raise ValueError('a compatibility group must preserve one accepted definition')
    return candidates


def _decline_helper_proof(name):
    # A selected native mod can override even stock query helpers. Review has
    # no independent source-ownership proof context and must not assume one.
    raise FunctionMergeError('helper-dependent composition requires its original proof context')


def _combine(conflict, owners):
    candidates = _candidate_map(conflict)
    items = tuple(candidates[owner].item for owner in owners)
    if not items:
        raise FunctionMergeError('no mod definition remains')
    if all(_same_instructions(items[0], item) for item in items[1:]):
        return items[0]
    if conflict.base is None or conflict.key[0] is not DefinitionKind.FUNCTION:
        raise FunctionMergeError('this definition has no safe structural ancestor')
    # Reuse the existing bound-parameter alignment, not a second source rewrite.
    from .standard_scripts import _align_parameters
    text = merge_function(conflict.base.text, {
        owner: _align_parameters(conflict.base.text, candidates[owner].item.text)
        for owner in owners
    }, function_lookup=_decline_helper_proof)
    return replace(items[0], text=text, source_name='<combined mod preferences>', span=None)


@dataclass(frozen=True)
class ModConflictPair:
    identity: str
    left: ScriptCandidate
    right: ScriptCandidate
    conflicts: tuple[ScriptConflict, ...]


def group_conflicts(conflicts):
    """Collect each real mod pair once, regardless of functions or datasets."""
    groups = {}
    for conflict in conflicts:
        candidates = _candidate_map(conflict)
        for left_owner, right_owner in conflict._analysis.pairs:
            left, right = candidates[left_owner], candidates[right_owner]
            identity = pair_key(left_owner, right_owner)
            if identity not in groups:
                groups[identity] = [left, right, {}]
            groups[identity][2].setdefault(conflict.identity, conflict)
    return tuple(ModConflictPair(identity, left, right, tuple(items.values()))
                 for identity, (left, right, items) in sorted(groups.items()))


class ScriptReviewRequired(ValueError):
    def __init__(self, conflicts):
        self.conflicts = tuple(conflicts)
        self.pairs = group_conflicts(self.conflicts)
        rows = '\n'.join(f'{pair.left.label} / {pair.right.label}' for pair in self.pairs)
        super().__init__(f'Choose your preferred mod for {len(self.pairs)} conflicting mod pair(s):\n{rows}')


class ScriptReviewCancelled(ValueError):
    pass


class ScriptReviewSession:
    def __init__(self, decisions=None):
        self.decisions = validate_preferences(decisions or {})
        self._observed = {}

    @property
    def conflicts(self):
        return tuple(self._observed.values())

    @property
    def observed(self):
        return self.conflicts

    def resolve(self, conflict):
        self._observed[conflict.identity] = conflict
        return self._resolution(conflict, validate_preferences(self.decisions))

    @staticmethod
    def _selected_owners(conflict, decisions):
        candidates = _candidate_map(conflict)
        pairs = group_conflicts((conflict,))
        if any(pair.identity not in decisions for pair in pairs):
            return None
        # An authored compatibility rule is one accepted implementation. It
        # cannot be split back into its pre-resolution mod bodies by preferences.
        pair_ids = {pair.identity for pair in pairs}
        for group in conflict.compatibility_groups:
            for outside in sorted(candidates.keys() - set(group)):
                preferences = {decisions[pair_key(owner, outside)] == outside
                               for owner in group if pair_key(owner, outside) in pair_ids}
                if len(preferences) > 1:
                    names = ' + '.join(candidates[owner].label for owner in group)
                    outsider = candidates[outside].label
                    raise ValueError(f'{names} already have shared compatibility rules. '
                                     f'Prefer all of them over {outsider}, or prefer {outsider} '
                                     'over all of them, to keep that combined behavior intact.')
        edges = {owner: set() for owner in candidates}
        incoming = {owner: 0 for owner in candidates}
        incompatible = {pair.identity for pair in pairs}
        for pair in pairs:
            winner = decisions[pair.identity]
            loser = pair.right.owner if winner == pair.left.owner else pair.left.owner
            edges[winner].add(loser)
            incoming[loser] += 1
        ready = deque(sorted(owner for owner, count in incoming.items() if count == 0))
        retained = []
        visited = 0
        while ready:
            owner = ready.popleft()
            visited += 1
            # A removed mod no longer suppresses another mod's compatible
            # changes. Only an incompatible, retained higher-priority version
            # can displace this candidate's definition.
            if not any(pair_key(owner, earlier) in incompatible for earlier in retained):
                retained.append(owner)
            for loser in sorted(edges[owner]):
                incoming[loser] -= 1
                if incoming[loser] == 0:
                    ready.append(loser)
        if visited != len(candidates) or not retained:
            raise ValueError('These mod preferences do not have a consistent winner.')
        return tuple(sorted(retained))

    @classmethod
    def _resolution(cls, conflict, decisions):
        selected = cls._selected_owners(conflict, decisions)
        if selected is None:
            return None
        try:
            item = conflict._analysis.combined or _combine(conflict, selected)
        except FunctionMergeError as exc:
            candidates = _candidate_map(conflict)
            names = ', '.join(candidates[owner].label for owner in selected)
            raise ValueError('These mod versions still cannot be combined with these preferences: '
                             f'{names}. Change your preferred mod, or cancel and disable one '
                             'of these mods before preparing again.') from exc
        return conflict._validate_item(item)

    def selected_owners(self, conflict):
        """Contributing owners, or None until required preferences are supplied."""
        return self._selected_owners(conflict, validate_preferences(self.decisions))

    def winner(self, conflict):
        """Return the sole selected owner; a safely combined result has no sole owner."""
        selected = self.selected_owners(conflict)
        return selected[0] if selected is not None and len(selected) == 1 else None

    @property
    def applicable_decisions(self):
        choices = validate_preferences(self.decisions)
        known = {pair.identity for pair in group_conflicts(self.observed)}
        return {identity: winner for identity, winner in choices.items() if identity in known}

    @property
    def unresolved(self):
        choices = validate_preferences(self.decisions)
        return tuple(conflict for conflict in self.observed
                     if self._selected_owners(conflict, choices) is None)

    def require_resolved(self):
        if self.unresolved:
            raise ScriptReviewRequired(self.unresolved)
        # Do not allow direct mutation of the public decision mapping to
        # bypass validation before a caller resumes composition.
        for conflict in self.observed:
            self._resolution(conflict, validate_preferences(self.decisions))

    def apply(self, decisions):
        choices = dict(decisions)
        expected = {pair.identity for pair in group_conflicts(self.observed)}
        if choices.keys() - expected:
            raise ValueError('mod preferences include a pair that is not currently conflicting')
        combined = validate_preferences({**self.decisions, **choices})
        if expected - combined.keys():
            raise ValueError('choose a preferred mod for every conflicting pair')
        for conflict in self.observed:
            self._resolution(conflict, combined)
        self.decisions = combined
