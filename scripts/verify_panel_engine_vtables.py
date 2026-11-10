"""Identify SDK class tables by complete RTTI data, not matching getter bytes.

Reads initialized PE data only. Code targets are checked to lie in executable
sections; their implementations are not expanded. A class name alone is not
accepted: the complete-object locator, zero subobject offset, hierarchy and
unique table reference must agree with the Public SDK anchor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

from panel_engine_profile_sources import ROOT, BRANCHES
sys.path.insert(0, str(ROOT / 'src'))
from majesty_cam.manager.qol_service import detect_majesty_branch


def read(pe, address, size):
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    section = pe.get_section_by_rva(rva)
    if section is None or section.Characteristics & 0x20000000 or not section.Characteristics & 0x40:
        raise ValueError('RTTI reference is outside initialized data')
    if rva + size > section.VirtualAddress + section.SizeOfRawData:
        raise ValueError('RTTI reference crosses its data section')
    result = pe.get_data(rva, size)
    if len(result) != size:
        raise ValueError('Truncated RTTI record')
    return result


def words(pe, address, count):
    return struct.unpack('<' + 'I' * count, read(pe, address, count * 4))


def typename(pe, address):
    # MSVC x86 TypeDescriptor: type_info vtable, spare word, decorated NUL name.
    prefix = words(pe, address, 2)
    if prefix[1] != 0:
        raise ValueError('Unsupported RTTI type descriptor')
    raw = bytearray()
    for index in range(200):
        char = read(pe, address + 8 + index, 1)
        if char == b'\0':
            return bytes(raw).decode('ascii')
        raw.extend(char)
    raise ValueError('Unterminated RTTI class name')


def table_data(pe, address, slots):
    locator = words(pe, address - 4, 1)[0]
    signature, offset, construction, descriptor, hierarchy = words(pe, locator, 5)
    if (signature, offset, construction) != (0, 0, 0):
        raise ValueError('Unsupported complete-object locator')
    _, attributes, count, base_array = words(pe, hierarchy, 4)
    if not 1 <= count <= 32:
        raise ValueError('Unsupported RTTI hierarchy')
    bases = []
    for base_descriptor in words(pe, base_array, count):
        base_type, contained, member, vbase, vdisp, flags = words(pe, base_descriptor, 6)
        bases.append({'name': typename(pe, base_type), 'contained': contained,
                      'placement': [member, vbase, vdisp], 'attributes': flags})
    targets = words(pe, address, slots)
    for target in targets:
        section = pe.get_section_by_rva(target - pe.OPTIONAL_HEADER.ImageBase)
        if section is None or not section.Characteristics & 0x20000000:
            raise ValueError('RTTI vtable contains a non-executable method target')
    return {'va': address, 'name': typename(pe, descriptor), 'hierarchyAttributes': attributes,
            'bases': bases, 'slots': list(targets),
            'sha256': hashlib.sha256(read(pe, address - 4, (slots + 1) * 4)).hexdigest()}


def aligned_references(pe, value):
    needle = struct.pack('<I', value)
    for section in pe.sections:
        if section.Characteristics & 0x20000000 or not section.Characteristics & 0x40:
            continue
        data = section.get_data()
        offset = data.find(needle)
        while offset >= 0:
            address = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + offset
            if address % 4 == 0:
                yield address
            offset = data.find(needle, offset + 1)


def find_table(pe, anchor, slots):
    types = []
    name = anchor['name'].encode('ascii') + b'\0'
    for section in pe.sections:
        if section.Characteristics & 0x20000000 or not section.Characteristics & 0x40:
            continue
        data = section.get_data()
        offset = data.find(name)
        while offset >= 0:
            address = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + offset - 8
            if address % 4 == 0 and typename(pe, address) == anchor['name']:
                types.append(address)
            offset = data.find(name, offset + 1)
    if len(types) != 1:
        raise ValueError('Missing or ambiguous native type descriptor: ' + anchor['name'])
    matches = []
    for reference in aligned_references(pe, types[0]):
        locator = reference - 12
        if words(pe, locator, 3) != (0, 0, 0):
            continue
        for table_reference in aligned_references(pe, locator):
            candidate = table_data(pe, table_reference + 4, slots)
            if candidate['bases'] == anchor['bases'] and candidate['hierarchyAttributes'] == anchor['hierarchyAttributes']:
                matches.append(candidate)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous native class table: ' + anchor['name'])
    return matches[0]


def verify(fixtures):
    import pefile
    provider = json.loads((ROOT / 'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    # GplInteger is used only through slot10 by GDH_RETURN. The base list uses
    # slots0..14 in the SDK. These are minimum consumed contracts, not a claim
    # that copying 40 entries or a complete native class layout is verified.
    roots = {'gplInteger': (0x7463f4, 11), 'unitList': (0x73d204, 15),
             'statsWindow': (0x73e3f0, 11), 'basicBuilding': (0x73d14c, 13)}
    images = {}
    for branch in BRANCHES:
        path = fixtures[branch]
        detected = detect_majesty_branch(path)
        if detected is None or not (detected.key == branch or branch == 'gog' and detected.key.startswith('gog')):
            raise ValueError('Unsupported fixture identity: ' + branch)
        if hashlib.sha256(path.read_bytes()).hexdigest() != provider[branch]['fixtureSha256']:
            raise ValueError('Fixture changed: ' + branch)
        images[branch] = pefile.PE(str(path))
    anchors = {name: table_data(images['public'], address, slots) for name, (address, slots) in roots.items()}
    profiles = {}
    for branch, pe in images.items():
        profiles[branch] = {'fixtureSha256': provider[branch]['fixtureSha256'],
            'classes': {name: find_table(pe, anchors[name], slots) for name, (_, slots) in roots.items()}}
    return {'schema': 1, 'contract': 'panel-engine.rtti-data.v1',
            'source': 'SDK GPL_INTEGER_VT/LIST_VTABLE; native x86 MSVC RTTI records',
            'limits': 'Class-table identity and consumed target slots only; native implementations, full sizes and 40-slot copying remain unproved.',
            'profiles': profiles}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
