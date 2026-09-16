"""Typed, source-composed extensions to stock GPL lifecycles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping, Sequence, Tuple, Union


_LOGICAL_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_GPL_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class GplFeatureError(ValueError):
    """Raised when a declarative GPL extension is unsafe or ambiguous."""


@dataclass(frozen=True)
class StockGplmxPurchaseEquipmentTail:
    """A boolean callback after stock Purchase_Equipment has declined."""

    callback_key: str
    callback_symbol: str
    type: str = "stock.gplmx-purchase-equipment-tail.v1"


@dataclass(frozen=True)
class StockGplmxPurchaseBazaarTail:
    """A boolean callback after stock Purchase_Bazaar has declined."""

    callback_key: str
    callback_symbol: str
    type: str = "stock.gplmx-purchase-bazaar-tail.v1"


@dataclass(frozen=True)
class StockControlledFollowerSpeedSync:
    """Tier-synchronized movement on the stock controlled-monster lifecycle."""

    feature_key: str
    eligibility_callback_symbol: str
    movement_rate_modifier_per_tier: int
    type: str = "stock.controlled-follower-speed-sync.v1"


@dataclass(frozen=True)
class StockHeroQuestLifecycle:
    """Package callbacks at stock hero quest, reset, and death boundaries."""

    feature_key: str
    hero_scripts: Tuple[str, ...]
    resume_callback_symbol: str
    consider_callback_symbol: str
    reset_callback_symbol: str
    death_callback_symbol: str
    type: str = "stock.hero-quest-lifecycle.v1"


GplFeature = Union[
    StockGplmxPurchaseEquipmentTail,
    StockGplmxPurchaseBazaarTail,
    StockControlledFollowerSpeedSync,
    StockHeroQuestLifecycle,
]


_STOCK_HERO_SCRIPTS = frozenset(
    {
        "mx_adept", "mx_barbarian", "mx_cultist", "mx_discord", "mx_dwarf",
        "mx_elf", "mx_gnome", "mx_healer", "mx_monk", "mx_paladin",
        "mx_priestess", "mx_ranger", "mx_rogue", "mx_solarus",
        "mx_warrior", "mx_wizard",
    }
)


def parse_gpl_feature(value: Mapping[str, object]) -> GplFeature:
    feature_type = value.get("type")
    feature_classes = {
        "stock.gplmx-purchase-equipment-tail.v1": StockGplmxPurchaseEquipmentTail,
        "stock.gplmx-purchase-bazaar-tail.v1": StockGplmxPurchaseBazaarTail,
    }
    if feature_type == "stock.controlled-follower-speed-sync.v1":
        expected = {
            "type",
            "feature_key",
            "eligibility_callback_symbol",
            "movement_rate_modifier_per_tier",
        }
        if set(value) != expected:
            missing = sorted(expected - set(value))
            extra = sorted(set(value) - expected)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unexpected " + ", ".join(extra))
            raise GplFeatureError(
                "invalid controlled-follower movement fields: " + "; ".join(details)
            )
        feature_key = value["feature_key"]
        callback_symbol = value["eligibility_callback_symbol"]
        modifier = value["movement_rate_modifier_per_tier"]
        if not isinstance(feature_key, str) or not _LOGICAL_KEY.fullmatch(feature_key):
            raise GplFeatureError("feature_key must be a logical identifier")
        if not isinstance(callback_symbol, str) or not _GPL_SYMBOL.fullmatch(callback_symbol):
            raise GplFeatureError(
                "eligibility_callback_symbol must be a GPL function name"
            )
        if (
            not isinstance(modifier, int)
            or isinstance(modifier, bool)
            or not -10000 <= modifier <= -1
        ):
            raise GplFeatureError(
                "movement_rate_modifier_per_tier must be an integer from -10000 to -1"
            )
        return StockControlledFollowerSpeedSync(
            feature_key, callback_symbol, modifier
        )
    if feature_type == "stock.hero-quest-lifecycle.v1":
        expected = {
            "type", "feature_key", "hero_scripts", "resume_callback_symbol",
            "consider_callback_symbol", "reset_callback_symbol",
            "death_callback_symbol",
        }
        if set(value) != expected:
            missing = sorted(expected - set(value))
            extra = sorted(set(value) - expected)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unexpected " + ", ".join(extra))
            raise GplFeatureError(
                "invalid hero-quest lifecycle fields: " + "; ".join(details)
            )
        feature_key = value["feature_key"]
        scripts = value["hero_scripts"]
        if not isinstance(feature_key, str) or not _LOGICAL_KEY.fullmatch(feature_key):
            raise GplFeatureError("feature_key must be a logical identifier")
        if not isinstance(scripts, (list, tuple)) or not 1 <= len(scripts) <= 16:
            raise GplFeatureError("hero_scripts must contain 1..16 stock script names")
        normalized_scripts = []
        seen_scripts = set()
        for script in scripts:
            if not isinstance(script, str) or script.casefold() not in _STOCK_HERO_SCRIPTS:
                raise GplFeatureError(f"unsupported stock hero script: {script!r}")
            folded = script.casefold()
            if folded in seen_scripts:
                raise GplFeatureError(f"duplicate stock hero script: {script!r}")
            seen_scripts.add(folded)
            normalized_scripts.append(folded)
        symbols = []
        for field_name in (
            "resume_callback_symbol", "consider_callback_symbol",
            "reset_callback_symbol", "death_callback_symbol",
        ):
            symbol = value[field_name]
            if not isinstance(symbol, str) or not _GPL_SYMBOL.fullmatch(symbol):
                raise GplFeatureError(f"{field_name} must be a GPL function name")
            symbols.append(symbol)
        if len({symbol.casefold() for symbol in symbols}) != 4:
            raise GplFeatureError("hero-quest lifecycle callbacks must be distinct")
        return StockHeroQuestLifecycle(
            feature_key=feature_key,
            hero_scripts=tuple(sorted(normalized_scripts)),
            resume_callback_symbol=symbols[0],
            consider_callback_symbol=symbols[1],
            reset_callback_symbol=symbols[2],
            death_callback_symbol=symbols[3],
        )
    if feature_type not in feature_classes:
        raise GplFeatureError(f"unsupported GPL feature type: {feature_type!r}")
    expected = {"type", "callback_key", "callback_symbol"}
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise GplFeatureError("invalid GPL tail feature fields: " + "; ".join(details))
    callback_key = value["callback_key"]
    callback_symbol = value["callback_symbol"]
    if not isinstance(callback_key, str) or not _LOGICAL_KEY.fullmatch(callback_key):
        raise GplFeatureError("callback_key must be a logical identifier")
    if not isinstance(callback_symbol, str) or not _GPL_SYMBOL.fullmatch(callback_symbol):
        raise GplFeatureError("callback_symbol must be a GPL function name")
    return feature_classes[feature_type](callback_key, callback_symbol)


def normalize_gpl_features(features: Sequence[GplFeature]) -> Tuple[GplFeature, ...]:
    normalized = tuple(sorted(features, key=_gpl_feature_sort_key))
    keys: set[tuple[str, str]] = set()
    symbols: set[tuple[str, str]] = set()
    for feature in normalized:
        logical_key = (
            feature.feature_key
            if isinstance(feature, (StockControlledFollowerSpeedSync, StockHeroQuestLifecycle))
            else feature.callback_key
        )
        callback_symbols = (
            (feature.eligibility_callback_symbol,)
            if isinstance(feature, StockControlledFollowerSpeedSync)
            else (
                (
                    feature.resume_callback_symbol,
                    feature.consider_callback_symbol,
                    feature.reset_callback_symbol,
                    feature.death_callback_symbol,
                )
                if isinstance(feature, StockHeroQuestLifecycle)
                else (feature.callback_symbol,)
            )
        )
        key = (feature.type, logical_key.casefold())
        if key in keys:
            raise GplFeatureError(
                f"duplicate {feature.type} feature key: {logical_key!r}"
            )
        keys.add(key)
        for callback_symbol in callback_symbols:
            symbol = (feature.type, callback_symbol.casefold())
            if symbol in symbols:
                raise GplFeatureError(
                    f"duplicate {feature.type} callback symbol: {callback_symbol!r}"
                )
            symbols.add(symbol)
    return normalized


def gpl_feature_mapping(feature: GplFeature) -> dict[str, object]:
    if not isinstance(
        feature,
        (
            StockGplmxPurchaseEquipmentTail,
            StockGplmxPurchaseBazaarTail,
            StockControlledFollowerSpeedSync,
            StockHeroQuestLifecycle,
        ),
    ):
        raise GplFeatureError(f"unsupported GPL feature: {feature!r}")
    return asdict(feature)


def _gpl_feature_sort_key(feature: GplFeature) -> tuple[str, str, str]:
    if isinstance(feature, StockControlledFollowerSpeedSync):
        return (
            feature.type,
            feature.feature_key.casefold(),
            feature.eligibility_callback_symbol.casefold(),
        )
    if isinstance(feature, StockHeroQuestLifecycle):
        return (
            feature.type,
            feature.feature_key.casefold(),
            feature.resume_callback_symbol.casefold(),
        )
    return (
        feature.type,
        feature.callback_key.casefold(),
        feature.callback_symbol.casefold(),
    )


__all__ = [
    "GplFeature",
    "GplFeatureError",
    "StockGplmxPurchaseEquipmentTail",
    "StockGplmxPurchaseBazaarTail",
    "StockControlledFollowerSpeedSync",
    "StockHeroQuestLifecycle",
    "gpl_feature_mapping",
    "normalize_gpl_features",
    "parse_gpl_feature",
]
