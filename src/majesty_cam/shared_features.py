"""Strict declarations for source-composed events and sampled activity time."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping, Union

EVENT_SIGNATURES = {
    "potion-consumed": ("agent", "string"),
    "reward-flag-paid": ("agent", "agent", "integer"),
    "caravan-delivered": ("agent", "agent", "integer"),
    "tournament-completed": ("agent", "agent", "integer", "integer", "integer"),
    "attack-flag-completed": ("agent", "agent"),
}
EVENT_TYPE = "stock.gameplay-event-observer.v1"
ACTIVITY_TYPE = "stock.activity-duration.v1"
SHARED_FEATURE_TYPES = frozenset((EVENT_TYPE, ACTIVITY_TYPE))
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")


@dataclass(frozen=True)
class StockGameplayEventObserver:
    feature_key: str
    event: str
    callback_symbol: str
    type: str = EVENT_TYPE


@dataclass(frozen=True)
class StockActivityDuration:
    feature_key: str
    api_prefix: str
    condition_callback_symbol: str
    completion_callback_symbol: str
    cancellation_callback_symbol: str
    type: str = ACTIVITY_TYPE


SharedFeature = Union[StockGameplayEventObserver, StockActivityDuration]


def activity_exports(feature: StockActivityDuration) -> tuple[str, ...]:
    return tuple(feature.api_prefix + suffix for suffix in (
        "_Start", "_Pause", "_Resume", "_Cancel", "_Elapsed", "_State",
    ))


def shared_callbacks(feature: SharedFeature) -> tuple[tuple[str, tuple[str, ...], bool], ...]:
    if isinstance(feature, StockGameplayEventObserver):
        return ((feature.callback_symbol, EVENT_SIGNATURES[feature.event], False),)
    context = ("agent", "agent", "agent", "integer")
    return (
        (feature.condition_callback_symbol, context, True),
        (feature.completion_callback_symbol, context, False),
        (feature.cancellation_callback_symbol, (*context, "integer"), False),
    )


def parse_shared_feature(value: Mapping[str, object]) -> SharedFeature:
    kind = value.get("type")
    if kind == EVENT_TYPE:
        expected = {"type", "feature_key", "event", "callback_symbol"}
        symbols = ("callback_symbol",)
    elif kind == ACTIVITY_TYPE:
        expected = {"type", "feature_key", "api_prefix", "condition_callback_symbol",
                    "completion_callback_symbol", "cancellation_callback_symbol"}
        symbols = ("condition_callback_symbol", "completion_callback_symbol",
                   "cancellation_callback_symbol", "api_prefix")
    else:
        raise ValueError(f"unsupported shared feature type: {kind!r}")
    if set(value) != expected:
        raise ValueError(f"{kind}: missing {sorted(expected-set(value))}; "
                         f"unexpected {sorted(set(value)-expected)}")
    key = value["feature_key"]
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("feature_key must be a logical identifier")
    for field in symbols:
        symbol = value[field]
        if (not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol)
                or symbol.casefold().startswith("mm_")):
            raise ValueError(f"{field} must be a package GPL symbol outside reserved MM_ names")
    if kind == EVENT_TYPE:
        event = value["event"]
        if not isinstance(event, str) or event not in EVENT_SIGNATURES:
            raise ValueError(f"unsupported gameplay event: {event!r}")
        return StockGameplayEventObserver(key, event, value["callback_symbol"])
    if len(value["api_prefix"]) > 48:
        raise ValueError("api_prefix must contain at most 48 characters")
    result = StockActivityDuration(key, value["api_prefix"],
                                  value["condition_callback_symbol"],
                                  value["completion_callback_symbol"],
                                  value["cancellation_callback_symbol"])
    names = (*activity_exports(result), *(row[0] for row in shared_callbacks(result)))
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("activity API exports and callbacks must be distinct")
    return result


def shared_feature_mapping(feature: SharedFeature) -> dict[str, object]:
    # Revalidate hand-constructed dataclasses as well as package JSON.
    value = asdict(feature)
    parse_shared_feature(value)
    return value
