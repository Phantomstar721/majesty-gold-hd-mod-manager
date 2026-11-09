"""Read-only PE evidence for Dawnfall's stock lifecycle; never installs hooks.

String references are discovery candidates, not certified callable addresses.
Explicit code windows retain executable identity, bytes and disassembly for
review. Use the workspace's existing Capstone environment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import capstone


class Image:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        pe = struct.unpack_from('<I', self.data, 60)[0]
        if self.data[pe:pe+4] != b'PE\0\0':
            raise ValueError('not a PE')
        optional = pe + 24
        if struct.unpack_from('<H', self.data, optional)[0] != 0x10b:
            raise ValueError('expected PE32')
        self.base = struct.unpack_from('<I', self.data, optional+28)[0]
        count = struct.unpack_from('<H', self.data, pe+6)[0]
        size = struct.unpack_from('<H', self.data, pe+20)[0]
        self.sections = []
        for index in range(count):
            offset = optional+size+40*index
            virtual_size, rva, raw_size, raw = struct.unpack_from('<4I', self.data, offset+8)
            flags = struct.unpack_from('<I', self.data, offset+36)[0]
            self.sections.append((self.base+rva, min(virtual_size, raw_size), raw, flags))

    def read(self, va, count):
        for start, size, raw, _ in self.sections:
            if start <= va and va+count <= start+size:
                return self.data[raw+va-start:raw+va-start+count]
        raise ValueError(f'non-file-backed range {va:#x}+{count:#x}')

    def find(self, needle, executable=False):
        hits = []
        for start, size, raw, flags in self.sections:
            if executable and not flags & 0x20000000:
                continue
            blob = self.data[raw:raw+size]
            at = blob.find(needle)
            while at >= 0:
                hits.append(start+at)
                at = blob.find(needle, at+1)
        return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--window', action='append', default=[], help='VA:byte-count (hex accepted)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    image = Image(args.image)
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    result = {'image': str(image.path.resolve()),
              'sha256': hashlib.sha256(image.data).hexdigest(),
              'base': hex(image.base), 'native_execution': False,
              'string_reference_candidates': {}, 'windows': []}
    for name in ('FadeIn', 'FadeOut', 'TeleportToUnit', 'SetSpellUnitTimeout'):
        locations = image.find(name.encode()+b'\0')
        result['string_reference_candidates'][name] = [
            {'string': hex(va), 'push_references': [hex(ref) for ref in image.find(b'\x68'+struct.pack('<I', va), True)]}
            for va in locations]
    for entry in args.window:
        start, size = (int(part, 0) for part in entry.split(':'))
        if not 1 <= size <= 16384:
            raise ValueError('bounded windows require 1..16384 bytes')
        blob = image.read(start, size)
        result['windows'].append({'va': hex(start), 'bytes': blob.hex(),
                                  'sha256': hashlib.sha256(blob).hexdigest(),
                                  'instructions': [f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in disassembler.disasm(blob, start)]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('refusing to overwrite existing evidence')
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result['string_reference_candidates']))


if __name__ == '__main__':
    main()
