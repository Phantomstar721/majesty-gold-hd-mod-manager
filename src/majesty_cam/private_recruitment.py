"""Bounded AP52 presentation/description evidence; no package-specific names."""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from typing import Sequence


class PrivateRecruitmentError(ValueError):
    pass


def validate_descriptions(descriptions: Sequence[ET.Element], parent: str) -> tuple[ET.Element, ...]:
    by_name: dict[str, list[ET.Element]] = {}
    for record in descriptions:
        if record.get("subType") == "Building":
            by_name.setdefault(record.get("Name", ""), []).append(record)
    # The root may be declared as the family name or its exact first stage.
    name = parent if parent in by_name else parent + "1"
    chain, seen, produces, dialog = [], set(), None, None
    while name:
        matches = by_name.get(name, [])
        if len(matches) != 1 or name in seen or len(chain) == 3:
            raise PrivateRecruitmentError("private recruitment requires one acyclic package-owned building chain of at most three levels")
        building = matches[0]
        game = building.find("Game")
        if game is None:
            raise PrivateRecruitmentError("private recruitment building has no Game description")
        value = lambda field: game.find(field).get("value", "") if game.find(field) is not None else ""
        choices = tuple(item.get("ID", "") for item in game.findall("./Produces/Unit"))
        if len(choices) != 3 or len(set(choices)) != 3 or not all(choices):
            raise PrivateRecruitmentError("private recruitment requires exactly three distinct ordered Produces Unit entries")
        if produces is not None and choices != produces:
            raise PrivateRecruitmentError("private recruitment Produces ordering must stay identical across upgrades")
        if dialog is not None and value("DialogID") != dialog:
            raise PrivateRecruitmentError("private recruitment upgrade stages must share one private DialogID")
        flags = {item.get("value") for item in game.findall("Flags")}
        try:
            capacity = int(value("MaxGuildMembers"))
        except ValueError:
            capacity = 0
        if "IsGuild" not in flags or not 1 <= capacity <= 0x7FFFFFFF:
            raise PrivateRecruitmentError("private recruitment requires stock IsGuild and positive shared MaxGuildMembers")
        identifier = building.get("ID", "")
        if len(identifier) != 4 or (chain and identifier != chain[0].get("ID", "")[:3] + str(len(chain)+1)):
            raise PrivateRecruitmentError("private recruitment upgrades require the stock same-family stage IDs ending 1, 2, 3")
        if value("UpgradeFrom") != (chain[-1].get("Name") if chain else ""):
            raise PrivateRecruitmentError("private recruitment UpgradeFrom does not match its preceding stage")
        next_name = value("UpgradeTo")
        if next_name and not chain and not identifier.endswith("1"):
            raise PrivateRecruitmentError("private recruitment upgrade chain must begin at stage 1")
        produces, dialog = choices, value("DialogID")
        seen.add(name)
        chain.append(building)
        name = next_name
    if not dialog or len(dialog) != 4:
        raise PrivateRecruitmentError("private recruitment requires one private four-byte DialogID in its descriptions")
    # A second family sharing this panel would use the wrong indexed contract.
    if any(record.get("Name") not in seen and
           record.find("./Game/DialogID") is not None and
           record.find("./Game/DialogID").get("value") == dialog
           for records in by_name.values() for record in records):
        raise PrivateRecruitmentError("private recruitment DialogID is shared with a building outside its upgrade chain")
    return tuple(chain)


def validate_resolved_descriptions(descriptions: Sequence[ET.Element], dialog: str) -> tuple[ET.Element, ...]:
    # Generated sidecar local_names are owner-qualified metadata hashes, not
    # Description names. Resolve the actual chain from its relocated dialog.
    roots = [record.get("Name", "") for record in descriptions
             if record.get("subType") == "Building"
             and record.find("./Game/DialogID") is not None
             and record.find("./Game/DialogID").get("value") == dialog
             and record.find("./Game/UpgradeFrom") is None]
    if len(roots) != 1:
        raise PrivateRecruitmentError("generated private recruitment requires one root building for its resolved DialogID")
    return validate_descriptions(descriptions, roots[0])


def records(payload: bytes) -> tuple[tuple[int, ...], ...]:
    if not payload or len(payload) % 4:
        raise PrivateRecruitmentError("private recruitment SMNU is not DWORD aligned")
    words = struct.unpack(f"<{len(payload)//4}I", payload)
    result, start = [], 0
    for index, value in enumerate(words):
        if value == 0xFFFFFFFF:
            result.append(words[start:index+1])
            start = index+1
    if start != len(words) or not result or result[-1] != (0xFFFFFFFF,):
        raise PrivateRecruitmentError("private recruitment SMNU has invalid record boundaries")
    return tuple(result)


def control_record(items: Sequence[tuple[int, ...]], control: int) -> tuple[int, ...]:
    matches = [record for record in items if
               any(record[i:i+2] == (6, control) for i in range(6, len(record)-1))]
    if len(matches) != 1:
        raise PrivateRecruitmentError(f"private recruitment requires exactly one SMNU control 0x{control:04X}; found {len(matches)}")
    return matches[0]


def _literal_clone(actual, stock, *, control, template_control, resize=False, icon=False,
                   caption_rect=False, artwork_set=False, font_choices=()):
    if len(actual) != len(stock) or stock[1] != 2:
        return False
    ignored = {2, 3} | ({4, 5} if resize else set())
    if caption_rect:
        # SMNU 0x2A is stock's text rectangle, consumed by the native widget
        # renderer. Keep its font/draw behavior; only permit author geometry
        # within the unchanged button, without borrowing the adjacent price.
        if len(stock) < 11 or stock[6] != 0x2A or actual[6] != 0x2A:
            return False
        left, top, width, height = actual[7:11]
        if not (0 <= left < actual[4] and 0 <= top < actual[5]
                and 0 < width <= actual[4] - left
                and 0 < height <= actual[5] - top):
            return False
        ignored.update(range(7, 11))
    if font_choices:
        # Opt-in stock font alternatives affect only the font value, never the
        # property tag, caption rectangle, colors, flags or widget shape.
        operands = [i+1 for i in range(6, len(stock)-1)
                    if stock[i] == 0x12 and stock[i+1] in font_choices]
        if len(operands) != 1 or actual[operands[0]] not in font_choices:
            return False
        ignored.add(operands[0])
    # These are value operands of literal stock fields, not an SMNU parser.
    # All property tags, widget kind, draw flags and colors remain stock.
    # Font remains exact unless the caller opts into the bounded choices above.
    # Resource identity is private (including cloned INTI/background artwork).
    fields = {7, 0x21, 5, 0x102, 0x10A, 0xC}
    if artwork_set:
        fields.add(0xD)
    for i in range(6, len(stock)-1):
        if stock[i] in fields:
            ignored.add(i+1)
        if stock[i:i+2] == (6, template_control):
            if actual[i:i+2] != (6, control):
                return False
            ignored.add(i+1)
    return all(i in ignored or left == right for i, (left, right) in enumerate(zip(actual, stock)))


def validate_panel(payload: bytes, ap52: bytes, ap53: bytes, third_price: int) -> None:
    panel, stock, wizard = records(payload), records(ap52), records(ap53)
    # All controls AP52 can address during its original constructor/setup must
    # remain present, including offscreen legacy layouts and Call to Arms.
    ids = []
    for record in stock:
        for i in range(6, len(record)-1):
            if record[i] == 6 and record[i+1] >= 0x1000:
                ids.append(record[i+1])
    for control in ids:
        control_record(panel, control)
    for control, template, template_control, resize, icon in (
        *((command, stock, 0x1F49, False, False) for command in (0x1F48, 0x1389, 0x1388)),
        *((price, stock, 0x1F51, False, False) for price in (0x1752, 0x1F51, third_price)),
        *((count, stock, count, True, False) for count in (0x1F1B, 0x1F0D, 0x1F1C)),
        *((icon_id, stock, icon_id, False, True) for icon_id in (0x1F19, 0x1F52, 0x1F1A)),
        *((shared, stock, shared, False, False) for shared in (0x1F56, 0x1F57)),
        *((upgrade, wizard, upgrade, False, False) for upgrade in (0x1E28, 0x1F47, 0x1F4F)),
    ):
        if not _literal_clone(control_record(panel, control),
                              control_record(template, template_control),
                              control=control, template_control=template_control,
                              resize=resize, icon=icon,
                              caption_rect=control in (0x1F48, 0x1389, 0x1388)):
            raise PrivateRecruitmentError(f"private recruitment control 0x{control:04X} must preserve its literal stock widget shape")
    for control in (0x22CE, 0x1F49, 0x1181, 0x1F0E, 0x1F11, 0x1F12, 0x1F13, 0x1F14):
        record = control_record(panel, control)
        if record[2] < 224 and record[3] < 256:
            raise PrivateRecruitmentError(f"private recruitment legacy control 0x{control:04X} must be offscreen")


def validate_secondary_panel(parent: bytes, child: bytes, templates: dict[bytes, bytes],
                             third_price: int, opener: int) -> None:
    """Validate native AP52 controls and the AP10/AP69 navigation widgets."""
    stock = records(templates[b"AP52"])
    wizard = records(templates[b"AP53"])
    main, sub = records(parent), records(child)
    for panel in (main, sub):
        for row in stock:
            for i in range(6, len(row)-1):
                if row[i] == 6 and row[i+1] >= 0x1000:
                    control_record(panel, row[i+1])

    def require(panel, control, template, original, resize=False, artwork_set=False, font_choices=()):
        if not _literal_clone(control_record(panel, control), control_record(template, original),
                              control=control, template_control=original, resize=resize,
                              artwork_set=artwork_set, font_choices=font_choices):
            raise PrivateRecruitmentError(f"recruitment panel control 0x{control:04X} must retain its stock widget")

    require(main, opener, records(templates[b"AP10"]), 0x1F49, artwork_set=True)
    require(sub, 0x1F4D, records(templates[b"AP69"]), 0x1F4D)
    for control in (0x1F48, 0x1389, 0x1388):
        # AP52's full-width 0x1389 uses fnt4; its other recruit widgets
        # 0x1388/0x1F48 use fnt7. Either stock recruit font is valid here.
        require(sub, control, stock, 0x1389, font_choices=(0x34746E66, 0x37746E66))
    for control in (0x1752, 0x1F51, third_price):
        require(sub, control, stock, 0x1F51)
    for control in (0x1F56, 0x1F57):
        require(sub, control, stock, control)
    for control in (0x1F1B, 0x1F0D, 0x1F1C, 0x1F19, 0x1F52, 0x1F1A):
        require(main, control, stock, control, resize=control in (0x1F1B, 0x1F0D, 0x1F1C))
    for control in (0x1E28, 0x1F47, 0x1F4F):
        require(main, control, wizard, control)
    hidden = (0x22CE, 0x1F49, 0x1181, 0x1F0E, 0x1F11, 0x1F12, 0x1F13, 0x1F14)
    for panel, controls in ((main, hidden + (0x1F48, 0x1389, 0x1388, 0x1752, 0x1F51, third_price, 0x1F56, 0x1F57)),
                            (sub, hidden)):
        for control in controls:
            row = control_record(panel, control)
            if row[2] < 224 and row[3] < 256:
                raise PrivateRecruitmentError(f"recruitment control 0x{control:04X} belongs offscreen on this panel")
