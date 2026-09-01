"""Deterministic runtime registry for bounded stock-controller recipes.

``MMCR`` is a manager-owned binary format.  It contains only recipes already
validated by :mod:`majesty_cam.stock_controller_features`; it cannot carry
paths, DLL names, RVAs, machine code, or arbitrary instructions.  The native
runtime parser mirrors these limits before any record is eligible for lookup.

The nine record sections below represent reusable stock lifecycle recipes.
Runtime integration must continue to use the proven single active AP10/AP69
panel, single AP99 owner, single pending Rage command, and single
sovereign-target session.  Multiple registry records are alternatives selected
into those stock-shaped singleton lifecycles, not permission to run parallel
replacement controllers.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import struct
import tempfile
from typing import Iterable, Mapping, Optional, Tuple, Type

from .stock_controller_features import (
    MAX_CONTROLLER_FEATURES,
    MAX_FEATURE_TEXT_BYTES,
    MAX_SECONDARY_PANELS,
    ControllerFeature,
    ControllerFeatureError,
    StockAp10Ap69SecondaryPanel,
    StockAp41Fl00HostileMonsterFlag,
    StockMx09Ap41RewardPanel,
    StockAp17UpgradeResearchGate,
    StockAp22ResourceMeter,
    StockAp24RageCommandAction,
    StockAp24TimedRageAction,
    StockAp69SovereignTargetAction,
    StockAp99ResearchRow,
    UpgradeRequirement,
    normalize_controller_features,
)


CONTROLLER_REGISTRY_MAGIC = b"MMCR"
CONTROLLER_REGISTRY_VERSION = 2
STOCK_CONTROLLER_RUNTIME_CAPABILITY = "stock.controller-recipes.v1"
CONTROLLER_REGISTRY_ENVIRONMENT = "MAJESTY_MOD_MANAGER_CONTROLLERS"
CONTROLLER_REGISTRY_RELATIVE_PATH = Path(
    "DataMX/majesty_mod_manager_controllers.bin"
)
MAX_CONTROLLER_REGISTRY_BYTES = 512 * 1024

_HEADER = struct.Struct("<4s10I")
_U32 = struct.Struct("<I")
_SECTIONS: Tuple[Type[ControllerFeature], ...] = (
    StockAp10Ap69SecondaryPanel,
    StockAp22ResourceMeter,
    StockAp99ResearchRow,
    StockAp17UpgradeResearchGate,
    StockAp24TimedRageAction,
    StockAp24RageCommandAction,
    StockAp69SovereignTargetAction,
    StockMx09Ap41RewardPanel,
    StockAp41Fl00HostileMonsterFlag,
)


class ControllerRegistryError(ControllerFeatureError):
    """Raised when an MMCR registry is malformed or non-canonical."""


@dataclass(frozen=True)
class ResolvedSecondaryPanelRecord:
    """Runtime panel identity after the manager resolves v3 dialog remapping."""

    panel_key: str
    parent_dialog_id: int
    child_dialog_id: int
    building_family_id: str
    open_command_id: int


@dataclass(frozen=True)
class ResolvedRewardPanelRecord:
    panel_key: str
    parent_dialog_id: int
    child_dialog_id: int
    open_command_id: int


@dataclass(frozen=True)
class ResolvedHostileMonsterFlagRecord:
    panel_key: str
    action_key: str
    private_mode: str
    private_flag_id: str
    flag_prototype_name: str
    cursor_ordinal: int
    availability_attribute_id: Optional[str]
    unavailable_alert_text: Optional[str]


@dataclass(frozen=True)
class ResolvedUpgradeGateRecord:
    """An AP17 gate whose parent is reached through its resolved panel."""

    panel_key: str
    upgrade_control_id: int
    upgrade_price_control_id: int
    requirements: Tuple[UpgradeRequirement, ...]


@dataclass(frozen=True)
class ResolvedControllerRegistry:
    """Manager-resolved records safe for native runtime serialization."""

    panels: Tuple[ResolvedSecondaryPanelRecord, ...]
    meters: Tuple[StockAp22ResourceMeter, ...]
    research_rows: Tuple[StockAp99ResearchRow, ...]
    upgrade_gates: Tuple[ResolvedUpgradeGateRecord, ...]
    timed_rage_actions: Tuple[StockAp24TimedRageAction, ...]
    rage_command_actions: Tuple[StockAp24RageCommandAction, ...]
    sovereign_target_actions: Tuple[StockAp69SovereignTargetAction, ...]
    reward_panels: Tuple[ResolvedRewardPanelRecord, ...] = ()
    hostile_monster_flags: Tuple[ResolvedHostileMonsterFlagRecord, ...] = ()


def resolve_stock_controller_registry(
    features_to_resolve: Iterable[ControllerFeature],
    panel_dialog_ids: Mapping[str, Tuple[int, int]],
    *,
    flag_prototypes: Mapping[str, str] | None = None,
) -> ResolvedControllerRegistry:
    """Resolve author records to explicit parent/child dialog IDs.

    ``panel_dialog_ids`` is keyed by the already owner-qualified ``panel_key``;
    each value is ``(parent_dialog_id, child_dialog_id)`` after all manager v3
    remapping.  Package-local ``parent_building`` and ``source_dialog_id`` are
    intentionally absent from the resulting runtime model.
    """

    try:
        features = normalize_controller_features(features_to_resolve)
    except ControllerFeatureError as exc:
        raise ControllerRegistryError(str(exc)) from exc
    panel_features = tuple(item for item in features if isinstance(
        item, (StockAp10Ap69SecondaryPanel, StockMx09Ap41RewardPanel)
    ))
    expected = {item.panel_key for item in panel_features}
    if set(panel_dialog_ids) != expected:
        raise ControllerRegistryError(
            "resolved panel dialog mapping must contain exactly every panel_key"
        )
    panels = []
    reward_panels = []
    for item in panel_features:
        value = panel_dialog_ids[item.panel_key]
        if not isinstance(value, tuple) or len(value) != 2:
            raise ControllerRegistryError(
                "resolved panel dialog mapping values must be (parent, child) pairs"
            )
        parent, child = value
        _resolved_dialog_id(parent, "parent_dialog_id")
        _resolved_dialog_id(child, "child_dialog_id")
        if isinstance(item, StockAp10Ap69SecondaryPanel):
            panels.append(ResolvedSecondaryPanelRecord(
                item.panel_key, parent, child, item.building_family_id,
                item.open_command_id,
            ))
        else:
            reward_panels.append(ResolvedRewardPanelRecord(
                item.panel_key, parent, child, item.open_command_id,
            ))
    prototypes = {} if flag_prototypes is None else dict(flag_prototypes)
    flag_features = tuple(
        item for item in features if isinstance(item, StockAp41Fl00HostileMonsterFlag)
    )
    if set(prototypes) != {item.action_key for item in flag_features}:
        if flag_features:
            raise ControllerRegistryError(
                "resolved flag prototype mapping must contain exactly every action_key"
            )
    flags = tuple(
        ResolvedHostileMonsterFlagRecord(
            item.panel_key, item.action_key, item.private_mode,
            item.private_flag_id, prototypes[item.action_key], item.cursor_ordinal,
            item.availability_attribute_id, item.unavailable_alert_text,
        )
        for item in flag_features
    )
    gates = tuple(
        ResolvedUpgradeGateRecord(
            item.panel_key, item.upgrade_control_id,
            item.upgrade_price_control_id, item.requirements,
        )
        for item in features
        if isinstance(item, StockAp17UpgradeResearchGate)
    )
    return _validate_resolved_registry(ResolvedControllerRegistry(
        panels=tuple(panels),
        meters=tuple(item for item in features if isinstance(item, StockAp22ResourceMeter)),
        research_rows=tuple(item for item in features if isinstance(item, StockAp99ResearchRow)),
        upgrade_gates=gates,
        timed_rage_actions=tuple(
            item for item in features if isinstance(item, StockAp24TimedRageAction)
        ),
        rage_command_actions=tuple(
            item for item in features if isinstance(item, StockAp24RageCommandAction)
        ),
        sovereign_target_actions=tuple(
            item for item in features if isinstance(item, StockAp69SovereignTargetAction)
        ),
        reward_panels=tuple(reward_panels),
        hostile_monster_flags=flags,
    ))


class _Writer:
    def __init__(self) -> None:
        self.data = bytearray()

    def u32(self, value: int) -> None:
        self.data += _U32.pack(value)

    def logical(self, value: str) -> None:
        self._bytes(value.encode("ascii"))

    def symbol(self, value: str) -> None:
        self._bytes(value.encode("ascii"))

    def text(self, value: str) -> None:
        self._bytes(value.encode("cp1252"))

    def fourcc(self, value: str) -> None:
        self.data += value.encode("ascii")

    def family(self, value: str) -> None:
        encoded = value.encode("ascii")
        self.data += encoded + b"\x00" * (4 - len(encoded))

    def _bytes(self, value: bytes) -> None:
        self.u32(len(value))
        self.data += value


class _Reader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.cursor = _HEADER.size

    def u32(self, field: str) -> int:
        if len(self.payload) - self.cursor < _U32.size:
            raise ControllerRegistryError(f"MMCR {field} is truncated")
        value = _U32.unpack_from(self.payload, self.cursor)[0]
        self.cursor += _U32.size
        return value

    def logical(self, field: str) -> str:
        return self._string(field, 64, "ascii")

    def symbol(self, field: str) -> str:
        return self._string(field, 64, "ascii")

    def text(self, field: str) -> str:
        return self._string(field, MAX_FEATURE_TEXT_BYTES, "cp1252")

    def fourcc(self, field: str) -> str:
        return self._fixed(field, 4).decode("ascii", "strict")

    def family(self, field: str) -> str:
        raw = self._fixed(field, 4)
        end = raw.find(b"\x00")
        if end < 0:
            end = len(raw)
        if any(raw[end:]):
            raise ControllerRegistryError(f"MMCR {field} has noncanonical padding")
        return raw[:end].decode("ascii", "strict")

    def _fixed(self, field: str, size: int) -> bytes:
        if len(self.payload) - self.cursor < size:
            raise ControllerRegistryError(f"MMCR {field} is truncated")
        value = self.payload[self.cursor:self.cursor + size]
        self.cursor += size
        return value

    def _string(self, field: str, maximum: int, encoding: str) -> str:
        length = self.u32(field + " length")
        if length == 0 or length > maximum:
            raise ControllerRegistryError(f"MMCR {field} length is outside bounds")
        raw = self._fixed(field, length)
        if b"\x00" in raw:
            raise ControllerRegistryError(f"MMCR {field} contains NUL")
        try:
            return raw.decode(encoding, "strict")
        except UnicodeError as exc:
            raise ControllerRegistryError(
                f"MMCR {field} has invalid {encoding} text"
            ) from exc


def encode_stock_controller_registry(registry: ResolvedControllerRegistry) -> bytes:
    """Encode canonical validated recipes into bounded MMCR v2 bytes."""

    try:
        registry = _validate_resolved_registry(registry)
    except ControllerRegistryError:
        raise
    except ControllerFeatureError as exc:
        raise ControllerRegistryError(str(exc)) from exc
    sections = (
        registry.panels,
        registry.meters,
        registry.research_rows,
        registry.upgrade_gates,
        registry.timed_rage_actions,
        registry.rage_command_actions,
        registry.sovereign_target_actions,
        registry.reward_panels,
        registry.hostile_monster_flags,
    )
    counts = tuple(len(section) for section in sections)
    writer = _Writer()
    writer.data += _HEADER.pack(
        CONTROLLER_REGISTRY_MAGIC,
        CONTROLLER_REGISTRY_VERSION,
        *counts,
    )
    for section in sections:
        for record in section:
            _encode_feature(writer, record)
    payload = bytes(writer.data)
    if len(payload) > MAX_CONTROLLER_REGISTRY_BYTES:
        raise ControllerRegistryError(
            f"MMCR registry exceeds {MAX_CONTROLLER_REGISTRY_BYTES} bytes"
        )
    return payload


def decode_stock_controller_registry(payload: bytes) -> ResolvedControllerRegistry:
    """Decode MMCR v2, rejecting malformed and non-canonical registries."""

    if not isinstance(payload, bytes):
        raise ControllerRegistryError("MMCR registry must be bytes")
    if not _HEADER.size <= len(payload) <= MAX_CONTROLLER_REGISTRY_BYTES:
        raise ControllerRegistryError("MMCR registry size is outside bounds")
    magic, version, *counts = _HEADER.unpack_from(payload)
    if magic != CONTROLLER_REGISTRY_MAGIC:
        raise ControllerRegistryError("controller registry magic is not MMCR")
    if version != CONTROLLER_REGISTRY_VERSION:
        raise ControllerRegistryError(
            f"unsupported MMCR registry version: {version}"
        )
    if sum(counts) > MAX_CONTROLLER_FEATURES:
        raise ControllerRegistryError("MMCR record count is outside bounds")
    if counts[0] > MAX_SECONDARY_PANELS:
        raise ControllerRegistryError("MMCR panel count is outside bounds")

    reader = _Reader(payload)
    sections = []
    try:
        for kind, count in zip(_SECTIONS, counts):
            sections.append(tuple(_decode_feature(reader, kind) for _ in range(count)))
    except (UnicodeError, struct.error, ValueError) as exc:
        if isinstance(exc, ControllerRegistryError):
            raise
        raise ControllerRegistryError("MMCR registry contains invalid data") from exc
    if reader.cursor != len(payload):
        raise ControllerRegistryError("MMCR registry contains trailing bytes")
    try:
        registry = ResolvedControllerRegistry(*sections)
        registry = _validate_resolved_registry(registry)
    except ControllerFeatureError as exc:
        raise ControllerRegistryError(str(exc)) from exc
    if encode_stock_controller_registry(registry) != payload:
        raise ControllerRegistryError(
            "MMCR registry is not in canonical deterministic form"
        )
    return registry


def write_stock_controller_registry(
    path: Path, registry: ResolvedControllerRegistry
) -> ResolvedControllerRegistry:
    """Atomically write a canonical MMCR file and return resolved records."""

    registry = _validate_resolved_registry(registry)
    payload = encode_stock_controller_registry(registry)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=destination.name + ".", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return registry


def _encode_feature(writer: _Writer, feature: object) -> None:
    writer.logical(feature.panel_key)
    if isinstance(feature, ResolvedSecondaryPanelRecord):
        writer.u32(feature.parent_dialog_id)
        writer.u32(feature.child_dialog_id)
        writer.family(feature.building_family_id)
        writer.u32(feature.open_command_id)
    elif isinstance(feature, StockAp22ResourceMeter):
        writer.logical(feature.resource_key)
        writer.fourcc(feature.attribute_id)
        writer.u32(feature.label_control_id)
        writer.u32(feature.count_control_id)
        writer.u32(feature.binding_control_id)
    elif isinstance(feature, StockAp99ResearchRow):
        writer.logical(feature.recipe_key)
        for value in (
            feature.action_control_id,
            feature.descriptor_template_control_id,
            feature.completion_template_control_id,
            feature.required_level,
            feature.price,
            feature.price_control_id,
            feature.progress_control_id,
            feature.active_display_control_id,
            feature.icon_control_id,
        ):
            writer.u32(value)
        writer.text(feature.completion_text)
    elif isinstance(feature, ResolvedUpgradeGateRecord):
        writer.u32(feature.upgrade_control_id)
        writer.u32(feature.upgrade_price_control_id)
        writer.u32(len(feature.requirements))
        for requirement in feature.requirements:
            writer.u32(requirement.building_level)
            writer.logical(requirement.recipe_key)
    elif isinstance(feature, StockAp24TimedRageAction):
        writer.logical(feature.action_key)
        for value in (
            feature.action_control_id,
            feature.descriptor_template_control_id,
            feature.level_price_template_control_id,
            feature.required_level,
            feature.gold_cost,
        ):
            writer.u32(value)
        writer.logical(feature.resource_key)
        writer.u32(feature.resource_cost)
        writer.symbol(feature.callback_symbol)
        for value in (
            feature.duration_ms,
            feature.icon_control_id,
            feature.price_control_id,
            feature.progress_control_id,
            feature.active_display_control_id,
        ):
            writer.u32(value)
    elif isinstance(feature, StockAp24RageCommandAction):
        writer.logical(feature.action_key)
        writer.u32(feature.action_control_id)
        writer.u32(feature.visual_template_control_id)
        writer.u32(feature.completion_template_research_control_id)
        writer.u32(feature.required_level)
        writer.logical(feature.resource_key)
        writer.u32(feature.resource_cost)
        writer.symbol(feature.callback_symbol)
        writer.u32(feature.icon_control_id)
        writer.u32(feature.price_control_id)
    elif isinstance(feature, StockAp69SovereignTargetAction):
        writer.logical(feature.action_key)
        writer.u32(feature.visual_control_id)
        writer.u32(feature.private_control_id)
        writer.u32(feature.visual_template_control_id)
        writer.u32(feature.target_template_control_id)
        writer.fourcc(feature.stock_target_mode)
        writer.fourcc(feature.stock_executor_mode)
        writer.fourcc(feature.private_mode)
        writer.fourcc(feature.private_unit_id)
        writer.u32(feature.cursor_ordinal)
        writer.u32(feature.required_level)
        writer.logical(feature.resource_key)
        writer.u32(feature.resource_cost)
        writer.u32(feature.icon_control_id)
        writer.u32(feature.price_control_id)
    elif isinstance(feature, ResolvedRewardPanelRecord):
        writer.u32(feature.parent_dialog_id)
        writer.u32(feature.child_dialog_id)
        writer.u32(feature.open_command_id)
    elif isinstance(feature, ResolvedHostileMonsterFlagRecord):
        writer.logical(feature.action_key)
        writer.fourcc(feature.private_mode)
        writer.fourcc(feature.private_flag_id)
        writer.symbol(feature.flag_prototype_name)
        writer.u32(feature.cursor_ordinal)
        writer.u32(1 if feature.availability_attribute_id is not None else 0)
        if feature.availability_attribute_id is not None:
            writer.family(feature.availability_attribute_id)
            writer.text(feature.unavailable_alert_text)
    else:  # pragma: no cover - normalization rejects this first
        raise ControllerRegistryError("unsupported MMCR record type")


def _decode_feature(reader: _Reader, kind: Type[ControllerFeature]) -> object:
    panel = reader.logical("panel_key")
    if kind is StockAp10Ap69SecondaryPanel:
        return ResolvedSecondaryPanelRecord(
            panel, reader.u32("parent_dialog_id"), reader.u32("child_dialog_id"),
            reader.family("building_family_id"), reader.u32("open_command_id"),
        )
    if kind is StockAp22ResourceMeter:
        return StockAp22ResourceMeter(
            panel, reader.logical("resource_key"), reader.fourcc("attribute_id"),
            reader.u32("label_control_id"), reader.u32("count_control_id"),
            reader.u32("binding_control_id"),
        )
    if kind is StockAp99ResearchRow:
        recipe = reader.logical("recipe_key")
        values = [reader.u32("AP99 field") for _ in range(9)]
        return StockAp99ResearchRow(panel, recipe, *values, reader.text("completion_text"))
    if kind is StockAp17UpgradeResearchGate:
        upgrade = reader.u32("upgrade_control_id")
        price = reader.u32("upgrade_price_control_id")
        count = reader.u32("upgrade requirement count")
        if not 1 <= count <= 3:
            raise ControllerRegistryError("MMCR upgrade requirement count is outside bounds")
        requirements = tuple(
            UpgradeRequirement(
                reader.u32("upgrade building_level"),
                reader.logical("upgrade recipe_key"),
            )
            for _ in range(count)
        )
        return ResolvedUpgradeGateRecord(panel, upgrade, price, requirements)
    if kind is StockAp24TimedRageAction:
        action = reader.logical("action_key")
        leading = [reader.u32("timed Rage field") for _ in range(5)]
        resource = reader.logical("resource_key")
        resource_cost = reader.u32("resource_cost")
        callback = reader.symbol("callback_symbol")
        trailing = [reader.u32("timed Rage field") for _ in range(5)]
        return StockAp24TimedRageAction(
            panel, action, *leading, resource, resource_cost, callback, *trailing
        )
    if kind is StockAp24RageCommandAction:
        action = reader.logical("action_key")
        leading = [reader.u32("Rage command field") for _ in range(4)]
        resource = reader.logical("resource_key")
        resource_cost = reader.u32("resource_cost")
        callback = reader.symbol("callback_symbol")
        return StockAp24RageCommandAction(
            panel, action, *leading, resource, resource_cost, callback,
            reader.u32("icon_control_id"), reader.u32("price_control_id"),
        )
    if kind is StockAp69SovereignTargetAction:
        action = reader.logical("action_key")
        controls = [reader.u32("sovereign control field") for _ in range(4)]
        modes = [reader.fourcc("sovereign FourCC field") for _ in range(4)]
        cursor = reader.u32("cursor_ordinal")
        level = reader.u32("required_level")
        resource = reader.logical("resource_key")
        return StockAp69SovereignTargetAction(
            panel, action, *controls, *modes, cursor, level, resource,
            reader.u32("resource_cost"), reader.u32("icon_control_id"),
            reader.u32("price_control_id"),
        )
    if kind is StockMx09Ap41RewardPanel:
        return ResolvedRewardPanelRecord(
            panel, reader.u32("parent_dialog_id"), reader.u32("child_dialog_id"),
            reader.u32("open_command_id"),
        )
    if kind is StockAp41Fl00HostileMonsterFlag:
        action = reader.logical("action_key")
        mode = reader.fourcc("private_mode")
        flag = reader.fourcc("private_flag_id")
        prototype = reader.symbol("flag_prototype_name")
        cursor = reader.u32("cursor_ordinal")
        has_gate = reader.u32("has_availability_gate")
        if has_gate not in (0, 1):
            raise ControllerRegistryError("MMCR availability gate marker is invalid")
        attribute = reader.family("availability_attribute_id") if has_gate else None
        alert = reader.text("unavailable_alert_text") if has_gate else None
        return ResolvedHostileMonsterFlagRecord(
            panel, action, mode, flag, prototype, cursor, attribute, alert,
        )
    raise ControllerRegistryError("unsupported MMCR section")


def _validate_resolved_registry(
    registry: ResolvedControllerRegistry,
) -> ResolvedControllerRegistry:
    if not isinstance(registry, ResolvedControllerRegistry):
        raise ControllerRegistryError("MMCR encoder requires a resolved registry")
    sections = (
        registry.panels, registry.meters, registry.research_rows,
        registry.upgrade_gates, registry.timed_rage_actions,
        registry.rage_command_actions, registry.sovereign_target_actions,
        registry.reward_panels, registry.hostile_monster_flags,
    )
    if any(not isinstance(section, tuple) for section in sections):
        raise ControllerRegistryError("MMCR resolved registry sections must be tuples")
    if sum(len(section) for section in sections) > MAX_CONTROLLER_FEATURES:
        raise ControllerRegistryError("MMCR record count is outside bounds")
    if len(registry.panels) + len(registry.reward_panels) > MAX_SECONDARY_PANELS:
        raise ControllerRegistryError("MMCR panel count is outside bounds")

    panels = {}
    child_dialogs = set()
    families = set()
    parent_commands = set()
    author_features = []
    for item in registry.panels:
        if not isinstance(item, ResolvedSecondaryPanelRecord):
            raise ControllerRegistryError("MMCR panel record type is invalid")
        if item.panel_key in panels:
            raise ControllerRegistryError("MMCR panel_key is duplicated")
        _resolved_dialog_id(item.parent_dialog_id, "parent_dialog_id")
        _resolved_dialog_id(item.child_dialog_id, "child_dialog_id")
        if item.child_dialog_id in child_dialogs:
            raise ControllerRegistryError("MMCR child dialog ID is duplicated")
        if item.building_family_id in families:
            raise ControllerRegistryError("MMCR building family ID is duplicated")
        parent_command = (item.parent_dialog_id, item.open_command_id)
        if parent_command in parent_commands:
            raise ControllerRegistryError("MMCR parent dialog command is duplicated")
        child_dialogs.add(item.child_dialog_id)
        families.add(item.building_family_id)
        parent_commands.add(parent_command)
        panels[item.panel_key] = item
        author_features.append(StockAp10Ap69SecondaryPanel(
            panel_key=item.panel_key,
            parent_building=_resolved_parent_key(item.parent_dialog_id),
            source_dialog_id=_unpack_fourcc(item.child_dialog_id),
            building_family_id=item.building_family_id,
            open_command_id=item.open_command_id,
        ))
    for item in registry.upgrade_gates:
        if not isinstance(item, ResolvedUpgradeGateRecord):
            raise ControllerRegistryError("MMCR upgrade gate record type is invalid")
        panel = panels.get(item.panel_key)
        if panel is None:
            raise ControllerRegistryError("MMCR upgrade gate has unknown panel_key")
        author_features.append(StockAp17UpgradeResearchGate(
            panel_key=item.panel_key,
            parent_building=_resolved_parent_key(panel.parent_dialog_id),
            upgrade_control_id=item.upgrade_control_id,
            upgrade_price_control_id=item.upgrade_price_control_id,
            requirements=item.requirements,
        ))
    author_features.extend(registry.meters)
    author_features.extend(registry.research_rows)
    author_features.extend(registry.timed_rage_actions)
    author_features.extend(registry.rage_command_actions)
    author_features.extend(registry.sovereign_target_actions)
    reward_panel_by_key = {}
    for item in registry.reward_panels:
        if not isinstance(item, ResolvedRewardPanelRecord):
            raise ControllerRegistryError("MMCR reward panel record type is invalid")
        if item.panel_key in panels or item.panel_key in reward_panel_by_key:
            raise ControllerRegistryError("MMCR panel_key is duplicated")
        _resolved_dialog_id(item.parent_dialog_id, "parent_dialog_id")
        _resolved_dialog_id(item.child_dialog_id, "child_dialog_id")
        if item.child_dialog_id in child_dialogs:
            raise ControllerRegistryError("MMCR child dialog ID is duplicated")
        parent_command = (item.parent_dialog_id, item.open_command_id)
        if parent_command in parent_commands:
            raise ControllerRegistryError("MMCR parent dialog command is duplicated")
        child_dialogs.add(item.child_dialog_id)
        parent_commands.add(parent_command)
        reward_panel_by_key[item.panel_key] = item
        author_features.append(StockMx09Ap41RewardPanel(
            item.panel_key, _resolved_parent_key(item.parent_dialog_id),
            _unpack_fourcc(item.child_dialog_id), item.open_command_id,
        ))
    flag_by_action = {}
    for item in registry.hostile_monster_flags:
        if not isinstance(item, ResolvedHostileMonsterFlagRecord):
            raise ControllerRegistryError("MMCR hostile-monster flag record type is invalid")
        if item.panel_key not in reward_panel_by_key:
            raise ControllerRegistryError("MMCR hostile-monster flag has unknown panel_key")
        if item.action_key in flag_by_action:
            raise ControllerRegistryError("MMCR hostile-monster action_key is duplicated")
        _gpl_runtime_symbol(item.flag_prototype_name, "flag_prototype_name")
        flag_by_action[item.action_key] = item
        author_features.append(StockAp41Fl00HostileMonsterFlag(
            item.panel_key, item.action_key, item.private_mode,
            item.private_flag_id, item.cursor_ordinal,
            item.availability_attribute_id, item.unavailable_alert_text,
        ))
    normalized = normalize_controller_features(author_features)

    panel_by_key = {item.panel_key: item for item in registry.panels}
    gate_by_key = {item.panel_key: item for item in registry.upgrade_gates}
    return ResolvedControllerRegistry(
        panels=tuple(
            panel_by_key[item.panel_key] for item in normalized
            if isinstance(item, StockAp10Ap69SecondaryPanel)
        ),
        meters=tuple(item for item in normalized if isinstance(item, StockAp22ResourceMeter)),
        research_rows=tuple(item for item in normalized if isinstance(item, StockAp99ResearchRow)),
        upgrade_gates=tuple(
            gate_by_key[item.panel_key] for item in normalized
            if isinstance(item, StockAp17UpgradeResearchGate)
        ),
        timed_rage_actions=tuple(
            item for item in normalized if isinstance(item, StockAp24TimedRageAction)
        ),
        rage_command_actions=tuple(
            item for item in normalized if isinstance(item, StockAp24RageCommandAction)
        ),
        sovereign_target_actions=tuple(
            item for item in normalized if isinstance(item, StockAp69SovereignTargetAction)
        ),
        reward_panels=tuple(
            reward_panel_by_key[item.panel_key] for item in normalized
            if isinstance(item, StockMx09Ap41RewardPanel)
        ),
        hostile_monster_flags=tuple(
            flag_by_action[item.action_key] for item in normalized
            if isinstance(item, StockAp41Fl00HostileMonsterFlag)
        ),
    )


def _gpl_runtime_symbol(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ControllerRegistryError(f"{field} must be a bounded ASCII GPL prototype")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError as exc:
        raise ControllerRegistryError(
            f"{field} must be a bounded ASCII GPL prototype"
        ) from exc
    if len(encoded) > 64:
        raise ControllerRegistryError(f"{field} must be a bounded ASCII GPL prototype")
    if not (value[0].isalpha() or value[0] == "_") or any(
        not (character.isalnum() or character == "_") for character in value
    ):
        raise ControllerRegistryError(f"{field} must be a GPL prototype identifier")
    return value


def _resolved_dialog_id(value: object, field: str) -> int:
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise ControllerRegistryError(f"{field} must be a nonzero uint32")
    raw = struct.pack("<I", value)
    if any(byte < 0x21 or byte > 0x7E for byte in raw):
        raise ControllerRegistryError(f"{field} must be a printable FourCC")
    return value


def _resolved_parent_key(value: int) -> str:
    return f"p{value:08x}"


def _unpack_fourcc(value: int) -> str:
    return struct.pack("<I", value).decode("ascii")
