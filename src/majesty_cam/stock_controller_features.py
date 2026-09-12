"""Bounded stock-lifecycle recipes for controller-backed custom content.

This module is deliberately data-only.  It does not describe patch sites,
addresses, DLLs, bytecode, timers, or replacement controller implementations.
Each record selects one stock lifecycle that has already been traced in the
manager runtime:

* AP10 opens and owns an AP69-shaped secondary panel, including the native
  creation, context hand-off, Back transition, replacement, and destructor
  boundaries.
* AP22 publishes a building-owned packed resource count.
* AP99 owns research descriptor allocation, eligibility, command submission,
  completion, presentation, and quest-unload cleanup.
* AP17 applies an upgrade prerequisite only after the stock presenter has
  finished and after every stock event refresh.
* AP24 owns Rage command metadata, treasury validation, Palace-wide exclusion,
  progress presentation, deterministic GPL dispatch, and effector cleanup.
* AP69 owns temple-row construction and the complete sovereign target,
  cancellation, repeat-cast, command, and spell-unit lifecycle.
* MX09 opens an AP41-shaped reward panel, and AP41/Fl00 own private hostile-
  monster reward placement, debit, cancellation, completion, and cleanup.
* MX22 owns persistent building-open state and mutually exclusive paired
  controls; the generic clone omits the Embassy's separate recruit order.

These records are the bounded manager-side contract for the runtime's
stock-controller registry. Package JSON must be validated into these records
by the manager; the runtime consumes only a manager-generated binary registry,
never raw package JSON.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import re
from typing import Iterable, Mapping, Optional, Sequence, Tuple, Union


LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY = (
    "alchemist.cgbrewing-secondary-controller"
)

CONTROLLER_FEATURE_FORMAT = "majesty.stock-controller-features"
CONTROLLER_FEATURE_FORMAT_VERSION = 1

MAX_CONTROLLER_FEATURES = 256
MAX_SECONDARY_PANELS = 32
MAX_FEATURE_TEXT_BYTES = 96
MAX_CALLBACK_SYMBOL_BYTES = 64
MAX_CANONICAL_FEATURE_BYTES = 256 * 1024

# Both supported executables' stock AP99 row iterators hard-gate controls to
# this half-open interval.  Private descriptor keys must live outside the
# complete stock discovery namespace, not merely avoid the 26 keys observed in
# one stock registry build.
_STOCK_AP99_CONTROL_ID_BEGIN = 0x1388
_STOCK_AP99_CONTROL_ID_END = 0x13EC

# AP99 constructs exactly these 26 stock research descriptors in both
# supported executables (public 0x004A7C20 -> 0x004A7AF0; beta2
# 0x004A8510 -> 0x004A83E0).  The surrounding discovery interval above is
# deliberately broader: private action IDs must avoid every slot the stock row
# iterator can discover, while a stock *template* must name a descriptor that
# AP99 actually constructs.
_PROVEN_STOCK_AP99_DESCRIPTOR_CONTROL_IDS = frozenset(
    (
        *range(0x1388, 0x138E),
        0x1392,
        *range(0x139C, 0x139E),
        *range(0x13A6, 0x13AC),
        *range(0x13B0, 0x13B4),
        0x13BA,
        *range(0x13C5, 0x13CB),
    )
)

# These are bounded v1 template relationships, not arbitrary spell-descriptor
# extension points.  They are the exact stock metadata already traced for the
# Alchemist compatibility path in both supported executables:
#
# * AP24 timed action: Fervus Healing (0x1140) supplies the AP69 row shape;
#   Petrify (0x113E) supplies the level-three, 1500-gold metadata.
# * AP24 command visual: Fervus Vines (0x1132) is a level-three row.
# * AP69 sovereign visual: Fervus's 0x1133 row supplies the presentation shape.
# * AP69 target: Vines (0x1132) owns Sp23 and stock level three.
#
# Adding another tuple requires its own stock trace and tests; accepting an
# arbitrary nonzero ID here would defer a malformed package until panel-open
# time, after Build had incorrectly advertised it as compatible.
_PROVEN_AP24_TIMED_TEMPLATE_METADATA = {
    (0x1140, 0x113E): (3, 1500),
}
_PROVEN_AP24_RAGE_VISUAL_TEMPLATE_LEVELS = {
    0x1132: 3,
}
_PROVEN_AP69_SOVEREIGN_VISUAL_TEMPLATES = frozenset((0x1133,))
_PROVEN_AP69_SOVEREIGN_TARGET_TEMPLATE_METADATA = {
    0x1132: ("Sp23", 3),
}

_LOGICAL_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_GPL_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class ControllerFeatureError(ValueError):
    """Raised when a controller recipe is ambiguous, unsafe, or incomplete."""


@dataclass(frozen=True)
class StockAp10Ap69SecondaryPanel:
    """An AP10-owned secondary panel using AP69's stock controller lifecycle."""

    panel_key: str
    parent_building: str
    source_dialog_id: str
    building_family_id: str
    open_command_id: int
    type: str = "stock.ap10-ap69-secondary-panel.v1"


@dataclass(frozen=True)
class StockMx09Ap41RewardPanel:
    """An MX09-shaped building opening AP41's stock reward panel lifecycle."""

    panel_key: str
    parent_building: str
    source_dialog_id: str
    open_command_id: int
    type: str = "stock.mx09-ap41-reward-panel.v1"


@dataclass(frozen=True)
class StockMx04Mx05OccupantActionPanel:
    """MX05's native occupant selection, queued payment, and GPL action."""

    panel_key: str
    parent_building: str
    source_dialog_id: str
    open_command_id: int
    cost_callback_symbol: str
    action_callback_symbol: str
    type: str = "stock.mx04-mx05-occupant-action-panel.v1"


@dataclass(frozen=True)
class StockAp08Mx05QuestBoardPanel:
    """One MX05-native Refresh row backed by the live AP08 Guild agent."""

    panel_key: str
    parent_building: str
    source_dialog_id: str
    open_command_id: int
    offer_count_callback_symbol: str
    revision_callback_symbol: str
    offer_name_text: str
    offer_goal_text: str
    offer_reward_callback_symbol: str
    refresh_cost_callback_symbol: str
    refresh_callback_symbol: str
    type: str = "stock.ap08-mx05-quest-list-panel.v4"


@dataclass(frozen=True)
class StockMx22BuildingOpenToggle:
    """MX22's persistent per-building open/closed state and paired controls."""

    toggle_key: str
    parent_building: str
    open_command_id: int
    close_command_id: int
    type: str = "stock.mx22-building-open-toggle.v1"


@dataclass(frozen=True)
class StockAp41Fl00HostileMonsterFlag:
    """AP41/Fl00 reward placement restricted to hostile stock monsters."""

    panel_key: str
    action_key: str
    private_mode: str
    private_flag_id: str
    cursor_ordinal: int
    availability_attribute_id: Optional[str]
    unavailable_alert_text: Optional[str]
    type: str = "stock.ap41-fl00-hostile-monster-flag.v1"


@dataclass(frozen=True)
class StockAp22ResourceMeter:
    """One AP22-shaped display of a building-owned packed resource."""

    panel_key: str
    resource_key: str
    attribute_id: str
    label_control_id: int
    count_control_id: int
    binding_control_id: int
    type: str = "stock.ap22-resource-meter.v1"


@dataclass(frozen=True)
class StockAp99ResearchRow:
    """One stock AP99 research descriptor, command, and completion row."""

    panel_key: str
    recipe_key: str
    action_control_id: int
    descriptor_template_control_id: int
    completion_template_control_id: int
    required_level: int
    price: int
    price_control_id: int
    progress_control_id: int
    active_display_control_id: int
    icon_control_id: int
    completion_text: str
    type: str = "stock.ap99-research-row.v1"


@dataclass(frozen=True)
class UpgradeRequirement:
    building_level: int
    recipe_key: str


@dataclass(frozen=True)
class StockAp17UpgradeResearchGate:
    """AP17's post-presenter upgrade gate, keyed to AP99 completion rows."""

    panel_key: str
    parent_building: str
    upgrade_control_id: int
    upgrade_price_control_id: int
    requirements: Tuple[UpgradeRequirement, ...]
    type: str = "stock.ap17-upgrade-research-gate.v1"


@dataclass(frozen=True)
class StockAp24TimedRageAction:
    """AP24 Rage command and active-progress lifecycle with a private GPL clone."""

    panel_key: str
    action_key: str
    action_control_id: int
    descriptor_template_control_id: int
    level_price_template_control_id: int
    required_level: int
    gold_cost: int
    resource_key: str
    resource_cost: int
    callback_symbol: str
    duration_ms: int
    icon_control_id: int
    price_control_id: int
    progress_control_id: int
    active_display_control_id: int
    type: str = "stock.ap24-timed-rage-action.v1"


@dataclass(frozen=True)
class StockAp24RageCommandAction:
    """One-shot AP24 Rage command dispatch with a private GPL clone."""

    panel_key: str
    action_key: str
    action_control_id: int
    visual_template_control_id: int
    completion_template_research_control_id: int
    required_level: int
    resource_key: str
    resource_cost: int
    callback_symbol: str
    icon_control_id: int
    price_control_id: int
    type: str = "stock.ap24-rage-command-action.v1"


@dataclass(frozen=True)
class StockAp69SovereignTargetAction:
    """AP69 temple targeting with manager-private mode, unit, and cursor IDs."""

    panel_key: str
    action_key: str
    visual_control_id: int
    private_control_id: int
    visual_template_control_id: int
    target_template_control_id: int
    stock_target_mode: str
    stock_executor_mode: str
    private_mode: str
    private_unit_id: str
    cursor_ordinal: int
    required_level: int
    resource_key: str
    resource_cost: int
    icon_control_id: int
    price_control_id: int
    type: str = "stock.ap69-sovereign-target-action.v1"


ControllerFeature = Union[
    StockMx22BuildingOpenToggle,
    StockMx04Mx05OccupantActionPanel,
    StockAp08Mx05QuestBoardPanel,
    StockAp10Ap69SecondaryPanel,
    StockMx09Ap41RewardPanel,
    StockAp41Fl00HostileMonsterFlag,
    StockAp22ResourceMeter,
    StockAp99ResearchRow,
    StockAp17UpgradeResearchGate,
    StockAp24TimedRageAction,
    StockAp24RageCommandAction,
    StockAp69SovereignTargetAction,
]


_FEATURE_TYPES = {
    "stock.mx22-building-open-toggle.v1": StockMx22BuildingOpenToggle,
    "stock.mx04-mx05-occupant-action-panel.v1": StockMx04Mx05OccupantActionPanel,
    "stock.ap08-mx05-quest-list-panel.v4": StockAp08Mx05QuestBoardPanel,
    "stock.ap10-ap69-secondary-panel.v1": StockAp10Ap69SecondaryPanel,
    "stock.mx09-ap41-reward-panel.v1": StockMx09Ap41RewardPanel,
    "stock.ap41-fl00-hostile-monster-flag.v1": StockAp41Fl00HostileMonsterFlag,
    "stock.ap22-resource-meter.v1": StockAp22ResourceMeter,
    "stock.ap99-research-row.v1": StockAp99ResearchRow,
    "stock.ap17-upgrade-research-gate.v1": StockAp17UpgradeResearchGate,
    "stock.ap24-timed-rage-action.v1": StockAp24TimedRageAction,
    "stock.ap24-rage-command-action.v1": StockAp24RageCommandAction,
    "stock.ap69-sovereign-target-action.v1": StockAp69SovereignTargetAction,
}

_FEATURE_ORDER = {name: index for index, name in enumerate(_FEATURE_TYPES)}


def legacy_alchemist_controller_features(
    parent_building: str,
) -> Tuple[ControllerFeature, ...]:
    """Translate the legacy Alchemist capability into generic stock recipes.

    ``parent_building`` is supplied from the package's declared building, so
    this compatibility adapter contains no package UUID or display-name test.
    Every numeric value below is the exact value used by the proven legacy
    runtime and is grouped by the stock lifecycle that owns it.
    """

    # Preserve the legacy package's exact values while expressing each one as
    # a reusable, stock-derived recipe.  The generated MMCR registry and native
    # runtime contain only these generic recipe types; the compatibility alias
    # and the package identity stop at this adapter.

    panel = "brewing"
    resource = "reagents"
    weapon_oil = "weapon-oil"
    phoenix_phial = "phoenix-phial"
    return normalize_controller_features(
        (
            StockAp10Ap69SecondaryPanel(
                panel_key=panel,
                parent_building=parent_building,
                source_dialog_id="CGBR",
                building_family_id="ALB",
                open_command_id=0x1F49,
            ),
            StockAp22ResourceMeter(
                panel_key=panel,
                resource_key=resource,
                attribute_id="APV0",
                label_control_id=0x2A23,
                count_control_id=0x2A24,
                binding_control_id=0x2A25,
            ),
            StockAp99ResearchRow(
                panel_key=panel,
                recipe_key=weapon_oil,
                action_control_id=0x2A13,
                descriptor_template_control_id=0x139C,
                completion_template_control_id=0x139C,
                required_level=1,
                price=250,
                price_control_id=0x2A13 + 1000,
                progress_control_id=0x2A11,
                active_display_control_id=0x2A12,
                icon_control_id=0,
                completion_text="Weapon Oil",
            ),
            StockAp99ResearchRow(
                panel_key=panel,
                recipe_key=phoenix_phial,
                action_control_id=0x2A16,
                descriptor_template_control_id=0x139C,
                completion_template_control_id=0x13B3,
                required_level=2,
                price=750,
                price_control_id=0x2A16 + 1000,
                progress_control_id=0x2A17,
                active_display_control_id=0x2A18,
                icon_control_id=0x2A16 + 500,
                completion_text="Phoenix Phial",
            ),
            StockAp17UpgradeResearchGate(
                panel_key=panel,
                parent_building=parent_building,
                upgrade_control_id=0x1F47,
                upgrade_price_control_id=0x1F4F,
                requirements=(
                    UpgradeRequirement(1, weapon_oil),
                    UpgradeRequirement(2, phoenix_phial),
                ),
            ),
            StockAp24TimedRageAction(
                panel_key=panel,
                action_key="vigor-elixir",
                action_control_id=0x2A10,
                descriptor_template_control_id=0x1140,
                level_price_template_control_id=0x113E,
                required_level=3,
                gold_cost=1500,
                resource_key=resource,
                resource_cost=1,
                callback_symbol="Alchemist_DoInvigoratingElixer",
                duration_ms=30000,
                icon_control_id=0x2A10 + 1000,
                price_control_id=0x2A10 - 1000,
                progress_control_id=0x2009,
                active_display_control_id=0x227A,
            ),
            StockAp24RageCommandAction(
                panel_key=panel,
                action_key="arcane-infusion",
                action_control_id=0x1132,
                visual_template_control_id=0x1132,
                completion_template_research_control_id=0x139C,
                required_level=3,
                resource_key=resource,
                resource_cost=10,
                callback_symbol="Alchemist_Arcane_Infusion",
                icon_control_id=0x1132 + 1000,
                price_control_id=0x1132 - 1000,
            ),
            StockAp69SovereignTargetAction(
                panel_key=panel,
                action_key="philosophers-stone",
                visual_control_id=0x1133,
                private_control_id=0x2A21,
                visual_template_control_id=0x1133,
                target_template_control_id=0x1132,
                stock_target_mode="Sp23",
                stock_executor_mode="Sp14",
                private_mode="AlS1",
                private_unit_id="ALS1",
                cursor_ordinal=39,
                required_level=3,
                resource_key=resource,
                resource_cost=10,
                icon_control_id=0x1133 + 1000,
                price_control_id=0x1133 - 1000,
            ),
        )
    )


def legacy_controller_features(
    capabilities: Iterable[str],
    *,
    parent_building: Optional[str] = None,
) -> Tuple[ControllerFeature, ...]:
    """Translate recognized v2 controller aliases, rejecting missing context."""

    requested = frozenset(capabilities)
    if LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY not in requested:
        return ()
    if parent_building is None:
        raise ControllerFeatureError(
            "the legacy Alchemist controller capability requires its declared "
            "parent building local_name"
        )
    return legacy_alchemist_controller_features(parent_building)


def normalize_controller_features(
    features_to_normalize: Iterable[ControllerFeature],
) -> Tuple[ControllerFeature, ...]:
    """Validate, deduplicate, and deterministically order controller recipes."""

    raw = tuple(features_to_normalize)
    if len(raw) > MAX_CONTROLLER_FEATURES:
        raise ControllerFeatureError(
            f"controller feature count exceeds {MAX_CONTROLLER_FEATURES}"
        )
    canonical_by_record = {}
    for feature in raw:
        canonical = _validate_feature(feature)
        canonical_by_record[_canonical_record_bytes(canonical)] = canonical
    features = tuple(
        sorted(canonical_by_record.values(), key=_feature_sort_key)
    )
    _validate_composition(features)
    return features


def parse_controller_feature(value: Mapping[str, object]) -> ControllerFeature:
    """Parse one exact author/adapter record; unknown fields fail closed."""

    if not isinstance(value, Mapping):
        raise ControllerFeatureError("controller feature must be an object")
    feature_type = value.get("type")
    if not isinstance(feature_type, str) or feature_type not in _FEATURE_TYPES:
        raise ControllerFeatureError(
            f"unsupported controller feature type: {feature_type!r}"
        )
    cls = _FEATURE_TYPES[feature_type]
    expected = {field.name for field in fields(cls)}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise ControllerFeatureError(
            "controller feature fields are invalid: " + "; ".join(details)
        )
    arguments = dict(value)
    if cls is StockAp17UpgradeResearchGate:
        raw_requirements = arguments["requirements"]
        if not isinstance(raw_requirements, (list, tuple)):
            raise ControllerFeatureError("requirements must be an array")
        parsed_requirements = []
        for index, requirement in enumerate(raw_requirements):
            if not isinstance(requirement, Mapping) or set(requirement) != {
                "building_level",
                "recipe_key",
            }:
                raise ControllerFeatureError(
                    f"requirements[{index}] must contain exactly building_level and recipe_key"
                )
            parsed_requirements.append(
                UpgradeRequirement(
                    building_level=requirement["building_level"],  # type: ignore[arg-type]
                    recipe_key=requirement["recipe_key"],  # type: ignore[arg-type]
                )
            )
        arguments["requirements"] = tuple(parsed_requirements)
    try:
        feature = cls(**arguments)
    except TypeError as exc:
        raise ControllerFeatureError(
            f"invalid {feature_type} controller feature"
        ) from exc
    return _validate_feature(feature)


def controller_feature_mapping(feature: ControllerFeature) -> dict:
    """Return the exact JSON-ready mapping for one validated record."""

    feature = _validate_feature(feature)
    value = asdict(feature)
    if isinstance(feature, StockAp17UpgradeResearchGate):
        value["requirements"] = [
            asdict(requirement) for requirement in feature.requirements
        ]
    # Keep type first for human-facing package examples without affecting the
    # canonical encoder, whose JSON keys are sorted.
    return {"type": value.pop("type"), **value}


def encode_controller_features(features_to_encode: Iterable[ControllerFeature]) -> bytes:
    """Create deterministic manager-side JSON for fingerprints and tests.

    This canonical JSON is not the injected runtime format.  Runtime wiring
    must translate the validated records into the bounded binary MMCR registry.
    """

    features = normalize_controller_features(features_to_encode)
    root = {
        "format": CONTROLLER_FEATURE_FORMAT,
        "version": CONTROLLER_FEATURE_FORMAT_VERSION,
        "features": [controller_feature_mapping(item) for item in features],
    }
    payload = json.dumps(
        root, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(payload) > MAX_CANONICAL_FEATURE_BYTES:
        raise ControllerFeatureError(
            f"controller feature payload exceeds {MAX_CANONICAL_FEATURE_BYTES} bytes"
        )
    return payload


def decode_controller_features(payload: bytes) -> Tuple[ControllerFeature, ...]:
    """Decode the deterministic manager-side representation fail-closed."""

    if not isinstance(payload, bytes):
        raise ControllerFeatureError("controller feature payload must be bytes")
    if len(payload) > MAX_CANONICAL_FEATURE_BYTES:
        raise ControllerFeatureError(
            f"controller feature payload exceeds {MAX_CANONICAL_FEATURE_BYTES} bytes"
        )
    try:
        root = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, _DuplicateKey) as exc:
        raise ControllerFeatureError("controller feature payload is invalid JSON") from exc
    if not isinstance(root, Mapping) or set(root) != {"format", "version", "features"}:
        raise ControllerFeatureError("controller feature payload root is invalid")
    if root["format"] != CONTROLLER_FEATURE_FORMAT:
        raise ControllerFeatureError("controller feature payload format is invalid")
    if root["version"] != CONTROLLER_FEATURE_FORMAT_VERSION:
        raise ControllerFeatureError(
            f"unsupported controller feature format version: {root['version']!r}"
        )
    raw_features = root["features"]
    if not isinstance(raw_features, list):
        raise ControllerFeatureError("controller feature payload features must be an array")
    if len(raw_features) > MAX_CONTROLLER_FEATURES:
        raise ControllerFeatureError(
            f"controller feature count exceeds {MAX_CONTROLLER_FEATURES}"
        )
    features = normalize_controller_features(
        parse_controller_feature(item) for item in raw_features
    )
    if encode_controller_features(features) != payload:
        raise ControllerFeatureError(
            "controller feature payload is not in canonical deterministic form"
        )
    return features


def _validate_feature(feature: ControllerFeature) -> ControllerFeature:
    if not isinstance(feature, tuple(_FEATURE_TYPES.values())):
        raise ControllerFeatureError("unsupported controller feature object")
    if isinstance(feature, StockMx22BuildingOpenToggle):
        _logical(feature.toggle_key, "toggle_key")
        _logical(feature.parent_building, "parent_building")
        _distinct_controls(
            "MX22 building open toggle",
            feature.open_command_id,
            feature.close_command_id,
        )
        if feature.open_command_id in (0x22AB, 0x22AC) or feature.close_command_id in (0x22AB, 0x22AC):
            raise ControllerFeatureError(
                "MX22 building toggle commands must be package-private and cannot "
                "reuse stock Embassy commands 0x22AB/0x22AC"
            )
    else:
        _logical(feature.panel_key, "panel_key")
    if isinstance(feature, StockAp10Ap69SecondaryPanel):
        _logical(feature.parent_building, "parent_building")
        _fourcc(feature.source_dialog_id, "source_dialog_id")
        _family_id(feature.building_family_id, "building_family_id")
        _control(feature.open_command_id, "open_command_id")
    elif isinstance(feature, (StockMx09Ap41RewardPanel, StockMx04Mx05OccupantActionPanel,
                              StockAp08Mx05QuestBoardPanel)):
        _logical(feature.parent_building, "parent_building")
        _fourcc(feature.source_dialog_id, "source_dialog_id")
        _control(feature.open_command_id, "open_command_id")
        if isinstance(feature, StockMx04Mx05OccupantActionPanel):
            _gpl_symbol(feature.cost_callback_symbol)
            _gpl_symbol(feature.action_callback_symbol)
            if feature.cost_callback_symbol.casefold() == feature.action_callback_symbol.casefold():
                raise ControllerFeatureError("occupant cost and action callbacks must be distinct")
        elif isinstance(feature, StockAp08Mx05QuestBoardPanel):
            symbols = (
                feature.offer_count_callback_symbol,
                feature.revision_callback_symbol,
                feature.offer_reward_callback_symbol,
                feature.refresh_cost_callback_symbol,
                feature.refresh_callback_symbol,
            )
            for symbol in symbols:
                _gpl_symbol(symbol)
            if len({symbol.casefold() for symbol in symbols}) != len(symbols):
                raise ControllerFeatureError("quest-list callback symbols must be distinct")
            _bounded_cp1252(feature.offer_name_text, "offer_name_text")
            _bounded_cp1252(feature.offer_goal_text, "offer_goal_text")
    elif isinstance(feature, StockAp41Fl00HostileMonsterFlag):
        _logical(feature.action_key, "action_key")
        _fourcc(feature.private_mode, "private_mode")
        _fourcc(feature.private_flag_id, "private_flag_id")
        if feature.private_mode == "Fl00" or feature.private_flag_id == "ARA2":
            raise ControllerFeatureError(
                "private reward mode/flag IDs cannot claim stock Fl00/ARA2"
            )
        if feature.private_mode != feature.private_flag_id:
            raise ControllerFeatureError(
                "the traced Fl00 clone requires private_mode and private_flag_id "
                "to be the same Overlay Description FourCC"
            )
        if type(feature.cursor_ordinal) is not int or not 32 <= feature.cursor_ordinal <= 255:
            raise ControllerFeatureError(
                "cursor_ordinal must be a package-owned private selector in 32..255"
            )
        paired = (
            feature.availability_attribute_id is not None,
            feature.unavailable_alert_text is not None,
        )
        if paired[0] != paired[1]:
            raise ControllerFeatureError(
                "availability_attribute_id and unavailable_alert_text must both "
                "be null or both be present"
            )
        if feature.availability_attribute_id is not None:
            _attribute_id(feature.availability_attribute_id, "availability_attribute_id")
            _bounded_cp1252(
                feature.unavailable_alert_text, "unavailable_alert_text"
            )
    elif isinstance(feature, StockAp22ResourceMeter):
        _logical(feature.resource_key, "resource_key")
        _fourcc(feature.attribute_id, "attribute_id")
        _distinct_controls(
            "AP22 resource meter",
            feature.label_control_id,
            feature.count_control_id,
            feature.binding_control_id,
        )
    elif isinstance(feature, StockAp99ResearchRow):
        _logical(feature.recipe_key, "recipe_key")
        _control(feature.action_control_id, "action_control_id")
        if (
            _STOCK_AP99_CONTROL_ID_BEGIN
            <= feature.action_control_id
            < _STOCK_AP99_CONTROL_ID_END
        ):
            raise ControllerFeatureError(
                "AP99 action_control_id cannot use Majesty's reserved stock "
                "AP99 control range 0x1388..0x13EB"
            )
        _proven_stock_ap99_template(
            feature.descriptor_template_control_id,
            "descriptor_template_control_id",
        )
        _proven_stock_ap99_template(
            feature.completion_template_control_id,
            "completion_template_control_id",
        )
        _level(feature.required_level)
        _nonnegative_u32(feature.price, "price")
        _control(feature.price_control_id, "price_control_id")
        _control(feature.progress_control_id, "progress_control_id")
        _control(feature.active_display_control_id, "active_display_control_id")
        _optional_control(feature.icon_control_id, "icon_control_id")
        _bounded_cp1252(feature.completion_text, "completion_text")
        _distinct_controls(
            "AP99 research row",
            feature.action_control_id,
            feature.price_control_id,
            feature.progress_control_id,
            feature.active_display_control_id,
            feature.icon_control_id,
        )
    elif isinstance(feature, StockAp17UpgradeResearchGate):
        _logical(feature.parent_building, "parent_building")
        _distinct_controls(
            "AP17 upgrade gate",
            feature.upgrade_control_id,
            feature.upgrade_price_control_id,
        )
        if not feature.requirements or len(feature.requirements) > 3:
            raise ControllerFeatureError(
                "AP17 upgrade gate requires 1..3 level prerequisites"
            )
        levels = []
        recipes = set()
        for requirement in feature.requirements:
            if not isinstance(requirement, UpgradeRequirement):
                raise ControllerFeatureError("upgrade requirements are invalid")
            _level(requirement.building_level)
            _logical(requirement.recipe_key, "requirements.recipe_key")
            if requirement.recipe_key in recipes:
                raise ControllerFeatureError("upgrade requirements repeat a recipe_key")
            recipes.add(requirement.recipe_key)
            levels.append(requirement.building_level)
        if levels != sorted(set(levels)):
            raise ControllerFeatureError(
                "upgrade requirement levels must be strictly increasing"
            )
    elif isinstance(feature, StockAp24TimedRageAction):
        _logical(feature.action_key, "action_key")
        _logical(feature.resource_key, "resource_key")
        _control(feature.descriptor_template_control_id, "descriptor_template_control_id")
        _control(feature.level_price_template_control_id, "level_price_template_control_id")
        _level(feature.required_level)
        _nonnegative_u32(feature.gold_cost, "gold_cost")
        template_metadata = _PROVEN_AP24_TIMED_TEMPLATE_METADATA.get(
            (
                feature.descriptor_template_control_id,
                feature.level_price_template_control_id,
            )
        )
        if template_metadata is None:
            raise ControllerFeatureError(
                "AP24 timed action must use a proven stock descriptor/level-price "
                "template pair"
            )
        if template_metadata != (feature.required_level, feature.gold_cost):
            required_level, gold_cost = template_metadata
            raise ControllerFeatureError(
                "AP24 timed action stock template metadata requires "
                f"required_level {required_level} and gold_cost {gold_cost}"
            )
        _positive_u32(feature.resource_cost, "resource_cost")
        _gpl_symbol(feature.callback_symbol)
        if type(feature.duration_ms) is not int or not 1 <= feature.duration_ms <= 86_400_000:
            raise ControllerFeatureError("duration_ms must be in 1..86400000")
        _distinct_controls(
            "AP24 timed Rage action",
            feature.action_control_id,
            feature.icon_control_id,
            feature.price_control_id,
            feature.progress_control_id,
            feature.active_display_control_id,
        )
    elif isinstance(feature, StockAp24RageCommandAction):
        _logical(feature.action_key, "action_key")
        _logical(feature.resource_key, "resource_key")
        _control(feature.visual_template_control_id, "visual_template_control_id")
        _proven_stock_ap99_template(
            feature.completion_template_research_control_id,
            "completion_template_research_control_id",
        )
        _level(feature.required_level)
        template_level = _PROVEN_AP24_RAGE_VISUAL_TEMPLATE_LEVELS.get(
            feature.visual_template_control_id
        )
        if template_level is None:
            raise ControllerFeatureError(
                "AP24 Rage command visual_template_control_id is not a proven "
                "stock visual template"
            )
        if template_level != feature.required_level:
            raise ControllerFeatureError(
                "AP24 Rage command stock visual template requires "
                f"required_level {template_level}"
            )
        _positive_u32(feature.resource_cost, "resource_cost")
        _gpl_symbol(feature.callback_symbol)
        _distinct_controls(
            "AP24 Rage command action",
            feature.action_control_id,
            feature.icon_control_id,
            feature.price_control_id,
        )
    elif isinstance(feature, StockAp69SovereignTargetAction):
        _logical(feature.action_key, "action_key")
        _logical(feature.resource_key, "resource_key")
        _control(feature.visual_template_control_id, "visual_template_control_id")
        _control(feature.target_template_control_id, "target_template_control_id")
        if (
            feature.visual_template_control_id
            not in _PROVEN_AP69_SOVEREIGN_VISUAL_TEMPLATES
        ):
            raise ControllerFeatureError(
                "AP69 sovereign visual_template_control_id is not a proven "
                "stock visual template"
            )
        _fourcc(feature.stock_target_mode, "stock_target_mode")
        _fourcc(feature.stock_executor_mode, "stock_executor_mode")
        if feature.stock_executor_mode != "Sp14":
            raise ControllerFeatureError(
                "stock.ap69-sovereign-target-action.v1 currently supports only "
                "the traced Sp14 stock_executor_mode"
            )
        _fourcc(feature.private_mode, "private_mode")
        if feature.private_mode.startswith("Sp"):
            raise ControllerFeatureError(
                "private_mode cannot use Majesty's reserved Sp** stock "
                "sovereign-mode namespace"
            )
        _fourcc(feature.private_unit_id, "private_unit_id")
        if feature.private_mode in {
            feature.stock_target_mode,
            feature.stock_executor_mode,
        }:
            raise ControllerFeatureError(
                "private_mode must differ from stock_target_mode and "
                "stock_executor_mode"
            )
        if type(feature.cursor_ordinal) is not int or not 0 <= feature.cursor_ordinal <= 255:
            raise ControllerFeatureError("cursor_ordinal must be in 0..255")
        _level(feature.required_level)
        target_metadata = _PROVEN_AP69_SOVEREIGN_TARGET_TEMPLATE_METADATA.get(
            feature.target_template_control_id
        )
        if target_metadata is None:
            raise ControllerFeatureError(
                "AP69 sovereign target_template_control_id is not a proven "
                "stock target template"
            )
        if target_metadata != (feature.stock_target_mode, feature.required_level):
            stock_target_mode, required_level = target_metadata
            raise ControllerFeatureError(
                "AP69 sovereign stock target template requires "
                f"stock_target_mode {stock_target_mode!r} and "
                f"required_level {required_level}"
            )
        _positive_u32(feature.resource_cost, "resource_cost")
        _distinct_controls(
            "AP69 sovereign target action",
            feature.visual_control_id,
            feature.private_control_id,
            feature.icon_control_id,
            feature.price_control_id,
        )
    return feature


def _validate_composition(features: Sequence[ControllerFeature]) -> None:
    panel_types = (StockAp10Ap69SecondaryPanel, StockMx09Ap41RewardPanel,
                   StockMx04Mx05OccupantActionPanel, StockAp08Mx05QuestBoardPanel)
    panels = {
        item.panel_key: item
        for item in features
        if isinstance(item, panel_types)
    }
    if len(panels) > MAX_SECONDARY_PANELS:
        raise ControllerFeatureError(
            f"secondary panel count exceeds {MAX_SECONDARY_PANELS}"
        )
    panel_records = [
        item for item in features if isinstance(item, panel_types)
    ]
    if len(panels) != len(panel_records):
        raise ControllerFeatureError("duplicate secondary panel_key")
    _unique_field(panel_records, "source_dialog_id", "source dialog ID")
    parent_commands = set()
    for panel in panel_records:
        key = (panel.parent_building, panel.open_command_id)
        if key in parent_commands:
            raise ControllerFeatureError(
                "two secondary panels claim the same parent command"
            )
        parent_commands.add(key)
    for index, first in enumerate(panel_records):
        for second in panel_records[index + 1:]:
            if isinstance(first, StockAp10Ap69SecondaryPanel) and isinstance(second, StockAp10Ap69SecondaryPanel) and (
                first.building_family_id.startswith(second.building_family_id)
                or second.building_family_id.startswith(first.building_family_id)
            ):
                raise ControllerFeatureError(
                    "secondary-panel building family prefixes overlap"
                )

    toggles = [item for item in features if isinstance(item, StockMx22BuildingOpenToggle)]
    _unique_field(toggles, "toggle_key", "building toggle_key")
    _unique_field(toggles, "parent_building", "building toggle parent")
    toggle_commands = set()
    for toggle in toggles:
        for command in (toggle.open_command_id, toggle.close_command_id):
            if command in toggle_commands:
                raise ControllerFeatureError("building toggle command IDs collide")
            toggle_commands.add(command)

    for feature in features:
        if isinstance(feature, StockMx22BuildingOpenToggle):
            continue
        if not isinstance(feature, panel_types) and feature.panel_key not in panels:
            raise ControllerFeatureError(
                f"controller feature refers to unknown panel_key {feature.panel_key!r}"
            )
        if (not isinstance(feature, (*panel_types, StockAp41Fl00HostileMonsterFlag))
                and not isinstance(panels[feature.panel_key], StockAp10Ap69SecondaryPanel)):
            raise ControllerFeatureError("this controller recipe requires an AP10/AP69 panel")

    meters: dict[tuple[str, str], StockAp22ResourceMeter] = {}
    meter_attributes: dict[str, StockAp22ResourceMeter] = {}
    research: dict[tuple[str, str], StockAp99ResearchRow] = {}
    actions = set()
    # GPL identifiers are case-insensitive in Majesty.  Retain the author's
    # exact spelling in the emitted record, but reserve callback identities by
    # their case-folded spelling so two packages cannot register aliases for
    # the same function.
    callbacks = set()
    global_private_commands = {}
    private_modes = set()
    stock_sovereign_modes = set()
    private_units = set()
    upgrade_gates = set()
    reward_actions = set()
    reward_action_panels = set()
    private_flag_ids = set()
    private_cursor_ordinals = set()
    controls: dict[str, dict[int, str]] = {key: {} for key in panels}

    for feature in features:
        if isinstance(feature, StockMx22BuildingOpenToggle):
            continue
        if isinstance(feature, (StockMx04Mx05OccupantActionPanel, StockAp08Mx05QuestBoardPanel)):
            symbols = (
                (feature.cost_callback_symbol, feature.action_callback_symbol)
                if isinstance(feature, StockMx04Mx05OccupantActionPanel)
                else (
                    feature.offer_count_callback_symbol,
                    feature.revision_callback_symbol,
                    feature.offer_reward_callback_symbol,
                    feature.refresh_cost_callback_symbol,
                    feature.refresh_callback_symbol,
                )
            )
            for symbol in symbols:
                if symbol.casefold() in callbacks:
                    raise ControllerFeatureError("duplicate private GPL callback symbol")
                callbacks.add(symbol.casefold())
        if isinstance(feature, StockAp22ResourceMeter):
            key = (feature.panel_key, feature.resource_key)
            if key in meters:
                raise ControllerFeatureError("duplicate resource meter identity")
            if feature.attribute_id in meter_attributes:
                raise ControllerFeatureError(
                    "duplicate AP22 resource-meter attribute_id "
                    f"{feature.attribute_id!r}"
                )
            meters[key] = feature
            meter_attributes[feature.attribute_id] = feature
            _claim_controls(controls, feature.panel_key, feature.type,
                            feature.label_control_id, feature.count_control_id,
                            feature.binding_control_id)
        elif isinstance(feature, StockAp99ResearchRow):
            key = (feature.panel_key, feature.recipe_key)
            if key in research:
                raise ControllerFeatureError("duplicate AP99 research recipe identity")
            research[key] = feature
            previous = global_private_commands.get(feature.action_control_id)
            if previous is not None:
                raise ControllerFeatureError(
                    "AP99's stock descriptor registry cannot contain duplicate "
                    f"private command 0x{feature.action_control_id:08X}"
                )
            global_private_commands[feature.action_control_id] = feature.type
            _claim_controls(controls, feature.panel_key, feature.type,
                            feature.action_control_id, feature.price_control_id,
                            feature.progress_control_id, feature.active_display_control_id,
                            feature.icon_control_id)
        elif isinstance(feature, StockAp17UpgradeResearchGate):
            if feature.panel_key in upgrade_gates:
                raise ControllerFeatureError(
                    "a secondary panel has more than one AP17 upgrade gate"
                )
            upgrade_gates.add(feature.panel_key)
            panel = panels[feature.panel_key]
            if panel.parent_building != feature.parent_building:
                raise ControllerFeatureError(
                    "upgrade gate parent_building does not match its secondary panel"
                )
            for requirement in feature.requirements:
                if (feature.panel_key, requirement.recipe_key) not in research:
                    raise ControllerFeatureError(
                        "upgrade gate refers to an unknown AP99 recipe_key"
                    )
        elif isinstance(feature, StockAp41Fl00HostileMonsterFlag):
            if not isinstance(panels[feature.panel_key], StockMx09Ap41RewardPanel):
                raise ControllerFeatureError(
                    "AP41/Fl00 hostile-monster action requires an MX09/AP41 reward panel"
                )
            identity = (feature.panel_key, feature.action_key)
            if identity in reward_actions:
                raise ControllerFeatureError("duplicate AP41 reward action identity")
            reward_actions.add(identity)
            if feature.panel_key in reward_action_panels:
                raise ControllerFeatureError(
                    "an AP41 reward panel can declare exactly one hostile-monster action"
                )
            reward_action_panels.add(feature.panel_key)
            if feature.private_mode in private_modes:
                raise ControllerFeatureError("duplicate private placement mode")
            if feature.private_flag_id in private_flag_ids:
                raise ControllerFeatureError("duplicate private reward flag ID")
            if feature.cursor_ordinal in private_cursor_ordinals:
                raise ControllerFeatureError("duplicate private cursor ordinal")
            private_modes.add(feature.private_mode)
            private_flag_ids.add(feature.private_flag_id)
            private_cursor_ordinals.add(feature.cursor_ordinal)
        elif isinstance(feature, (
            StockAp24TimedRageAction,
            StockAp24RageCommandAction,
            StockAp69SovereignTargetAction,
        )):
            identity = (feature.panel_key, feature.action_key)
            if identity in actions:
                raise ControllerFeatureError("duplicate controller action identity")
            actions.add(identity)
            if (feature.panel_key, feature.resource_key) not in meters:
                raise ControllerFeatureError(
                    "controller action refers to an unknown resource_key"
                )
            if isinstance(feature, StockAp24TimedRageAction):
                previous = global_private_commands.get(feature.action_control_id)
                if previous is not None:
                    raise ControllerFeatureError(
                        "private command ID conflicts with another global "
                        "descriptor registration"
                    )
                global_private_commands[feature.action_control_id] = feature.type
                visible = (
                    feature.action_control_id, feature.icon_control_id,
                    feature.price_control_id, feature.progress_control_id,
                    feature.active_display_control_id,
                )
            elif isinstance(feature, StockAp24RageCommandAction):
                visible = (
                    feature.action_control_id, feature.icon_control_id,
                    feature.price_control_id,
                )
            else:
                previous = global_private_commands.get(feature.private_control_id)
                if previous is not None:
                    raise ControllerFeatureError(
                        "private command ID conflicts with another global "
                        "descriptor registration"
                    )
                global_private_commands[feature.private_control_id] = feature.type
                visible = (
                    feature.visual_control_id, feature.private_control_id,
                    feature.icon_control_id, feature.price_control_id,
                )
                if feature.private_mode in private_modes:
                    raise ControllerFeatureError("duplicate private sovereign mode")
                if feature.private_unit_id in private_units:
                    raise ControllerFeatureError("duplicate private sovereign unit ID")
                private_modes.add(feature.private_mode)
                private_units.add(feature.private_unit_id)
                stock_sovereign_modes.update(
                    (feature.stock_target_mode, feature.stock_executor_mode)
                )
            _claim_controls(controls, feature.panel_key, feature.type, *visible)
            if isinstance(feature, (StockAp24TimedRageAction, StockAp24RageCommandAction)):
                callback_identity = feature.callback_symbol.casefold()
                if callback_identity in callbacks:
                    raise ControllerFeatureError("duplicate private GPL callback symbol")
                callbacks.add(callback_identity)

    overlap = private_modes & stock_sovereign_modes
    if overlap:
        raise ControllerFeatureError(
            "private sovereign mode(s) collide with stock target/executor "
            f"mode(s): {', '.join(sorted(overlap))}"
        )
    if private_flag_ids & private_units:
        raise ControllerFeatureError(
            "private reward flag IDs collide with private sovereign unit IDs"
        )
    reward_panels = {
        item.panel_key for item in panel_records
        if isinstance(item, StockMx09Ap41RewardPanel)
    }
    if reward_action_panels != reward_panels:
        raise ControllerFeatureError(
            "every MX09/AP41 reward panel requires exactly one linked "
            "AP41/Fl00 hostile-monster action"
        )


def _feature_sort_key(feature: ControllerFeature) -> tuple:
    identity = ""
    for field_name in ("resource_key", "recipe_key", "action_key", "parent_building"):
        if hasattr(feature, field_name):
            identity = str(getattr(feature, field_name))
            break
    logical_key = (
        feature.toggle_key
        if isinstance(feature, StockMx22BuildingOpenToggle)
        else feature.panel_key
    )
    return (_FEATURE_ORDER[feature.type], logical_key, identity,
            _canonical_record_bytes(feature))


def _canonical_record_bytes(feature: ControllerFeature) -> bytes:
    return json.dumps(
        controller_feature_mapping_unchecked(feature),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def controller_feature_mapping_unchecked(feature: ControllerFeature) -> dict:
    value = asdict(feature)
    if isinstance(feature, StockAp17UpgradeResearchGate):
        value["requirements"] = [asdict(item) for item in feature.requirements]
    return value


def _logical(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _LOGICAL_KEY.fullmatch(value) is None:
        raise ControllerFeatureError(
            f"{field_name} must be a 1..64 byte logical identifier"
        )
    return value


def _gpl_symbol(value: object) -> str:
    if not isinstance(value, str) or _GPL_SYMBOL.fullmatch(value) is None:
        raise ControllerFeatureError(
            "callback_symbol must be a bounded GPL identifier, not code or a path"
        )
    if len(value.encode("ascii")) > MAX_CALLBACK_SYMBOL_BYTES:
        raise ControllerFeatureError("callback_symbol is too long")
    return value


def _fourcc(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ControllerFeatureError(f"{field_name} must be a FourCC string")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ControllerFeatureError(f"{field_name} must be an ASCII FourCC") from exc
    if len(encoded) != 4 or any(byte < 0x21 or byte > 0x7E for byte in encoded):
        raise ControllerFeatureError(
            f"{field_name} must contain exactly four printable ASCII bytes"
        )
    return value


def _family_id(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ControllerFeatureError(f"{field_name} must be an ASCII resource family")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ControllerFeatureError(f"{field_name} must be ASCII") from exc
    if not 1 <= len(encoded) <= 3 or any(byte < 0x21 or byte > 0x7E for byte in encoded):
        raise ControllerFeatureError(
            f"{field_name} must contain 1..3 printable ASCII bytes"
        )
    return value


def _attribute_id(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ControllerFeatureError(f"{field_name} must be an ASCII attribute ID")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ControllerFeatureError(f"{field_name} must be ASCII") from exc
    if not 1 <= len(encoded) <= 4 or any(byte < 0x21 or byte > 0x7E for byte in encoded):
        raise ControllerFeatureError(
            f"{field_name} must contain 1..4 printable ASCII bytes"
        )
    return value


def _bounded_cp1252(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ControllerFeatureError(f"{field_name} must be non-empty text")
    if "\x00" in value:
        raise ControllerFeatureError(f"{field_name} cannot contain NUL")
    try:
        encoded = value.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ControllerFeatureError(
            f"{field_name} must be Windows-1252 text"
        ) from exc
    if len(encoded) > MAX_FEATURE_TEXT_BYTES:
        raise ControllerFeatureError(
            f"{field_name} exceeds {MAX_FEATURE_TEXT_BYTES} Windows-1252 bytes"
        )
    return value


def _level(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 3:
        raise ControllerFeatureError("required building level must be in 1..3")
    return value


def _nonnegative_u32(value: object, field_name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0x7FFFFFFF:
        raise ControllerFeatureError(f"{field_name} must be in 0..2147483647")
    return value


def _positive_u32(value: object, field_name: str) -> int:
    if type(value) is not int or not 1 <= value <= 0x7FFFFFFF:
        raise ControllerFeatureError(f"{field_name} must be in 1..2147483647")
    return value


def _control(value: object, field_name: str) -> int:
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise ControllerFeatureError(f"{field_name} must be a nonzero uint32")
    return value


def _proven_stock_ap99_template(value: object, field_name: str) -> int:
    control_id = _control(value, field_name)
    if control_id not in _PROVEN_STOCK_AP99_DESCRIPTOR_CONTROL_IDS:
        raise ControllerFeatureError(
            f"{field_name} must identify one of Majesty's 26 proven stock "
            "AP99 research descriptors"
        )
    return control_id


def _optional_control(value: object, field_name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ControllerFeatureError(f"{field_name} must be a uint32")
    return value


def _distinct_controls(context: str, *values: int) -> None:
    for value in values:
        _optional_control(value, "control_id")
    nonzero = [value for value in values if value != 0]
    if len(nonzero) != len(set(nonzero)):
        raise ControllerFeatureError(f"{context} contains duplicate control IDs")


def _claim_controls(
    controls: dict[str, dict[int, str]],
    panel_key: str,
    owner: str,
    *values: int,
) -> None:
    claimed = controls[panel_key]
    for value in values:
        if value == 0:
            continue
        previous = claimed.get(value)
        if previous is not None:
            raise ControllerFeatureError(
                f"panel {panel_key!r} control 0x{value:08X} is claimed by "
                f"both {previous} and {owner}"
            )
        claimed[value] = owner


def _unique_field(items: Sequence[object], field_name: str, label: str) -> None:
    seen = set()
    for item in items:
        value = getattr(item, field_name)
        if value in seen:
            raise ControllerFeatureError(f"duplicate {label}: {value!r}")
        seen.add(value)


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: Sequence[Tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


__all__ = [
    "CONTROLLER_FEATURE_FORMAT",
    "CONTROLLER_FEATURE_FORMAT_VERSION",
    "ControllerFeature",
    "ControllerFeatureError",
    "LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY",
    "MAX_CONTROLLER_FEATURES",
    "StockAp10Ap69SecondaryPanel",
    "StockAp08Mx05QuestBoardPanel",
    "StockAp17UpgradeResearchGate",
    "StockAp22ResourceMeter",
    "StockAp24RageCommandAction",
    "StockAp24TimedRageAction",
    "StockAp69SovereignTargetAction",
    "StockAp99ResearchRow",
    "StockMx22BuildingOpenToggle",
    "StockMx04Mx05OccupantActionPanel",
    "StockMx09Ap41RewardPanel",
    "UpgradeRequirement",
    "controller_feature_mapping",
    "decode_controller_features",
    "encode_controller_features",
    "legacy_alchemist_controller_features",
    "legacy_controller_features",
    "normalize_controller_features",
    "parse_controller_feature",
]
