"""Stock equipment evidence and post-relocation presentation binding."""
from dataclasses import replace
import struct

from .equipment import StockEquipment, EquipmentRegistration, registration
from .strt import parse_strt


def declarations(inventory):
    return tuple(item for item in inventory.selected.package.definition.runtime_features
                 if isinstance(item, StockEquipment))


def _one_resource(inventory, section, key):
    matches = [item for item in inventory.resources
               if item.section == section and item.key == key.encode("ascii")]
    if len(matches) != 1:
        raise ValueError(f"equipment requires exactly one package-owned {section.decode()}/{key}")
    return matches[0]


def validate_names(inventory, name_table):
    table = parse_strt(_one_resource(inventory, b"STRT", name_table).entry.data)
    if (not 4 <= len(table.records) <= 64 or
            [row.string_id for row in table.records] != list(range(len(table.records))) or
            any(not row.text or len(row.text) > 128 for row in table.records)):
        raise ValueError("equipment names require 4..64 nonempty rank-ordered STRT entries with IDs 0..N-1 (at most 128 bytes each)")


def _equipment_set_frames(header, payload):
    """Prove the coherent Original/MX stock layout and return its TILE fields.

    Original INBw/INBa use v3/116 bytes; MX uses v4/124 bytes. The two extra
    words precede the MX frame pairs and must not be omitted under a v4 header.
    The general end-anchored reference reader intentionally doesn't prove this
    version-specific layout; equipment must do so before and after binding.
    """
    headers = {struct.pack("<5I", version, 0, 0, 0, 0): version for version in (3, 4)}
    version = headers.get(header)
    if version is None:
        raise ValueError("equipment IMAG must clone a stock INBw/INBa version-3 or version-4 header")
    prefix = [1, 0, 0, 256] + [0] * 12 + [68, 0, 262145, 0, 0]
    if version == 4:
        prefix += [65536, 0]
    expected = prefix + [0] * 8
    if len(payload) != 4 * len(expected):
        raise ValueError(f"equipment icon set must match its version-{version} stock frame layout")
    values = list(struct.unpack(f"<{len(expected)}I", payload))
    fields = tuple(range(len(prefix) + 1, len(expected), 2))
    tile_indices = tuple(values[index] for index in fields)
    for index in fields:
        values[index] = 0
    if values != expected or any(index >= 0xFFFF for index in tile_indices):
        raise ValueError("equipment icon set changed stock frame flags, direction, timing, or geometry")
    return fields, tile_indices


def validate_art(inventory, image_id, image_set):
    from .compose import _split_imag_sets
    image = _one_resource(inventory, b"IMAG", image_id)
    header, sets = _split_imag_sets(image.entry)
    _fields, tile_indices = _equipment_set_frames(header, dict(sets).get(image_set, b""))
    tiles = [item for item in inventory.resources if item.section == b"TILE"
             and item.source == image.source and item.cam_order == image.cam_order]
    if (not tiles or len({item.section_order for item in tiles}) != 1 or
            sorted(item.entry_order for item in tiles) != list(range(len(tiles)))):
        raise ValueError("equipment IMAG requires one complete TILE table in the same archive")
    by_index = {item.entry_order: item.entry.data for item in tiles}
    for index in tile_indices:
        tile = by_index.get(index, b"")
        # Literal stock type-1 23x23 pixels + embedded 256-color palette.
        if len(tile) != 1587 or tile[:20] != struct.pack("<10H", 1, 23, 23, 23, 0, 0, 0, 0, 255, 0):
            raise ValueError(f"equipment TILE {index} must clone stock 23x23 type-1 icon storage including its embedded palette")


def resolve_equipment(inventories):
    from .compose import _parse_description_file
    records = []
    claimed_ids, claimed_heroes = {}, {}
    for inventory in inventories:
        features = declarations(inventory)
        if not features:
            continue
        descriptions = [record.to_element() for path in inventory.descriptions
                        for record in _parse_description_file(path).records]
        owner = inventory.selected.alias
        for feature in features:
            label = f"{owner}: equipment {feature.feature_key}"
            try:
                if feature.name_table in {f"EN{index:02d}" for index in range(1, 16)}:
                    raise ValueError("equipment name table must not replace stock EN01..EN15")
                if feature.image_id in ("INBw", "INBa"):
                    raise ValueError("equipment artwork must use a package-private IMAG, not INBw/INBa")
                validate_names(inventory, feature.name_table)
                validate_art(inventory, feature.image_id, feature.image_set)
                for section, key in ((b"STRT", feature.name_table), (b"IMAG", feature.image_id)):
                    if any(other is not inventory and any(resource.section == section and
                           resource.key == key.encode("ascii") for resource in other.resources)
                           for other in inventories):
                        raise ValueError(f"private equipment {section.decode()}/{key} is also supplied by another package")
                resolved = registration(inventory.selected.package.mod_id, feature)
                if resolved.equipment_id in claimed_ids:
                    raise ValueError(f"stable ID collision with {claimed_ids[resolved.equipment_id]}; change the new feature key, never reassign an existing saved identity")
                claimed_ids[resolved.equipment_id] = label
                for hero in feature.hero_ids:
                    key = (hero, feature.slot)
                    if key in claimed_heroes:
                        raise ValueError(f"{hero} {feature.slot} is also assigned by {claimed_heroes[key]}")
                    matches = [element for element in descriptions
                               if element.get("type") == "Unit" and element.get("ID") == hero
                               and element.get("subType") == "Character"]
                    if len(matches) != 1:
                        raise ValueError(f"{hero} must be exactly one package-owned Unit/Character Description")
                    slot = feature.slot.title()
                    allowed = matches[0].findall(f"./Game/Allowed{slot}")
                    base = matches[0].findall(f"./Game/{slot}BasicDamage")
                    if len(allowed) != 1 or len(base) != 1 or not allowed[0].get("value"):
                        raise ValueError(f"{hero} needs one Game/Allowed{slot} and {slot}BasicDamage")
                    raw = base[0].get("value", "")
                    if not raw.isascii() or not raw.isdecimal() or not 0 <= int(raw) <= 0x7FFFFFFF:
                        raise ValueError(f"{hero} {slot}BasicDamage must be a nonnegative signed-32-bit stock value")
                    claimed_heroes[key] = label
                records.append(resolved)
            except ValueError as exc:
                raise ValueError(f"{label}: {exc}") from exc
    return tuple(records)


def transform_equipment_description(definition, element):
    if element.get("type") != "Unit" or element.get("subType") != "Character":
        return
    for feature in definition.runtime_features:
        if isinstance(feature, StockEquipment) and element.get("ID") in feature.hero_ids:
            fields = element.findall(f"./Game/Allowed{feature.slot.title()}")
            if len(fields) != 1:
                raise ValueError("equipment hero has an ambiguous Allowed equipment field")
            fields[0].set("value", registration(definition.mod_id, feature).enum_name)


def bind_equipment_art(results, inventories):
    """Graft only already-relocated sets into the native equipment IMAGs.

    A TILE index has meaning only within its art domain. Cross-domain copying
    is forbidden; authors must package their native icons in the interface domain.
    """
    from .compose import _split_imag_sets, _join_imag_sets
    for inventory in inventories:
        for feature in declarations(inventory):
            record = registration(inventory.selected.package.mod_id, feature)
            target_key = record.image_id.encode("ascii")
            source_key = feature.image_id.encode("ascii")
            sources = [(i, entry) for i, result in enumerate(results)
                       for section in result.archive.sections if section.extension == b"IMAG"
                       for entry in section.entries if entry.name[:4] == source_key]
            targets = [(i, entry) for i, result in enumerate(results)
                       for section in result.archive.sections if section.extension == b"IMAG"
                       for entry in section.entries if entry.name[:4] == target_key]
            if len(sources) != 1 or len(targets) != 1 or sources[0][0] != targets[0][0]:
                raise ValueError(f"{inventory.selected.alias}: equipment artwork must share the stock interface art domain with {record.image_id}")
            index, target = targets[0]
            source_header, source_sets = _split_imag_sets(sources[0][1])
            payload = dict(source_sets).get(feature.image_set)
            header, sets = _split_imag_sets(target)
            if payload is None or record.equipment_id in dict(sets):
                raise ValueError("equipment icon set is missing or its stable target ID collides")
            # Clone the destination's stock recipe, not the source set's bytes:
            # Original and MX containers use different per-set frame layouts.
            # Only substitute the four already-relocated private TILE values.
            template_id = 1004 if record.slot == 0 else 1000
            template = dict(sets).get(template_id, b"")
            _source_fields, tiles = _equipment_set_frames(source_header, payload)
            target_fields, _stock_tiles = _equipment_set_frames(header, template)
            bound_payload = bytearray(template)
            for field, tile in zip(target_fields, tiles):
                struct.pack_into("<I", bound_payload, field * 4, tile)
            updated = _join_imag_sets(target, header, (*sets, (record.equipment_id, bytes(bound_payload))))
            result = results[index]
            sections = tuple(replace(section, entries=tuple(updated if entry is target else entry
                             for entry in section.entries)) for section in result.archive.sections)
            results = (*results[:index], replace(result, archive=replace(result.archive, sections=sections)), *results[index + 1:])
    return results


def validate_generated_equipment(inventory, record: EquipmentRegistration):
    from .compose import _parse_description_file
    validate_names(inventory, record.name_table)
    validate_art(inventory, record.image_id, record.equipment_id)
    slot = "Weapon" if record.slot == 0 else "Armor"
    if not any(element.get("subType") == "Character" and
               any(field.get("value") == record.enum_name for field in element.findall(f"./Game/Allowed{slot}"))
               for path in inventory.descriptions
               for description in _parse_description_file(path).records
               for element in (description.to_element(),)):
        raise ValueError(f"generated equipment {record.enum_name} has no hero assignment")
