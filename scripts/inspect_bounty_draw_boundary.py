"""Offline GPL draw-wrapper audit. No native execution or callee traversal.

The named registration identifies each build independently. This does not
certify reward-flag rendering, persistence, or a full-transparency setting.
"""
import hashlib
import json
import struct
from pathlib import Path
import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT.parent / 'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
PROFILES = (
    ('public', Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/MajestyHD.exe'),
     '255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4'),
    ('beta2', FIXTURES/'beta2/MajestyHD.exe',
     '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82'),
    ('gog', FIXTURES/'gog-pristine/MajestyHD.exe',
     '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792'),
)

def audit(path, expected, symbol='SetDrawEffects'):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, 'Unsupported executable'
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    symbol_bytes = symbol.encode('ascii') + b'\0'
    assert raw.count(symbol_bytes) == 1
    name = base + pe.get_rva_from_offset(raw.index(symbol_bytes))
    needle = b'\x68' + struct.pack('<I', name)
    assert raw.count(needle) == 1, 'Ambiguous registration name reference'
    offset = raw.index(needle)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    registration = list(decoder.disasm(raw[offset:offset+64], base+pe.get_rva_from_offset(offset)))
    handlers = [int(i.op_str, 16) for i in registration if i.mnemonic == 'push'
                and i.op_str.startswith('0x') and int(i.op_str, 16) != name]
    assert len(handlers) == 1, 'Ambiguous registered handler'
    handler = handlers[0]
    instructions = []
    for i in decoder.disasm(pe.get_data(handler-base, 512), handler):
        instructions.append(i)
        if i.mnemonic == 'ret':
            break
    assert instructions[-1].mnemonic == 'ret', 'Unbounded wrapper'
    end = instructions[-1].address + instructions[-1].size
    for i in instructions:
        if i.mnemonic.startswith('j'):
            assert handler <= int(i.op_str, 16) < end, 'External branch'
    pairs = [(i.mnemonic, i.op_str) for i in instructions]
    if symbol == 'SetDrawEffects':
        assert ('cmp', 'ecx, 0xa') in pairs
        assert ('test', 'ecx, ecx') in pairs
        assert ('or', 'ecx, 5') in pairs
        assert ('mov', 'edx, dword ptr [edx + 0x54]') in pairs
        conclusion = 'GPL wrapper accepts transparency only for 0 < n < 10 and forwards a draw descriptor through slot54. No full-hidden reward-flag or save/load contract established; callees remain opaque.'
    else:
        assert symbol == 'SetSpellUnitTimeout'
        assert ('push', 'esi') in pairs and ('push', 'eax') in pairs
        conclusion = 'GPL wrapper reads agent and integer, resolves the unit, and forwards it with the duration when nonnull. The completion/removal callback is not certified by this wrapper.'
    body = pe.get_data(handler-base, end-handler)
    return dict(executable=str(path), executable_sha256=expected,
                handler=hex(handler), body_sha256=hashlib.sha256(body).hexdigest(),
                body_bytes=len(body), listing=[f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in instructions],
                conclusion=conclusion)

if __name__ == '__main__':
    results = {name: {symbol: audit(path, digest, symbol)
                     for symbol in ('SetDrawEffects', 'SetSpellUnitTimeout')}
               for name, path, digest in PROFILES}
    output = ROOT/'private/bounty-action-v1/draw-wrapper-three-profile-evidence.json'
    output.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(output)
