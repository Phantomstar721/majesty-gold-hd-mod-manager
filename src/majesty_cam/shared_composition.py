"""Validation and deterministic bindings for shared GPL services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .gpl import DefinitionKind, ParsedSemanticSource
from .gameplay_events import require_callback
from .shared_features import (SharedFeature, StockActivityDuration,
                              StockGameplayEventObserver, activity_exports,
                              shared_callbacks, shared_feature_mapping)


@dataclass(frozen=True)
class SharedBinding:
    mod_id: str
    feature: SharedFeature

    @property
    def identity(self) -> str:
        return self.mod_id + ":" + self.feature.feature_key.casefold()


def validate_shared_bindings(
    packages: Iterable[tuple[str, Sequence[SharedFeature], Sequence[ParsedSemanticSource]]],
) -> tuple[SharedBinding, ...]:
    result = []
    claimed = {}
    keys = set()
    all_functions = set()
    exports = set()
    for mod_id, features, sources in packages:
        functions = {}
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:
                    functions.setdefault(item.normalized_name, []).append(item)
                    all_functions.add(item.normalized_name)
        for feature in features:
            shared_feature_mapping(feature)
            key = (mod_id, feature.type, feature.feature_key.casefold())
            if key in keys:
                raise ValueError(f"duplicate shared feature {key}")
            keys.add(key)
            for symbol, types, boolean in shared_callbacks(feature):
                matches = functions.get(symbol.casefold(), ())
                if len(matches) != 1:
                    raise ValueError(f"{mod_id}: callback {symbol!r} requires exactly one "
                                     "package-owned function")
                require_callback(matches[0], symbol, types, boolean)
                # One function may intentionally observe two events with the
                # same argument shape, but another package must not own it.
                prior = claimed.setdefault(symbol.casefold(), mod_id)
                if prior != mod_id:
                    raise ValueError(f"shared callback {symbol!r} is owned by both {prior} and {mod_id}")
            if isinstance(feature, StockActivityDuration):
                for symbol in activity_exports(feature):
                    if symbol.casefold() in exports:
                        raise ValueError(f"duplicate activity API export {symbol!r}")
                    exports.add(symbol.casefold())
            result.append(SharedBinding(mod_id, feature))
    collisions = exports & all_functions
    if collisions:
        raise ValueError(f"generated activity API collides with package functions: {sorted(collisions)}")
    return tuple(sorted(result, key=lambda b: (b.feature.type, b.mod_id,
                                               b.feature.feature_key.casefold())))


def event_subscribers(bindings: Sequence[SharedBinding]) -> dict[str, tuple[str, ...]]:
    groups = {}
    for binding in bindings:
        feature = binding.feature
        if isinstance(feature, StockGameplayEventObserver):
            groups.setdefault(feature.event, []).append(feature.callback_symbol)
    return {key: tuple(values) for key, values in groups.items()}
