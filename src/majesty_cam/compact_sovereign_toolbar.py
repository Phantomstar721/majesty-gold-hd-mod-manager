"""Typed compact-toolbar references to existing paid sovereign actions.

The shared parser, MMCR registry and AP92 composer consume these bindings;
a toolbar declaration cannot redefine the referenced action's effect or price.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Mapping, Sequence



FEATURE_TYPE = "stock.ap92-sovereign-toolbar-action.v1"


@dataclass(frozen=True)
class ToolbarAction:
    panel_key: str
    action_key: str
    required_level: int
    icon_id: str
    icon_set: int
    hover_text: str
    type: str = FEATURE_TYPE


@dataclass(frozen=True)
class BoundToolbarAction:
    toolbar: ToolbarAction
    panel: StockAp10Ap69SecondaryPanel
    action: StockAp69PaidSourceTargetAction

    @property
    def required_level(self) -> int:
        # An additional presentation origin must never weaken the action gate.
        return max(self.toolbar.required_level, self.action.required_level)

    @property
    def building_family_id(self) -> str:
        return self.panel.building_family_id


def parse(value: Mapping[str, object]) -> ToolbarAction:
    keys = {"type", "panel_key", "action_key", "required_level",
            "icon_id", "icon_set", "hover_text"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("toolbar fields must be exactly " + ", ".join(sorted(keys)))
    if value["type"] != FEATURE_TYPE:
        raise ValueError("unsupported compact toolbar type")
    for key in ("panel_key", "action_key"):
        text = value[key]
        if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", text):
            raise ValueError(f"invalid toolbar {key}")
    level = value["required_level"]
    if type(level) is not int or not 1 <= level <= 3:
        raise ValueError("toolbar required_level must be 1..3")
    icon = value["icon_id"]
    if not isinstance(icon, str) or len(icon) != 4 or not all(33 <= ord(c) <= 126 for c in icon):
        raise ValueError("toolbar icon_id must be four printable ASCII characters")
    image_set = value["icon_set"]
    if type(image_set) is not int or not 0 <= image_set <= 65535:
        raise ValueError("toolbar icon_set must be 0..65535")
    text = value["hover_text"]
    if not isinstance(text, str) or not text.strip() or "\x00" in text:
        raise ValueError("toolbar hover_text must be nonempty text without NUL")
    try:
        encoded = text.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ValueError("toolbar hover_text must use the game's Windows-1252 encoding") from exc
    if len(encoded) > 1024:
        raise ValueError("toolbar hover_text exceeds 1024 bytes")
    return ToolbarAction(**value)


def bind(toolbar: ToolbarAction, features: Sequence[object]) -> BoundToolbarAction:
    """Bind inside one owner package, never through another mod's logical keys."""
    from .stock_controller_features import StockAp10Ap69SecondaryPanel, StockAp69PaidSourceTargetAction
    parse(vars(toolbar))
    panels = [item for item in features if isinstance(item, StockAp10Ap69SecondaryPanel)
              and item.panel_key == toolbar.panel_key]
    actions = [item for item in features if isinstance(item, StockAp69PaidSourceTargetAction)
               and item.panel_key == toolbar.panel_key and item.action_key == toolbar.action_key]
    if len(panels) != 1 or len(actions) != 1:
        raise ValueError("toolbar must reference exactly one owned secondary panel and paid action")
    if toolbar.required_level < actions[0].required_level:
        raise ValueError("toolbar required_level cannot weaken the referenced action")
    return BoundToolbarAction(toolbar, panels[0], actions[0])
