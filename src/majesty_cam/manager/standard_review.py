"""Adapt native load-order choices to the common grouped preference window."""
from dataclasses import dataclass
from types import SimpleNamespace

from ..script_review import _ConflictAnalysis, pair_key
from .conflict_preview import rule_label
from .build import _standard_order_has_cycle


@dataclass(frozen=True)
class StandardReviewConflict:
    source: object
    dataset: str = 'any'
    fixed_preferences: tuple = ()
    compatibility_groups: tuple = ()

    @property
    def identity(self):
        return 'standard:' + self.source.pair_key

    @property
    def candidates(self):
        return tuple(SimpleNamespace(owner=o, label=n, item=o) for o, n in (
            (self.source.left_id, self.source.left_name),
            (self.source.right_id, self.source.right_name)))

    def candidate_map(self):
        return {c.owner: c for c in self.candidates}

    @property
    def _analysis(self):
        return _ConflictAnalysis(((self.source.left_id, self.source.right_id),), None, False)

    @property
    def gameplay_label(self):
        return ', '.join(sorted({rule_label(k) for k in self.source.change_keys}))

    @property
    def gameplay_explanation(self):
        return ('These Standard mods use native load order. The preferred mod loads last '
                'and supplies their overlapping content. Both mods stay enabled.\n'
                'Affected definitions: ' + ', '.join(self.source.change_keys))

    def combine(self, owners):
        if len(owners) != 1:
            raise ValueError('Choose one Standard mod for each pair.')
        return owners[0]

    def _validate_item(self, item):
        if item not in self.candidate_map():
            raise ValueError('Invalid Standard mod choice.')
        return item


def native_choices(conflicts, decisions):
    return {c.pair_key: decisions[pair_key(c.left_id, c.right_id)] for c in conflicts}


def validate_native_choices(catalog, selections, choices):
    entries = {e.content_id: e for e in catalog.standard
               if selections.get(e.content_id) and e.selectable}
    if _standard_order_has_cycle(entries, set(entries), choices):
        raise ValueError('These preferences conflict with each other or required load order. '
                         'Change a preferred mod before saving.')
