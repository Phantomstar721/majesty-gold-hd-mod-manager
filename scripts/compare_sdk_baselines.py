"""Read-only structural comparison; does not execute or rewrite game scripts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def compare(game, codec_path):
    spec = importlib.util.spec_from_file_location('wire', codec_path)
    wire = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wire)
    paths = ('Data/Bytecode.bcd', 'DataMX/MX_Compatibility.bcd',
             'DataMX/MX_Build.bcd', 'DataMX/MX_Data.bcd',
             'DataMX/MX_Decision.bcd', 'DataMX/MX_Task.bcd')
    name = lambda value: ''.join(map(chr, value['units']))
    def indexed(entries):
        result = {name(e['name']): e['value'] for e in entries}
        assert len(result) == len(entries), 'duplicate entry cannot be collapsed'
        return result
    rows = []
    for relative in paths:
        blobs = [(root / relative).read_bytes() for root in (game, game/'SDK/OriginalQuests')]
        decoded = [wire.decode_package(b) for b in blobs]
        assert all(wire.encode_package(d) == b for d, b in zip(decoded, blobs))
        tapes = [indexed(d['tapes']['entries']) for d in decoded]
        # Debug source/line records are distinct from actual instruction operands.
        def instructions(tape):
            return [(op['operands'], op['metadata']['opcode'], op['metadata']['word'],
                     op['metadata']['itemBits']) for op in tape['operations']]
        changed = [n for n in sorted(tapes[0].keys() | tapes[1].keys())
                   if n not in tapes[0] or n not in tapes[1] or
                   instructions(tapes[0][n]) != instructions(tapes[1][n])]
        symbols = [[indexed(g) for g in d['symbols']['groups']] for d in decoded]
        rows.append(dict(path=relative, hashes=[hashlib.sha256(b).hexdigest() for b in blobs],
                         changed_instruction_tapes=changed,
                         symbols_equal=symbols[0] == symbols[1],
                         datasets_equal=decoded[0]['datasets'] == decoded[1]['datasets']))
    return rows


if __name__ == '__main__':
    print(json.dumps(compare(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
