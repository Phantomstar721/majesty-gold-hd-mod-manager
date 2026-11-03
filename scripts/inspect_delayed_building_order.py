"""Bounded offline delayed-research order evidence. Never attaches to a process.

2026-10-18 user-approved Manager investigation of the saved charge lifecycle.
RTTI identifies each table independently; evidence stops at external callees.
This is not proof of destruction, owner transfer, or exactly-once delivery.
"""
import hashlib
import json
import struct
import capstone
from inspect_bounty_draw_boundary import PROFILES
from trace_dawnfall_lifecycle import Image


def inspect(path, expected):
    image = Image(path)
    if hashlib.sha256(image.data).hexdigest() != expected:
        raise ValueError('Unsupported executable')
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    word = lambda address: struct.unpack('<I', image.read(address, 4))[0]
    result = {'path': str(path), 'sha256': expected, 'classes': {}}
    for name in ('GS_ResearchOrder', 'GS_BaseDelayedOrder', 'OrderEntry', 'OrderHeader'):
        names = list(image.find(('.?AV' + name + '@@\0').encode()))
        if len(names) != 1:
            raise ValueError('Ambiguous RTTI: ' + name)
        descriptor = names[0] - 8
        locators = [ref - 12 for ref in image.find(struct.pack('<I', descriptor))
                    if image.read(ref - 12, 12) == bytes(12)]
        tables = [ref + 4 for locator in locators
                  for ref in image.find(struct.pack('<I', locator))]
        if len(tables) != 1:
            raise ValueError('Ambiguous vtable: ' + name)
        methods = {}
        # Serialization and debug-print slots only. Slot zero deletion and
        # external actor/order ownership implementations are not traversed.
        for slot in (1, 2, 3, 4, 5):
            address = word(tables[0] + slot * 4)
            instructions = []
            for ins in decoder.disasm(image.read(address, 512), address):
                instructions.append(ins)
                if ins.mnemonic == 'ret':
                    break
            if not instructions or instructions[-1].mnemonic != 'ret':
                raise ValueError('Bounded method lacks return')
            size = instructions[-1].address + instructions[-1].size - address
            methods[str(slot)] = {
                'address': hex(address), 'size': size,
                'sha256': hashlib.sha256(image.read(address, size)).hexdigest(),
                'listing': [f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in instructions],
            }
        if name in ('GS_ResearchOrder', 'GS_BaseDelayedOrder'):
            address = word(tables[0] + 6 * 4)
            # Complete multi-return body, unlike the straight-line serializer
            # wrappers above. Keep internal branches and all terminal paths.
            data = image.read(address, 0x5e)
            instructions = list(decoder.disasm(data, address))
            if sum(i.size for i in instructions) != len(data) or instructions[-1].mnemonic != 'ret':
                raise ValueError('Unexpected delayed-order processor extent')
            methods['6'] = {'address': hex(address), 'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest(),
                'listing': [f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in instructions]}
        result['classes'][name] = {'table': hex(tables[0]), 'methods': methods}
    return result


if __name__ == '__main__':
    print(json.dumps({name: inspect(path, digest) for name, path, digest in PROFILES}, indent=2))
