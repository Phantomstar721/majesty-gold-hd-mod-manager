"""Read-only admission of ordinary private actor animation resources."""
import struct


def validate_image(entry):
    # Version-4 layout and exclusions are mapped in private-imag-admission-
    # 20261004. Reuse the archive's bounded set parser; never load native caches.
    from .compose import _split_imag_sets
    header, sets = _split_imag_sets(entry)
    if header != struct.pack('<5I', 4, 0, 0, 0, 0):
        raise ValueError('private placement image requires the ordinary version-4 header')
    u32 = lambda data, offset: struct.unpack_from('<I', data, offset)[0]
    seen = set()
    try:
        for key, data in sets:
            if key in seen or key >> 24 or len(data) < 0x40:
                raise ValueError('private placement image has ambiguous families')
            seen.add(key)
            count = u32(data, 0)
            if not 0 < count <= 32 or u32(data, 0x10) or data[0x2C:0x3C] != bytes(16):
                raise ValueError('private placement image has nonordinary set metadata')
            offsets = [u32(data, 0x40 + 4*d) for d in range(count)]
            if offsets != sorted(set(offsets)) or offsets[0] < 0x40 + 4*count:
                raise ValueError('private placement direction table is invalid')
            for direction, start in enumerate(offsets):
                end = offsets[direction+1] if direction+1 < count else len(data)
                if start+20 > end or end > len(data):
                    raise ValueError('private placement direction is truncated')
                _, _, streams, frames, rectangles, other, timing, groups = struct.unpack_from('<hhHHIIHH', data, start)
                if streams not in (1, 2) or not frames or rectangles >= 8 or other or timing or groups != 1:
                    raise ValueError('private placement image has unsupported attachment/frame metadata')
                pairs = start + 20 + 8*bin(rectangles).count('1') + 4
                if pairs + 8*streams*frames != end:
                    raise ValueError('private placement frame topology is incomplete')
                if any(u32(data, pairs+8*i+4) & 0x18000000 for i in range(streams*frames)):
                    raise ValueError('private placement image cannot acquire alternate 3D resources')
        if not {8, 65, 66} <= seen:
            raise ValueError('private placement image lacks Stand/departure/arrival families')
    except struct.error as exc:
        raise ValueError('truncated private placement image') from exc


def certify(binding, records, inventories, art_results, stock_records):
    from .attack_observation import _description_index
    actor_key = ('unit', binding.feature.actor.casefold())
    actor = _description_index(records, {actor_key})[actor_key].to_element()
    node = actor.find('Engine/ImageIDBase')
    image = node.get('value', '') if node is not None else ''
    if len(image) != 4 or not image.isascii():
        raise ValueError('private placement actor requires a four-byte image identity')
    key = image.encode('ascii')
    for record in stock_records:
        node = record.to_element().find('Engine/ImageIDBase')
        if node is not None and node.get('value') == image:
            raise ValueError('placement presentation must not replace a stock actor image')
    resources = [(inv, resource) for inv in inventories for resource in inv.resources
                 if resource.section == b'IMAG' and resource.key == key]
    if len(resources) != 1:
        raise ValueError('placement image must have exactly one package owner; competing overrides are not safe')
    inv, resource = resources[0]
    from .compose import _normalized_mod_uuid
    if _normalized_mod_uuid(inv.selected.package.mod_id) != binding.owner:
        raise ValueError('placement image must belong to the action provider')
    validate_image(resource.entry)
    output = [entry for result in art_results for section in result.archive.sections
              if section.extension == b'IMAG' for entry in section.entries if entry.name[:4] == key]
    if len(output) != 1:
        raise ValueError('placement image is missing or ambiguous in composed artwork')
    validate_image(output[0])
    return int.from_bytes(key, 'little')
