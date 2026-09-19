"""Private identities in Majesty's existing equipment tables (beta2 only).

No per-unit state, shopping rules, rank conversion, or combat callbacks live
here. The stock lifecycle is traced in docs/stock-custom-equipment-audit.md.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import struct
import uuid


EQUIPMENT_FEATURE_TYPE = "stock.equipment.v1"
MAX_EQUIPMENT = 256


@dataclass(frozen=True)
class StockEquipment:
    feature_key: str
    slot: str
    name_table: str
    image_id: str
    image_set: int
    hero_ids: tuple[str, ...]


@dataclass(frozen=True)
class EquipmentRegistration:
    """Manager-owned native record; never accepted from an author verbatim."""
    equipment_id: int
    slot: int  # 0 weapon, 1 armor
    name_table: str

    @property
    def enum_name(self) -> str:
        return f"MME_{self.equipment_id:06X}"

    @property
    def image_id(self) -> str:
        return "INBw" if self.slot == 0 else "INBa"


def fourcc(value, field):
    if not isinstance(value, str) or re.fullmatch(r"[!-~]{4}", value) is None:
        raise ValueError(f"equipment {field} must be a printable ASCII FourCC")
    return value


def parse_equipment(value) -> StockEquipment:
    fields = {"type", "feature_key", "slot", "name_table", "image_id", "image_set", "hero_ids"}
    if set(value) != fields:
        raise ValueError("stock.equipment.v1 requires exactly " + ", ".join(sorted(fields)))
    key = value["feature_key"]
    if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", key) is None:
        raise ValueError("equipment feature_key must be a stable lowercase key (1..64 characters)")
    if value["slot"] not in ("weapon", "armor"):
        raise ValueError("equipment slot must be weapon or armor")
    image_set = value["image_set"]
    if type(image_set) is not int or not 0 <= image_set < 0x1000000:
        raise ValueError("equipment image_set must be an unlayered 24-bit set ID")
    heroes = value["hero_ids"]
    if not isinstance(heroes, list) or not 1 <= len(heroes) <= 256:
        raise ValueError("equipment hero_ids requires 1..256 package-owned hero IDs")
    heroes = tuple(fourcc(item, "hero_ids") for item in heroes)
    if len(set(heroes)) != len(heroes):
        raise ValueError("equipment hero_ids must be unique")
    return StockEquipment(key, value["slot"], fourcc(value["name_table"], "name_table"),
                          fourcc(value["image_id"], "image_id"), image_set, heroes)


def equipment_mapping(feature: StockEquipment) -> dict:
    return dict(type=EQUIPMENT_FEATURE_TYPE, feature_key=feature.feature_key,
                slot=feature.slot, name_table=feature.name_table,
                image_id=feature.image_id, image_set=feature.image_set,
                hero_ids=list(feature.hero_ids))


def registration(mod_id: str, feature: StockEquipment) -> EquipmentRegistration:
    # Stable across selection order and added/removed packages. Never probe to
    # another ID on collision: a saved native type index must not change meaning.
    identity = uuid.UUID(mod_id).bytes + b"\0" + feature.feature_key.encode("ascii")
    index = 0x800000 | (int.from_bytes(hashlib.sha256(identity).digest()[:4], "little") & 0x7FFFFF)
    return EquipmentRegistration(index, int(feature.slot == "armor"), feature.name_table)


def validate_registration(record: EquipmentRegistration) -> None:
    if type(record.equipment_id) is not int or not 0x800000 <= record.equipment_id <= 0xFFFFFF:
        raise ValueError("equipment identity is outside the private unlayered range")
    if type(record.slot) is not int or record.slot not in (0, 1):
        raise ValueError("equipment slot must be 0 or 1")
    fourcc(record.name_table, "name_table")


def require_beta2(executable) -> None:
    """Cheap profile check; native installation separately verifies code bytes."""
    with executable.open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            raise ValueError("Selected runtime features require the audited Steam beta2 executable")
        offset = struct.unpack_from("<I", header, 60)[0]
        if offset > 0x100000:
            raise ValueError("Invalid executable PE header")
        stream.seek(offset)
        pe = stream.read(12)
    if (len(pe) != 12 or pe[:4] != b"PE\0\0" or
            struct.unpack_from("<H", pe, 4)[0] != 0x14C or
            struct.unpack_from("<I", pe, 8)[0] != 0x5A8A11D5):
        raise ValueError("Selected runtime features are supported only on audited Steam beta2 (1.5.2.28); public/unverified executables are not supported")
