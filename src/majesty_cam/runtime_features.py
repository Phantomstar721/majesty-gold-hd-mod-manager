"""Validated manager-to-runtime feature registry.

Packages describe reusable, stock-derived features.  The manager is the only
component that turns those descriptions into the compact ``MMFR`` registry
consumed by the injected runtime.  The wire format deliberately contains data
only: no code, addresses, patch bytes, or package-owned paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import tempfile
from typing import Iterable, Sequence, Union
from .equipment import EquipmentRegistration, EQUIPMENT_FEATURE_TYPE, MAX_EQUIPMENT, validate_registration
from .kingdom_research import (KingdomResearchRegistration, KINGDOM_RESEARCH_TYPE,
    MAX_KINGDOM_RESEARCH, validate_registration as validate_kingdom_registration)
from .hero_info import HeroInfoRow, HERO_INFO_TYPE, HERO_INFO_KINDS, MAX_HERO_INFO_ROWS, hero_info_mapping


RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH = (
    "DataMX/majesty_mod_manager_features.bin"
)
RUNTIME_FEATURE_REGISTRY_ENV_VAR = "MAJESTY_MOD_MANAGER_FEATURES"
NAME_GENERATOR_RUNTIME_CAPABILITY = "stock.name-generator.v1"
ENCHANTMENT_ROW_RUNTIME_CAPABILITY = "stock.ap78-enchantment-row.v1"
MAP_QUERY_RUNTIME_CAPABILITY = "stock.map-fog-query.v1"
MOVEMENT_QUERY_RUNTIME_CAPABILITY = "stock.movement-query.v1"
NATIVE_TIMING_RUNTIME_CAPABILITY = "stock.native-timing.v1"

_MAGIC = b"MMFR"
_VERSION = 1
_HEADER = struct.Struct("<4sIII")
_NAME_GENERATOR = struct.Struct("<IIIII")
_ENCHANTMENT_HEADER = struct.Struct("<II")
_MAX_NAME_GENERATORS = 256
_MAX_ENCHANTMENT_ROWS = 1024
_MAX_DISPLAY_TEXT_BYTES = 512
_MAX_REGISTRY_BYTES = 1024 * 1024

_LEGACY_ALCHEMIST_NAMES = "alchemist.nm18-name-generator"
_LEGACY_PHANTOM_NAMES = "phantom.nm19-name-generator"
_LEGACY_ALCHEMIST_ROWS = "alchemist.ap78-private-oil-rows"
_STOCK_NAME_GENERATOR_IDS = frozenset(f"NM{index:02d}" for index in range(1, 18))
_STOCK_NAME_PART_IDS = frozenset(f"HN{index:02d}" for index in range(1, 69))


@dataclass(frozen=True)
class NameGeneratorFeature:
    """One stock name-generator construction recipe.

    ``generator_id`` is an ``NMxx`` FourCC and ``name_part_ids`` contains the
    four ordered ``HNxx`` resources passed to Majesty's stock constructor.
    """

    generator_id: str
    name_part_ids: tuple[str, str, str, str]


@dataclass(frozen=True)
class EnchantmentRowFeature:
    """One private overlay presented through the stock AP78 XR01 row."""

    overlay_id: str
    display_text: str


@dataclass(frozen=True)
class MapFogQueryFeature:
    """Read-only stock fog queries with explicitly bounded frontier work."""


@dataclass(frozen=True)
class MovementQueryFeature:
    """Read-only native locomotion rates for units and unit descriptions."""


@dataclass(frozen=True)
class NativeTimingFeature:
    """Stock clock/base periods, declared effects and learned-spell cooldowns."""

    spell_ids: tuple[str, ...] = ()
    effector_ids: tuple[str, ...] = ()


RuntimeFeature = Union[NameGeneratorFeature, EnchantmentRowFeature, MapFogQueryFeature,
                       MovementQueryFeature, NativeTimingFeature, EquipmentRegistration,
                       KingdomResearchRegistration, HeroInfoRow]


@dataclass(frozen=True)
class RuntimeFeatureRegistry:
    name_generators: tuple[NameGeneratorFeature, ...] = ()
    enchantment_rows: tuple[EnchantmentRowFeature, ...] = ()
    map_fog_query: bool = False
    movement_query: bool = False
    native_timing: NativeTimingFeature | None = None
    equipment: tuple[EquipmentRegistration, ...] = ()
    kingdom_research: tuple[KingdomResearchRegistration, ...] = ()
    hero_info_rows: tuple[HeroInfoRow, ...] = ()

    @property
    def features(self) -> tuple[RuntimeFeature, ...]:
        return (*self.name_generators, *self.enchantment_rows, *self.equipment, *self.kingdom_research, *self.hero_info_rows,
                *((MapFogQueryFeature(),) if self.map_fog_query else ()),
                *((MovementQueryFeature(),) if self.movement_query else ()),
                *((self.native_timing,) if self.native_timing is not None else ()))


def _fourcc_bytes(value: object, *, prefix: str | None = None) -> bytes:
    if not isinstance(value, str):
        raise ValueError("runtime feature FourCCs must be strings")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("runtime feature FourCCs must be ASCII") from exc
    if len(encoded) != 4 or any(byte < 0x21 or byte > 0x7E for byte in encoded):
        raise ValueError(
            "runtime feature FourCCs must contain exactly four printable ASCII bytes"
        )
    if prefix is not None and not value.startswith(prefix):
        raise ValueError(f"runtime feature FourCC must begin with {prefix!r}")
    return encoded


def _fourcc_u32(value: object, *, prefix: str | None = None) -> int:
    return int.from_bytes(_fourcc_bytes(value, prefix=prefix), "little")


def _u32_fourcc(value: int, *, prefix: str | None = None) -> str:
    raw = value.to_bytes(4, "little")
    try:
        decoded = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("runtime feature FourCC is not ASCII") from exc
    _fourcc_bytes(decoded, prefix=prefix)
    return decoded


def _display_text_bytes(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("enchantment-row display text must be a string")
    if "\x00" in value:
        raise ValueError("enchantment-row display text cannot contain NUL")
    try:
        encoded = value.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "enchantment-row display text must be representable in Windows-1252"
        ) from exc
    if not encoded or len(encoded) > _MAX_DISPLAY_TEXT_BYTES:
        raise ValueError(
            "enchantment-row display text must contain "
            f"1..{_MAX_DISPLAY_TEXT_BYTES} Windows-1252 bytes"
        )
    # Python's codec rejects the five undefined Windows-1252 characters on
    # encode.  Check bytes as well so decoder inputs follow the same contract.
    if any(byte in (0x81, 0x8D, 0x8F, 0x90, 0x9D) for byte in encoded):
        raise ValueError("enchantment-row display text is not valid Windows-1252")
    return encoded


def normalize_runtime_features(
    features: Iterable[RuntimeFeature] = (),
    *,
    legacy_capabilities: Iterable[str] = (),
) -> RuntimeFeatureRegistry:
    """Validate, merge, and deterministically order runtime feature records.

    Exact duplicate declarations collapse to one record.  Two declarations
    claiming the same generator or overlay with different data fail closed.
    Legacy v2 capability names are translated to the same generic records.
    """

    expanded = [*features, *legacy_runtime_features(legacy_capabilities)]
    names: dict[int, NameGeneratorFeature] = {}
    rows: dict[int, EnchantmentRowFeature] = {}
    map_fog_query = False
    movement_query = False
    timing = False
    timing_spells: set[int] = set()
    timing_effectors: set[int] = set()
    equipment: dict[int, EquipmentRegistration] = {}
    research: dict[str, KingdomResearchRegistration] = {}
    info = {}
    info_subjects = set()
    research_commands, research_attributes, research_families = set(), set(), set()
    for feature in expanded:
        if isinstance(feature, NameGeneratorFeature):
            generator_key = _fourcc_u32(feature.generator_id, prefix="NM")
            if feature.generator_id in _STOCK_NAME_GENERATOR_IDS:
                raise ValueError(
                    f"name-generator feature {feature.generator_id} collides with stock Majesty"
                )
            if len(feature.name_part_ids) != 4:
                raise ValueError(
                    "name-generator features require exactly four HN FourCCs"
                )
            canonical = NameGeneratorFeature(
                generator_id=feature.generator_id,
                name_part_ids=tuple(
                    _u32_fourcc(_fourcc_u32(part, prefix="HN"), prefix="HN")
                    for part in feature.name_part_ids
                ),  # type: ignore[arg-type]
            )
            if len(set(canonical.name_part_ids)) != 4:
                raise ValueError(
                    "name-generator features require four distinct HN FourCCs"
                )
            stock_parts = sorted(
                set(canonical.name_part_ids) & _STOCK_NAME_PART_IDS
            )
            if stock_parts:
                raise ValueError(
                    "name-generator features cannot own stock Majesty HN01-HN68 "
                    f"tables: {', '.join(stock_parts)}"
                )
            previous = names.get(generator_key)
            if previous is not None and previous != canonical:
                raise ValueError(
                    f"conflicting name-generator feature for {feature.generator_id}"
                )
            names[generator_key] = canonical
        elif isinstance(feature, EnchantmentRowFeature):
            overlay_key = _fourcc_u32(feature.overlay_id)
            encoded_text = _display_text_bytes(feature.display_text)
            canonical = EnchantmentRowFeature(
                overlay_id=feature.overlay_id,
                display_text=encoded_text.decode("cp1252"),
            )
            previous = rows.get(overlay_key)
            if previous is not None and previous != canonical:
                raise ValueError(
                    f"conflicting enchantment-row feature for {feature.overlay_id}"
                )
            rows[overlay_key] = canonical
        elif isinstance(feature, HeroInfoRow):
            hero_info_mapping(feature)
            key = feature.sort_key
            if key in info:
                if info[key] != feature:
                    raise ValueError("conflicting hero information row")
                continue
            subject = (feature.kind, feature.subject_id)
            if feature.kind != "passive" and subject in info_subjects:
                raise ValueError("duplicate hero information subject")
            info_subjects.add(subject)
            info[key] = feature
        elif isinstance(feature, KingdomResearchRegistration):
            validate_kingdom_registration(feature)
            if (feature.identity in research or feature.action_control_id in research_commands
                    or feature.completion_attribute in research_attributes
                    or feature.building_family in research_families):
                raise ValueError("duplicate or colliding kingdom research identity, command or attribute")
            research[feature.identity] = feature
            research_commands.add(feature.action_control_id)
            research_attributes.add(feature.completion_attribute)
            research_families.add(feature.building_family)
        elif isinstance(feature, EquipmentRegistration):
            validate_registration(feature)
            if feature.equipment_id in equipment:
                raise ValueError("duplicate or colliding equipment identity")
            equipment[feature.equipment_id] = feature
        elif isinstance(feature, MapFogQueryFeature):
            map_fog_query = True
        elif isinstance(feature, MovementQueryFeature):
            movement_query = True
        elif isinstance(feature, NativeTimingFeature):
            timing = True
            for values, destination in ((feature.spell_ids, timing_spells),
                                        (feature.effector_ids, timing_effectors)):
                if not isinstance(values, tuple) or len(values) > 1024:
                    raise ValueError("native timing IDs must be tuples of at most 1024 FourCCs")
                keys = tuple(_fourcc_u32(value) for value in values)
                if len(keys) != len(set(keys)):
                    raise ValueError("native timing IDs must be unique within each declaration")
                destination.update(keys)
        else:
            raise ValueError(
                "runtime features must be name-generator, enchantment-row, query, or native timing records"
            )
    if len(names) > _MAX_NAME_GENERATORS:
        raise ValueError(
            f"runtime feature registry has {len(names)} name generators; "
            f"maximum is {_MAX_NAME_GENERATORS}"
        )
    if len(rows) > _MAX_ENCHANTMENT_ROWS:
        raise ValueError(
            f"runtime feature registry has {len(rows)} enchantment rows; "
            f"maximum is {_MAX_ENCHANTMENT_ROWS}"
        )
    if max(len(timing_spells), len(timing_effectors)) > 1024:
        raise ValueError("native timing registry exceeds 1024 IDs per resource family")
    if len(equipment) > MAX_EQUIPMENT:
        raise ValueError("equipment registry exceeds 256 identities")
    if len(research) > MAX_KINGDOM_RESEARCH:
        raise ValueError("kingdom research registry exceeds 32 identities")
    if len(info) > MAX_HERO_INFO_ROWS:
        raise ValueError("hero information registry exceeds 1024 rows")
    if any(row.kind == "enchantment" and _fourcc_u32(row.subject_id) in rows for row in info.values()):
        raise ValueError("hero information and legacy enchantment rows claim the same overlay")
    return RuntimeFeatureRegistry(
        name_generators=tuple(names[key] for key in sorted(names)),
        enchantment_rows=tuple(rows[key] for key in sorted(rows)),
        map_fog_query=map_fog_query,
        movement_query=movement_query,
        equipment=tuple(equipment[key] for key in sorted(equipment)),
        kingdom_research=tuple(research[key] for key in sorted(research)),
        hero_info_rows=tuple(info[key] for key in sorted(info)),
        native_timing=NativeTimingFeature(
            tuple(_u32_fourcc(key) for key in sorted(timing_spells)),
            tuple(_u32_fourcc(key) for key in sorted(timing_effectors)),
        ) if timing else None,
    )


def legacy_runtime_features(capabilities: Iterable[str]) -> tuple[RuntimeFeature, ...]:
    """Translate supported v2 package aliases into reusable feature records."""

    requested = frozenset(capabilities)
    features: list[RuntimeFeature] = []
    if _LEGACY_ALCHEMIST_NAMES in requested:
        features.append(
            NameGeneratorFeature("NM18", ("HN69", "HN70", "HN71", "HN72"))
        )
    if _LEGACY_PHANTOM_NAMES in requested:
        features.append(
            NameGeneratorFeature("NM19", ("HN73", "HN74", "HN75", "HN76"))
        )
    if _LEGACY_ALCHEMIST_ROWS in requested:
        features.extend(
            (
                EnchantmentRowFeature(
                    "ALo1", "Paralytic Oil - brief stun on weapon hit"
                ),
                EnchantmentRowFeature(
                    "ALo2", "Transmutation Oil - +5 gold on weapon hit"
                ),
                EnchantmentRowFeature(
                    "ALo3", "Poisoned Weapon - poison on weapon hit"
                ),
            )
        )
    return tuple(features)


def derive_feature_runtime_capabilities(
    capabilities: Iterable[str], registry: RuntimeFeatureRegistry
) -> tuple[str, ...]:
    """Derive MMCP hook groups from exact MMFR records.

    Legacy v2 capability names are accepted only as package input.  Every
    requested legacy alias must have its exact fixed records in ``registry``;
    generated manifests are then canonicalized to generic, data-driven hook
    names.  Caller-supplied generic names are ignored so an MMCP entry can
    never enable a hook without matching manager-generated MMFR evidence.
    """

    effective = set(capabilities)
    requested_legacy = legacy_runtime_features(effective)
    for feature in requested_legacy:
        if isinstance(feature, NameGeneratorFeature):
            present = feature in registry.name_generators
        else:
            present = feature in registry.enchantment_rows
        if not present:
            raise ValueError(
                "legacy runtime capability is missing its exact translated "
                f"MMFR record: {feature!r}"
            )

    effective.difference_update(
        {
            _LEGACY_ALCHEMIST_NAMES,
            _LEGACY_PHANTOM_NAMES,
            _LEGACY_ALCHEMIST_ROWS,
        }
    )
    effective.discard(NAME_GENERATOR_RUNTIME_CAPABILITY)
    effective.discard(ENCHANTMENT_ROW_RUNTIME_CAPABILITY)
    effective.discard(MAP_QUERY_RUNTIME_CAPABILITY)
    effective.discard(MOVEMENT_QUERY_RUNTIME_CAPABILITY)
    effective.discard(NATIVE_TIMING_RUNTIME_CAPABILITY)
    effective.discard(EQUIPMENT_FEATURE_TYPE)
    effective.discard(KINGDOM_RESEARCH_TYPE)
    effective.discard(HERO_INFO_TYPE)
    if registry.hero_info_rows:
        effective.add(HERO_INFO_TYPE)
    if registry.kingdom_research:
        effective.add(KINGDOM_RESEARCH_TYPE)
    if registry.equipment:
        effective.add(EQUIPMENT_FEATURE_TYPE)
    if registry.map_fog_query:
        effective.add(MAP_QUERY_RUNTIME_CAPABILITY)
    if registry.movement_query:
        effective.add(MOVEMENT_QUERY_RUNTIME_CAPABILITY)
    if registry.native_timing is not None:
        effective.add(NATIVE_TIMING_RUNTIME_CAPABILITY)
    if registry.name_generators:
        effective.add(NAME_GENERATOR_RUNTIME_CAPABILITY)
    if registry.enchantment_rows or any(r.kind == "enchantment" for r in registry.hero_info_rows):
        effective.add(ENCHANTMENT_ROW_RUNTIME_CAPABILITY)
    return tuple(sorted(effective))


def encode_runtime_feature_registry(
    features: RuntimeFeatureRegistry | Iterable[RuntimeFeature] = (),
    *,
    legacy_capabilities: Iterable[str] = (),
) -> bytes:
    registry = (
        normalize_runtime_features(
            features.features, legacy_capabilities=legacy_capabilities
        )
        if isinstance(features, RuntimeFeatureRegistry)
        else normalize_runtime_features(
            features, legacy_capabilities=legacy_capabilities
        )
    )
    visual_research = any(item.active_effector for item in registry.kingdom_research)
    chunks = [
        _HEADER.pack(
            _MAGIC,
            7 if registry.hero_info_rows else 6 if visual_research else 5 if registry.kingdom_research else 4 if registry.equipment else 3 if registry.native_timing is not None else
            2 if registry.map_fog_query or registry.movement_query else _VERSION,
            len(registry.name_generators),
            len(registry.enchantment_rows),
        )
    ]
    if registry.hero_info_rows or registry.kingdom_research or registry.equipment or registry.map_fog_query or registry.movement_query or registry.native_timing is not None:
        chunks.append(struct.pack("<I", int(registry.map_fog_query) |
                                  (int(registry.movement_query) << 1) |
                                  (int(registry.native_timing is not None) << 2) |
                                  (int(bool(registry.equipment)) << 3) |
                                  (int(bool(registry.kingdom_research)) << 4) |
                                  (int(bool(registry.hero_info_rows)) << 5)))
    for feature in registry.name_generators:
        chunks.append(
            _NAME_GENERATOR.pack(
                _fourcc_u32(feature.generator_id, prefix="NM"),
                *(
                    _fourcc_u32(part, prefix="HN")
                    for part in feature.name_part_ids
                ),
            )
        )
    for feature in registry.enchantment_rows:
        text = _display_text_bytes(feature.display_text)
        chunks.extend(
            (
                _ENCHANTMENT_HEADER.pack(
                    _fourcc_u32(feature.overlay_id), len(text)
                ),
                text,
            )
        )
    if registry.native_timing is not None:
        for values in (registry.native_timing.spell_ids, registry.native_timing.effector_ids):
            chunks.append(struct.pack("<I", len(values)))
            chunks.extend(struct.pack("<I", _fourcc_u32(value)) for value in values)
    if registry.equipment:
        chunks.append(struct.pack("<I", len(registry.equipment)))
        chunks.extend(struct.pack("<III", item.equipment_id, item.slot,
                                  _fourcc_u32(item.name_table)) for item in registry.equipment)
    if registry.kingdom_research:
        chunks.append(struct.pack("<I", len(registry.kingdom_research)))
        for item in registry.kingdom_research:
            text = item.completion_text.encode("cp1252")
            chunks.append(struct.pack("<16s11I", bytes.fromhex(item.identity),
                item.building_family, item.action_control_id, item.descriptor_template_control_id,
                item.completion_attribute, item.required_level, item.price,
                item.gold_bonus_percent, item.experience_bonus_percent,
                item.progress_control_id, item.active_display_control_id, len(text)))
            chunks.append(text)
            if visual_research or registry.hero_info_rows:
                effector = item.active_effector.encode("ascii")
                chunks.extend((struct.pack("<I", len(effector)), effector))
    if registry.hero_info_rows:
        chunks.append(struct.pack("<I", len(registry.hero_info_rows)))
        for row in registry.hero_info_rows:
            key, label, tooltip = row.feature_key.encode("ascii"), _display_text_bytes(row.display_text), _display_text_bytes(row.tooltip_text)
            chunks.append(struct.pack("<8I", HERO_INFO_KINDS.index(row.kind) + 1,
                _fourcc_u32(row.subject_id), row.unlock_level, _fourcc_u32(row.image_id),
                row.image_set, len(key), len(label), len(tooltip)))
            chunks.extend((key, label, tooltip))
    payload = b"".join(chunks)
    if len(payload) > _MAX_REGISTRY_BYTES:
        raise ValueError(
            f"runtime feature registry exceeds {_MAX_REGISTRY_BYTES} bytes"
        )
    return payload


def decode_runtime_feature_registry(payload: bytes) -> RuntimeFeatureRegistry:
    if not isinstance(payload, bytes):
        raise ValueError("runtime feature registry must be bytes")
    if len(payload) > _MAX_REGISTRY_BYTES:
        raise ValueError(
            f"runtime feature registry exceeds {_MAX_REGISTRY_BYTES} bytes"
        )
    if len(payload) < _HEADER.size:
        raise ValueError("runtime feature registry header is truncated")
    magic, version, name_count, row_count = _HEADER.unpack_from(payload)
    if magic != _MAGIC:
        raise ValueError("runtime feature registry magic is invalid")
    if version not in (1, 2, 3, 4, 5, 6, 7):
        raise ValueError(f"unsupported runtime feature registry version: {version}")
    if name_count > _MAX_NAME_GENERATORS:
        raise ValueError(
            f"runtime feature registry has {name_count} name generators; "
            f"maximum is {_MAX_NAME_GENERATORS}"
        )
    if row_count > _MAX_ENCHANTMENT_ROWS:
        raise ValueError(
            f"runtime feature registry has {row_count} enchantment rows; "
            f"maximum is {_MAX_ENCHANTMENT_ROWS}"
        )

    header_size = _HEADER.size + (4 if version >= 2 else 0)
    if len(payload) < header_size:
        raise ValueError("runtime feature registry flags are truncated")
    flags = struct.unpack_from("<I", payload, _HEADER.size)[0] if version >= 2 else 0
    if (flags & ~(63 if version == 7 else 31 if version >= 5 else 15 if version == 4 else 7 if version == 3 else 3)
            or (version == 3 and not flags & 4) or (version == 4 and not flags & 8)
            or (version in (5, 6) and not flags & 16) or (version == 7 and not flags & 32)):
        raise ValueError("runtime feature registry has unsupported flags")
    minimum_size = (
        header_size
        + name_count * _NAME_GENERATOR.size
        + row_count * _ENCHANTMENT_HEADER.size
    )
    if minimum_size > len(payload):
        raise ValueError("runtime feature registry cannot contain its declared records")

    offset = header_size
    names: list[NameGeneratorFeature] = []
    previous_generator = -1
    for _index in range(name_count):
        if offset + _NAME_GENERATOR.size > len(payload):
            raise ValueError("name-generator record is truncated")
        values = _NAME_GENERATOR.unpack_from(payload, offset)
        offset += _NAME_GENERATOR.size
        generator_id = values[0]
        if generator_id <= previous_generator:
            raise ValueError(
                "name-generator FourCCs must be strictly sorted and unique"
            )
        names.append(
            NameGeneratorFeature(
                _u32_fourcc(generator_id, prefix="NM"),
                tuple(
                    _u32_fourcc(value, prefix="HN") for value in values[1:]
                ),  # type: ignore[arg-type]
            )
        )
        previous_generator = generator_id

    rows: list[EnchantmentRowFeature] = []
    previous_overlay = -1
    for _index in range(row_count):
        if offset + _ENCHANTMENT_HEADER.size > len(payload):
            raise ValueError("enchantment-row header is truncated")
        overlay_id, text_size = _ENCHANTMENT_HEADER.unpack_from(payload, offset)
        offset += _ENCHANTMENT_HEADER.size
        if overlay_id <= previous_overlay:
            raise ValueError(
                "enchantment-row FourCCs must be strictly sorted and unique"
            )
        if text_size == 0 or text_size > _MAX_DISPLAY_TEXT_BYTES:
            raise ValueError(
                "enchantment-row display text length is outside supported bounds"
            )
        end = offset + text_size
        if end > len(payload):
            raise ValueError("enchantment-row display text is truncated")
        encoded_text = payload[offset:end]
        offset = end
        if b"\x00" in encoded_text or any(
            byte in (0x81, 0x8D, 0x8F, 0x90, 0x9D) for byte in encoded_text
        ):
            raise ValueError(
                "enchantment-row display text is not valid non-NUL Windows-1252"
            )
        try:
            display_text = encoded_text.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "enchantment-row display text is not Windows-1252"
            ) from exc
        rows.append(
            EnchantmentRowFeature(
                _u32_fourcc(overlay_id),
                display_text,
            )
        )
        previous_overlay = overlay_id
    timing_features = ()
    if flags & 4:
        families = []
        for _ in range(2):
            if offset + 4 > len(payload):
                raise ValueError("native timing resource count is truncated")
            count = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            if count > 1024 or offset + 4 * count > len(payload):
                raise ValueError("native timing resources are invalid or truncated")
            keys = struct.unpack_from(f"<{count}I", payload, offset)
            offset += 4 * count
            if any(left >= right for left, right in zip(keys, keys[1:])):
                raise ValueError("native timing IDs must be strictly sorted and unique")
            families.append(tuple(_u32_fourcc(key) for key in keys))
        timing_features = (NativeTimingFeature(*families),)
    equipment = []
    if flags & 8:
        if offset + 4 > len(payload):
            raise ValueError("equipment count is truncated")
        count = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        if not 1 <= count <= MAX_EQUIPMENT or offset + 12 * count > len(payload):
            raise ValueError("equipment records are invalid or truncated")
        previous = 0
        for _ in range(count):
            index, slot, name = struct.unpack_from("<III", payload, offset)
            offset += 12
            if index <= previous:
                raise ValueError("equipment identities must be sorted and unique")
            equipment.append(EquipmentRegistration(index, slot, _u32_fourcc(name)))
            previous = index
    research = []
    if flags & 16:
        if offset + 4 > len(payload):
            raise ValueError("kingdom research count is truncated")
        count = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        if not 1 <= count <= MAX_KINGDOM_RESEARCH:
            raise ValueError("invalid kingdom research count")
        previous = ""
        for _ in range(count):
            if offset + 60 > len(payload):
                raise ValueError("kingdom research record is truncated")
            values = struct.unpack_from("<16s11I", payload, offset)
            offset += 60
            identity, size = values[0].hex(), values[-1]
            if identity <= previous or not 1 <= size <= 96 or offset + size > len(payload):
                raise ValueError("kingdom research identities or text are invalid")
            text = payload[offset:offset+size].decode("cp1252")
            offset += size
            effector = ""
            if version >= 6:
                if offset + 4 > len(payload):
                    raise ValueError("kingdom research active effector length is truncated")
                size = struct.unpack_from("<I", payload, offset)[0]
                offset += 4
                if size > 64 or offset + size > len(payload):
                    raise ValueError("kingdom research active effector is invalid or truncated")
                effector = payload[offset:offset+size].decode("ascii")
                offset += size
            research.append(KingdomResearchRegistration(identity, *values[1:-1], text, effector))
            previous = identity
        if version == 6 and not any(item.active_effector for item in research):
            raise ValueError("MMFR v6 requires an active effector")
    info = []
    if flags & 32:
        if offset + 4 > len(payload):
            raise ValueError("hero information count is truncated")
        count = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        if not 1 <= count <= MAX_HERO_INFO_ROWS:
            raise ValueError("hero information count is invalid")
        for _ in range(count):
            if offset + 32 > len(payload):
                raise ValueError("hero information record is truncated")
            kind, subject, level, image, image_set, nk, nl, nt = struct.unpack_from("<8I", payload, offset)
            offset += 32
            if not (1 <= kind <= 3 and 1 <= nk <= 64 and 1 <= nl <= 512 and 1 <= nt <= 512) or offset + nk + nl + nt > len(payload):
                raise ValueError("hero information fields are invalid or truncated")
            key = payload[offset:offset+nk].decode("ascii")
            label = payload[offset+nk:offset+nk+nl].decode("cp1252")
            tooltip = payload[offset+nk+nl:offset+nk+nl+nt].decode("cp1252")
            offset += nk + nl + nt
            row = HeroInfoRow(key, HERO_INFO_KINDS[kind-1], _u32_fourcc(subject), level,
                              label, tooltip, _u32_fourcc(image), image_set)
            if info and row.sort_key <= info[-1].sort_key:
                raise ValueError("hero information rows must be sorted and unique")
            info.append(row)
    if offset != len(payload):
        raise ValueError("runtime feature registry has trailing bytes")
    return normalize_runtime_features((*names, *rows, *equipment, *research, *info,
        *((MapFogQueryFeature(),) if flags & 1 else ()),
        *((MovementQueryFeature(),) if flags & 2 else ()), *timing_features))


def write_runtime_feature_registry(
    path: Path,
    features: RuntimeFeatureRegistry | Sequence[RuntimeFeature] = (),
    *,
    legacy_capabilities: Iterable[str] = (),
) -> RuntimeFeatureRegistry:
    """Atomically write and return the canonical, decoded registry."""

    payload = encode_runtime_feature_registry(
        features, legacy_capabilities=legacy_capabilities
    )
    canonical = decode_runtime_feature_registry(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", dir=path.parent, delete=False
        ) as stream:
            stream.write(payload)
            stream.flush()
            temporary = Path(stream.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return canonical


__all__ = [
    "EnchantmentRowFeature",
    "ENCHANTMENT_ROW_RUNTIME_CAPABILITY",
    "NAME_GENERATOR_RUNTIME_CAPABILITY",
    "NameGeneratorFeature",
    "RUNTIME_FEATURE_REGISTRY_ENV_VAR",
    "RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH",
    "RuntimeFeature",
    "MapFogQueryFeature",
    "MovementQueryFeature",
    "MOVEMENT_QUERY_RUNTIME_CAPABILITY",
    "NativeTimingFeature",
    "NATIVE_TIMING_RUNTIME_CAPABILITY",
    "MAP_QUERY_RUNTIME_CAPABILITY",
    "RuntimeFeatureRegistry",
    "decode_runtime_feature_registry",
    "derive_feature_runtime_capabilities",
    "encode_runtime_feature_registry",
    "legacy_runtime_features",
    "normalize_runtime_features",
    "write_runtime_feature_registry",
]
