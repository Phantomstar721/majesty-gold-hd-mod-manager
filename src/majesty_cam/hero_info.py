"""Data-only presentation in stock AP78's learned/effect lists."""
from dataclasses import asdict, dataclass
import re
import struct

HERO_INFO_TYPE = "stock.ap78-info-row.v1"
HERO_INFO_KINDS = ("spell", "enchantment", "passive")
MAX_HERO_INFO_ROWS = 1024


def enable_native_tooltips(payload):
    """Retain AP78's list records, enabling stock hover registration at load."""
    from .private_recruitment import records, control_record
    items = list(records(payload))
    for control in (0x221A, 0x221B):
        row = control_record(items, control)
        # Literal AP78 listbox property layout: type 6, flags property 3,
        # then control-ID property 6. Do not search arbitrary values for flags.
        if len(row) < 20 or row[0] != 6 or row[16] != 3 or row[18:20] != (6, control):
            raise ValueError("AP78 information list has an unsupported flags/control layout")
        changed = list(row)
        changed[17] |= 0x400  # FLAG_HAS_TOOLTIP; stock owns hover registration.
        items[items.index(row)] = tuple(changed)
    return b"".join(struct.pack(f"<{len(row)}I", *row) for row in items)


@dataclass(frozen=True)
class HeroInfoRow:
    feature_key: str
    kind: str
    subject_id: str
    unlock_level: int
    display_text: str
    tooltip_text: str
    image_id: str
    image_set: int

    @property
    def sort_key(self):
        return (HERO_INFO_KINDS.index(self.kind) + 1,
                int.from_bytes(self.subject_id.encode("ascii"), "little"), self.feature_key)


def parse_hero_info(value):
    from .runtime_features import _fourcc_bytes, _display_text_bytes
    fields = set(HeroInfoRow.__dataclass_fields__)
    if set(value) != fields | {"type"} or value.get("type") != HERO_INFO_TYPE:
        raise ValueError("hero information row requires exactly " + ", ".join(sorted(fields)))
    if not isinstance(value["feature_key"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value["feature_key"]):
        raise ValueError("hero information feature_key must be a lowercase logical key")
    kind = value["kind"]
    if kind not in HERO_INFO_KINDS:
        raise ValueError("hero information kind must be spell, enchantment or passive")
    for name in ("subject_id", "image_id"):
        _fourcc_bytes(value[name])
    if value["image_id"] in ("INTn", "IX93"):
        raise ValueError("hero information icons require a private IMAG, not INTn/IX93")
    level = value["unlock_level"]
    if type(level) is not int or not (1 <= level <= 1000 if kind == "passive" else level == 0):
        raise ValueError("unlock_level must be 1..1000 for passive rows and 0 for native spell/effect rows")
    if type(value["image_set"]) is not int or not 0 <= value["image_set"] <= 0xFFFFFF:
        raise ValueError("hero information image_set must be an unlayered 24-bit set ID")
    for name in ("display_text", "tooltip_text"):
        _display_text_bytes(value[name])
    return HeroInfoRow(**{name: value[name] for name in fields})


def hero_info_mapping(row):
    value = dict(type=HERO_INFO_TYPE, **asdict(row))
    parse_hero_info(value)
    return value


def validate_hero_info_evidence(inventory, row):
    from .compose import _parse_description_file, _split_imag_sets
    hero_info_mapping(row)
    type_name, subtype = {"spell": ("Action", "Standard"),
                          "enchantment": ("Unit", "Overlay"),
                          "passive": ("Unit", "Character")}[row.kind]
    matches = [record.to_element() for path in inventory.descriptions
               for record in _parse_description_file(path).records
               if record.key == (type_name, row.subject_id)]
    if len(matches) != 1 or matches[0].get("subType") != subtype:
        raise ValueError(f"hero information {row.subject_id} needs one owned {type_name}/{subtype} Description")
    if row.kind == "spell":
        flags = matches[0].findall("./Game/Flags")
        if len(flags) != 1 or "IsSpell" not in re.split(r"[\s|,]+", flags[0].get("value", "")):
            raise ValueError("hero spell row must identify an actual IsSpell Action")
    images = [r for r in inventory.resources if r.section == b"IMAG" and r.key == row.image_id.encode("ascii")]
    if len(images) != 1:
        raise ValueError(f"hero information requires exactly one owned IMAG/{row.image_id}")
    image = images[0]
    header, sets = _split_imag_sets(image.entry)
    payload = dict(sets).get(row.image_set, b"")
    # Literal INTn/IX93 version-4 static set, with only the TILE index changed.
    expected = [1, 0, 0, 256] + [0] * 12 + [68, 0, 65537, 0, 0, 65536, 0, 0, 0]
    if header != struct.pack("<5I", 4, 0, 0, 0, 0) or len(payload) != len(expected) * 4:
        raise ValueError("hero information IMAG must clone the stock version-4 INTn/IX93 single-frame set")
    values = list(struct.unpack("<25I", payload))
    index, values[-1] = values[-1], 0
    if values != expected or index >= 0xFFFF:
        raise ValueError("hero information icon changed stock direction, frame flags or timing")
    tiles = [r for r in inventory.resources if r.section == b"TILE"
             and r.source == image.source and r.cam_order == image.cam_order]
    if not tiles or len({r.section_order for r in tiles}) != 1:
        raise ValueError("hero information IMAG needs one TILE table in its own archive")
    tile = [r.entry.data for r in tiles if r.entry_order == index]
    side = 25 if row.kind == "enchantment" else 24
    if len(tile) != 1 or len(tile[0]) != 1058 + side * side:
        raise ValueError(f"hero information icon must use stock {side}x{side} indexed TILE storage")
    fields = struct.unpack_from("<10H", tile[0])
    if fields[:8] != (1, side, side, side, 0, 0, 0, 0) or fields[8] > 255 or fields[9] != 0:
        raise ValueError("hero information TILE changed stock geometry or pixel format")
