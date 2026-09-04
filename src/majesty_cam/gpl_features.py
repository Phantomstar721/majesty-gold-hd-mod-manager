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


GplFeature = Union[
    StockGplmxPurchaseEquipmentTail,
    StockGplmxPurchaseBazaarTail,
]


def parse_gpl_feature(value: Mapping[str, object]) -> GplFeature:
    feature_type = value.get("type")
    feature_classes = {
        "stock.gplmx-purchase-equipment-tail.v1": StockGplmxPurchaseEquipmentTail,
        "stock.gplmx-purchase-bazaar-tail.v1": StockGplmxPurchaseBazaarTail,
    }
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
    normalized = tuple(sorted(features, key=lambda item: (item.type, item.callback_key.casefold(), item.callback_symbol.casefold())))
    keys: set[tuple[str, str]] = set()
    symbols: set[tuple[str, str]] = set()
    for feature in normalized:
        key = (feature.type, feature.callback_key.casefold())
        symbol = (feature.type, feature.callback_symbol.casefold())
        if key in keys:
            raise GplFeatureError(f"duplicate {feature.type} callback_key: {feature.callback_key!r}")
        if symbol in symbols:
            raise GplFeatureError(f"duplicate {feature.type} callback_symbol: {feature.callback_symbol!r}")
        keys.add(key)
        symbols.add(symbol)
    return normalized


def gpl_feature_mapping(feature: GplFeature) -> dict[str, object]:
    if not isinstance(feature, (StockGplmxPurchaseEquipmentTail, StockGplmxPurchaseBazaarTail)):
        raise GplFeatureError(f"unsupported GPL feature: {feature!r}")
    return asdict(feature)


__all__ = [
    "GplFeature",
    "GplFeatureError",
    "StockGplmxPurchaseEquipmentTail",
    "StockGplmxPurchaseBazaarTail",
    "gpl_feature_mapping",
    "normalize_gpl_features",
    "parse_gpl_feature",
]
