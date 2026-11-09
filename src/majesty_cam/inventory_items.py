"""Package-owned numeric items extending the stock hero death exclusion."""
from dataclasses import dataclass, asdict
import re

from .gpl import DefinitionKind

TYPE = "stock.inventory-death-drop-exclusion.v1"


@dataclass(frozen=True)
class InventoryDeathDropExclusion:
    feature_key: str
    item_expression: str
    type: str = TYPE


def parse(value):
    if set(value) != {"type", "feature_key", "item_expression"} or value.get("type") != TYPE:
        raise ValueError("invalid inventory death-drop exclusion fields")
    if not isinstance(value["feature_key"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", value["feature_key"]):
        raise ValueError("feature_key must be a logical identifier")
    if not isinstance(value["item_expression"], str) or not re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_]{0,63}", value["item_expression"]):
        raise ValueError("item_expression must name a GPL expression")
    return InventoryDeathDropExclusion(value["feature_key"], value["item_expression"])


def mapping(feature):
    return asdict(feature)


def bindings(inventories, parsed_by_owner):
    """Require each declaration's literal numeric ID in that package's source."""
    result = []
    owners = {}
    for inventory in inventories:
        alias = inventory.selected.alias
        definition = getattr(getattr(inventory.selected, "package", None), "definition", None)
        for feature in getattr(definition, "runtime_features", ()):
            if not isinstance(feature, InventoryDeathDropExclusion):
                continue
            matches = [item for source in parsed_by_owner[alias] for item in source.items
                       if item.kind == DefinitionKind.EXPRESSION
                       and item.name.casefold() == feature.item_expression.casefold()]
            if len(matches) != 1:
                raise ValueError(f"{alias}: inventory exclusion requires one package-owned {feature.item_expression}")
            match = re.fullmatch(r"\s*expression\s+#[A-Za-z_][A-Za-z0-9_]*\s+(\d+)\s*", matches[0].text, re.I)
            if not match or not 0 <= int(match[1]) <= 127:
                raise ValueError(f"{alias}: inventory exclusion requires a literal item ID in 0..127 (stock signed QITM index)")
            number = int(match[1])
            if number in owners:
                raise ValueError(f"inventory item ID {number} has multiple exclusion owners: {owners[number]}, {alias}")
            owners[number] = alias
            result.append(feature.item_expression)
    return tuple(result)
