"""Read-only comparison of the BCD loader across the three supported builds.

Requires the workspace's shared pefile/capstone tooling, not runtime dependencies.
Usage: audit_bcd_ownership.py <beta2-exe> <public-exe> <gog-exe>
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import capstone
import pefile


RANGES = (
    (0x55d740, 0x55d8a6, 'file_loader'),
    (0x618f50, 0x618f81, 'block_begin'),
    (0x618f90, 0x618fb8, 'block_end'),
    (0x5729e0, 0x572b36, 'instruction_table'),
    (0x5900b0, 0x5904cf, 'symbol_tables'),
    (0x580430, 0x58067c, 'data_table'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('beta2', 'public', 'gog'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    images, hashes = {}, {}
    for name, path in vars(args).items():
        raw = path.read_bytes()
        pe = pefile.PE(data=raw)
        if pe.OPTIONAL_HEADER.ImageBase != 0x400000:
            raise ValueError(f'{name}: unexpected image base')
        images[name] = pe.get_memory_mapped_image()
        hashes[name] = hashlib.sha256(raw).hexdigest()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    ranges = []
    for start, end, label in RANGES:
        body = images['beta2'][start - 0x400000:end - 0x400000]
        mask = set()
        for instruction in md.disasm(body, start):
            branch = instruction.group(capstone.CS_GRP_JUMP) or instruction.group(capstone.CS_GRP_CALL)
            absolute = any(o.type == capstone.x86.X86_OP_IMM and o.imm >= 0x400000
                           for o in instruction.operands)
            if branch or absolute:
                offset = instruction.address - start + instruction.imm_offset
                mask.update(range(offset, offset + instruction.imm_size))
            if any(o.type == capstone.x86.X86_OP_MEM and o.mem.disp >= 0x400000
                   for o in instruction.operands):
                offset = instruction.address - start + instruction.disp_offset
                mask.update(range(offset, offset + instruction.disp_size))
        pattern = b''.join(b'.' if i in mask else re.escape(bytes([v])) for i, v in enumerate(body))
        row = dict(label=label, size=end - start)
        for name, data in images.items():
            matches = list(re.finditer(pattern, data, re.S))
            if len(matches) != 1:
                raise ValueError(f'{name}: {label} has {len(matches)} matches, expected one')
            row[name] = hex(0x400000 + matches[0].start())
        ranges.append(row)
    addresses = {row['label']: row for row in ranges}
    for name, image in images.items():
        start = int(addresses['file_loader'][name], 16)
        instructions = md.disasm(image[start - 0x400000:start - 0x400000 + RANGES[0][1] - RANGES[0][0]], start)
        calls = [i.operands[0].imm for i in instructions if i.mnemonic == 'call'
                 and i.operands[0].type == capstone.x86.X86_OP_IMM]
        expected = [int(addresses[k][name], 16) for k in
                    ('block_begin', 'instruction_table', 'symbol_tables', 'data_table', 'block_end')]
        if [x for x in calls if x in expected] != expected:
            raise ValueError(f'{name}: loader dispatch sequence differs')
    print(json.dumps(dict(sha256=hashes, ranges=ranges), indent=2))


if __name__ == '__main__':
    main()
