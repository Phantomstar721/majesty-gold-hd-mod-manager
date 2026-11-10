"""Verify normal UI constructor bodies and their primary class-table binding.

Exception handler address operands remain opaque; their implementations are
never decoded. We select the actual RTTI class, never one of the many unrelated
constructors with identical instruction prefixes. Base calls are delegated to
stock with the same argument/return shape; no actor construction is followed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, manager_profiles
from verify_panel_engine_data_clients import decode


def pattern(body, address):
    import capstone
    masks = set()
    for instruction in decode(body, address):
        offset = instruction.address - address
        if instruction.group(capstone.CS_GRP_CALL) and instruction.operands[0].type == capstone.x86.X86_OP_IMM:
            masks.update(range(offset + instruction.imm_offset, offset + instruction.imm_offset + instruction.imm_size))
        for operand in instruction.operands:
            if operand.type == capstone.x86.X86_OP_MEM and 0x400000 <= operand.mem.disp < 0x900000:
                masks.update(range(offset + instruction.disp_offset, offset + instruction.disp_offset + instruction.disp_size))
            if operand.type == capstone.x86.X86_OP_IMM and not (instruction.group(capstone.CS_GRP_CALL) or instruction.group(capstone.CS_GRP_JUMP)) and 0x400000 <= operand.imm < 0x900000:
                masks.update(range(offset + instruction.imm_offset, offset + instruction.imm_offset + instruction.imm_size))
    return re.compile(b''.join(b'[\\s\\S]' if index in masks else re.escape(bytes([value])) for index, value in enumerate(body)))


def target(body, address, offset):
    if body[offset] != 0xe8:
        raise ValueError('Constructor no longer uses the expected direct stock call')
    return address + offset + 5 + struct.unpack_from('<i', body, offset + 1)[0]


def verify(fixtures):
    import pefile
    vtables = json.loads((ROOT / 'profiles/panel-engine/vtables.json').read_bytes())['profiles']
    manager = manager_profiles()
    images = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != vtables[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed native fixture: ' + branch)
        images[branch] = pefile.PE(data=raw)
    # (source Public VA, complete normal bytes, vtable literal operand offset,
    # corresponding class). All end in ret8: stock takes view and unit.
    roots = {'statsWindow': (0x4aea20, 100, 0x43),
             'basicBuilding': (0x495b10, 138, 0x45),
             'unitList': (0x498f80, 129, 0x46)}
    result = {branch: {'fixtureSha256': vtables[branch]['fixtureSha256'], 'constructors': {}} for branch in BRANCHES}
    for name, (public_address, size, literal_offset) in roots.items():
        original = images['public'].get_data(public_address - 0x400000, size)
        if original[-3:] != bytes.fromhex('c20800'):
            raise ValueError('Constructor argument contract changed')
        template = pattern(original, public_address)
        for branch, pe in images.items():
            table = vtables[branch]['classes'][name]['va']
            found = []
            for section in pe.sections:
                if not section.Characteristics & 0x20000000:
                    continue
                for match in template.finditer(section.get_data()):
                    body = match.group()
                    if struct.unpack_from('<I', body, literal_offset)[0] != table:
                        continue
                    address = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start()
                    decode(body, address)
                    found.append((address, body))
            if len(found) != 1:
                raise ValueError('Constructor correspondence ambiguous/missing: ' + name + '/' + branch)
            address, body = found[0]
            row = {'va': address, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                   'primaryVtableVA': table, 'returnStackBytes': 8}
            if name == 'statsWindow':
                row['opaqueBaseControllerVA'] = target(body, address, 0x34)
            else:
                offset = 0x36 if name == 'basicBuilding' else 0x34
                stats = result[branch]['constructors']['statsWindow']['va']
                if target(body, address, offset) != stats:
                    raise ValueError('UI constructor does not delegate to its stock StatsWindow base')
                row['statsConstructorVA'] = stats
            if name == 'basicBuilding':
                expected = 0x400000 + int(manager[branch]['uiManagerRva'], 0)
                if target(body, address, 0x49) != expected:
                    raise ValueError('Building constructor changed its UI context provider')
                row['uiContextVA'] = expected
            result[branch]['constructors'][name] = row
    return {'schema': 1, 'contract': 'panel-engine.ui-construction.v1',
            'sources': ['SDK STATS_CTOR/BUILDING_CTOR/LIST_CTOR',
                        'profiles/panel-engine/vtables.json', 'runtime/MajestyModManagerRuntime.cpp:uiManagerRva'],
            'limits': 'Complete normal constructor callers/class identity; base/allocator/exception implementations and full layout/teardown remain separate.',
            'profiles': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
