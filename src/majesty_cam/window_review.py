"""Whole-window choices through the shared mod-pair review."""
from dataclasses import dataclass
from functools import cached_property
import hashlib
import json

from .gpl_function_merge import FunctionMergeError
from .script_review import _ConflictAnalysis


@dataclass(frozen=True)
class WindowCandidate:
    label: str
    item: object
    owner: str


@dataclass(frozen=True)
class WindowConflict:
    key: tuple
    candidates: tuple
    dataset: str = 'any'
    compatibility_groups: tuple = ()
    fixed_preferences: tuple = ()
    detail: str = 'Different window resources use the same native ID.'
    base: object = None

    @property
    def name(self):
        return self.key[1].decode('ascii', errors='replace')

    @property
    def gameplay_label(self):
        return ('Window layout: ' if self.key[0] == b'SMNU' else 'Window text: ') + self.name

    @property
    def gameplay_explanation(self):
        return ('Your preferred mod supplies this whole window record. Everything '
                'that opens this window uses that version; unrelated windows are kept.')

    @cached_property
    def identity(self):
        evidence = [part.hex() for part in self.key] + [
            (c.owner, hashlib.sha256(c.item.data).hexdigest()) for c in self.candidates]
        return hashlib.sha256(json.dumps(evidence).encode()).hexdigest()

    def candidate_map(self):
        result = {}
        for c in self.candidates:
            self._validate_item(c.item)
            if c.owner in result:
                raise ValueError('Duplicate effective window owner')
            result[c.owner] = c
        return result

    def combine(self, owners):
        candidates = self.candidate_map()
        entries = [candidates[o].item for o in owners]
        if not entries or any(e.data != entries[0].data for e in entries):
            raise FunctionMergeError('Window records require a preferred mod')
        return entries[0]

    @cached_property
    def _analysis(self):
        candidates = self.candidate_map()
        owners = sorted(candidates)
        pairs = tuple((a, b) for i, a in enumerate(owners) for b in owners[i + 1:]
                      if candidates[a].item.data != candidates[b].item.data)
        return _ConflictAnalysis(pairs, None, False)

    @property
    def whole_definition_priority(self):
        return False

    def _validate_item(self, entry):
        if entry.name[:4] != self.key[1]:
            raise ValueError('Window choice changed its native ID')
        return entry


def reviewed_window_resolutions(inventories, resources, review, *, renames=None,
                                resolutions=None, stock_resources=None,
                                text_transform=None, excluded_strt_keys=()):
    """Turn remaining SMNU/STRT window collisions into mod-pair review choices.

    Keys that already have a resolution (an explicit choice or a declared
    window replacement) keep it. Records identical to stock and records
    relocated to a private internal ID never conflict. An ``STRT`` record is
    window text only when a selected package ships that window's ``SMNU``
    record and the merge will emit it - the pairing the text merge uses to
    place panel text. Any other private ``STRT`` bank, such as a GPL text
    table, is left to the normal merge and its conflict error. Each remaining
    collision is observed by ``review``. With a saved pair preference the
    preferred mod's record is chosen; otherwise the first candidate stands in
    provisionally, the conflict stays unresolved in ``review``, and the caller
    must ask for preferences and merge again before using the result.
    """
    from .compose import ScopedNamedResourceResolution

    rename_map = dict(renames or {})
    existing = dict(resolutions or {})
    stock = dict(stock_resources or {})
    excluded = set(excluded_strt_keys)
    window_keys = set()
    for resource in resources:
        if resource.section != b'SMNU':
            continue
        key = rename_map.get((resource.owner, resource.key), resource.key)
        # The merge drops an unresolved SMNU identical to stock, so it is not a
        # shipped window there either.
        if (b'SMNU', key) in existing or stock.get((b'SMNU', key)) != resource.entry.data:
            window_keys.add(key)
    grouped = {}
    for resource in resources:
        section, key = resource.section, resource.key
        if section not in (b'SMNU', b'STRT'):
            continue
        if section == b'STRT' and (key in excluded or key not in window_keys):
            continue
        if rename_map.get((resource.owner, key), key) != key:
            continue
        if (section, key) in existing:
            continue
        if stock.get((section, key)) == resource.entry.data:
            continue
        group = grouped.setdefault((section, key), [])
        if any(owner == resource.owner for owner, _, _ in group):
            continue  # the normal merge reports a duplicated owner record
        compared = resource.entry
        if section == b'STRT' and text_transform is not None:
            compared = text_transform(resource.owner, key, resource.entry)
        group.append((resource.owner, resource.entry, compared))

    conflicting = {key: group for key, group in grouped.items()
                   if len({compared.data for _, _, compared in group}) > 1}
    if not conflicting:
        return {}
    labels = {inventory.selected.alias: (
                  inventory.selected.package.mod_id.strip('{}').casefold(),
                  inventory.selected.package.metadata.display_name)
              for inventory in inventories}
    aliases = {owner_id: alias for alias, (owner_id, _) in labels.items()}
    result = {}
    for (section, key), group in conflicting.items():
        conflict = WindowConflict((section, key), tuple(
            WindowCandidate(labels[owner][1], compared, labels[owner][0])
            for owner, _, compared in group))
        review.resolve(conflict)
        selected = review.selected_owners(conflict)
        chosen = aliases[selected[0]] if selected else group[0][0]
        entry = next(original for owner, original, _ in group if owner == chosen)
        result[(section, key)] = ScopedNamedResourceResolution(
            entry, frozenset(owner for owner, _, _ in group), chosen)
    return result
