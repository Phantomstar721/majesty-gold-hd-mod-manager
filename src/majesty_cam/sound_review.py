"""Whole-record sound choices through the shared mod-pair review."""
from dataclasses import dataclass
from functools import cached_property
import hashlib
import json

from .gpl_function_merge import FunctionMergeError
from .script_review import _ConflictAnalysis


@dataclass(frozen=True)
class SoundCandidate:
    label: str
    item: object
    owner: str


@dataclass(frozen=True)
class SoundConflict:
    key: tuple
    candidates: tuple
    dataset: str = 'any'
    compatibility_groups: tuple = ()
    fixed_preferences: tuple = ()
    detail: str = 'Different sound resources use the same native ID.'
    base: object = None

    @property
    def name(self):
        return self.key[1].decode('ascii', errors='replace')

    @property
    def gameplay_label(self):
        return ('Sound definition: ' if self.key[0] == b'DSND' else 'Sound audio: ') + self.name

    @property
    def gameplay_explanation(self):
        return ('Your preferred mod supplies this sound resource. Anything using '
                'the shared ID will use that version; unrelated sounds are kept.')

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
                raise ValueError('Duplicate effective sound owner')
            result[c.owner] = c
        return result

    def combine(self, owners):
        candidates = self.candidate_map()
        entries = [candidates[o].item for o in owners]
        if not entries or any(e.data != entries[0].data for e in entries):
            raise FunctionMergeError('Sound records require a preferred mod')
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
            raise ValueError('Sound choice changed its native ID')
        return entry


def collect_sound_conflicts(inventories, review, stock, explicit=None):
    from .compose import collapse_native_cam_resources
    labels = {i.selected.alias: (i.selected.package.mod_id.strip('{}').casefold(),
                                 i.selected.package.metadata.display_name) for i in inventories}
    grouped = {}
    for r in collapse_native_cam_resources(r for i in inventories for r in i.resources):
        key = (r.section, r.key)
        if r.section not in (b'DSND', b'WAVE') or stock.get(key) == r.entry.data:
            continue
        resolution = (explicit or {}).get(key)
        entry = resolution.entry if resolution and r.owner in resolution.participant_owners else r.entry
        owner, label = labels[r.owner]
        grouped.setdefault(key, []).append(SoundCandidate(label, entry, owner))
    conflicts = []
    for key, candidates in grouped.items():
        if len({c.item.data for c in candidates}) < 2:
            continue
        conflict = SoundConflict(key, tuple(candidates))
        review.resolve(conflict)
        conflicts.append(conflict)
    return tuple(conflicts)


def sound_resolutions(inventories, review, conflicts, explicit=None):
    from .compose import ScopedNamedResourceResolution
    aliases = {i.selected.package.mod_id.strip('{}').casefold(): i.selected.alias for i in inventories}
    result = dict(explicit or {})
    for conflict in conflicts:
        entry = review.resolve(conflict)
        if entry is None:
            review.require_resolved()
        result[conflict.key] = ScopedNamedResourceResolution(
            entry, frozenset(aliases[c.owner] for c in conflict.candidates))
    return result
