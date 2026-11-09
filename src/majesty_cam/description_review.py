"""XML records use the same mod-pair preference policy as script definitions."""
from dataclasses import dataclass
from functools import cached_property
import hashlib
import json

from .descriptions import (DescriptionsDocument, DescriptionMergeConflict,
                           merge_descriptions, parse_descriptions)
from .gpl_function_merge import FunctionMergeError
from .script_review import _ConflictAnalysis


@dataclass(frozen=True)
class DescriptionReviewCandidate:
    label: str
    item: object
    owner: str


@dataclass(frozen=True)
class DescriptionReviewConflict:
    dataset: str
    key: tuple
    name: str
    detail: str
    base: object
    candidates: tuple
    compatibility_groups: tuple = ()
    fixed_preferences: tuple = ()

    @property
    def gameplay_label(self):
        element = self.candidates[0].item.to_element()
        category = 'Building' if element.get('subType') == 'Building' else 'Game object'
        return category + ': ' + self.name.replace('_', ' ')

    @property
    def gameplay_explanation(self):
        return 'These mods change the same object settings. Your preferred mod supplies the conflicting version.'

    @cached_property
    def identity(self):
        evidence = [self.dataset, self.key, self.base.payload.hex() if self.base else None,
                    [(c.owner, c.item.payload.hex()) for c in self.candidates]]
        return hashlib.sha256(json.dumps(evidence).encode()).hexdigest()

    def candidate_map(self):
        result = {}
        for candidate in self.candidates:
            if candidate.item.key != self.key:
                raise ValueError('XML candidate key disagrees with its conflict')
            previous = result.get(candidate.owner)
            if previous and previous.item._fingerprint != candidate.item._fingerprint:
                raise ValueError('One mod supplies multiple effective XML records')
            result[candidate.owner] = candidate
        if not result:
            raise ValueError('XML review requires an authored candidate')
        return result

    def combine(self, owners):
        candidates = self.candidate_map()
        variants = [(owner, DescriptionsDocument('Majesty', (), (candidates[owner].item,)))
                    for owner in owners]
        try:
            merged = merge_descriptions(b'<Majesty/>', variants,
                field_merge_stock={self.key: self.base} if self.base else {})
        except DescriptionMergeConflict as exc:
            raise FunctionMergeError(str(exc)) from exc
        return merged.document.index[self.key]

    @cached_property
    def _analysis(self):
        owners = tuple(sorted(self.candidate_map()))
        try:
            return _ConflictAnalysis((), self.combine(owners), False)
        except FunctionMergeError:
            pass
        pairs = tuple((left, right) for i, left in enumerate(owners) for right in owners[i + 1:])
        incompatible = []
        for pair in pairs:
            try:
                self.combine(pair)
            except FunctionMergeError:
                incompatible.append(pair)
        return _ConflictAnalysis(tuple(incompatible) or pairs, None, not incompatible)

    @property
    def whole_definition_priority(self):
        return self._analysis.whole_definition_priority

    def _validate_item(self, item):
        document = parse_descriptions(b'<Majesty>' + item.payload + b'</Majesty>')
        if len(document.records) != 1 or document.records[0].key != self.key:
            raise ValueError('XML choice must preserve its object identity')
        return item
