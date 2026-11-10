"""Verify complete SDK data-client bodies without expanding native providers.

The string-copy client reuses allocation/copy/free boundaries from the existing
guarded string constructor/destructor. The raw attribute client uses its exact
existing three-build profile and a connected, data-only tree lookup. Import
identities, complete branches, instruction bytes and every transfer are checked.
No process access, call execution, callee disassembly or address delta is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

from panel_engine_profile_sources import ROOT, BRANCHES, paid_source_target_profiles
sys.path.insert(0, str(ROOT / 'src'))
from majesty_cam.manager.qol_service import detect_majesty_branch


def decode(body, address):
    import capstone
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instructions = tuple(decoder.disasm(body, address))
    if sum(i.size for i in instructions) != len(body) or not instructions[-1].mnemonic.startswith('ret'):
        raise ValueError('Incomplete native own-body extent')
    starts = {i.address for i in instructions}
    for instruction in instructions:
        if instruction.group(capstone.CS_GRP_JUMP):
            if instruction.operands[0].type != capstone.x86.X86_OP_IMM or instruction.operands[0].imm not in starts:
                raise ValueError('Native branch escapes the declared complete own body')
    return instructions


def code_references(body, address):
    import capstone
    result = []
    for instruction in decode(body, address):
        offset = instruction.address - address
        if instruction.group(capstone.CS_GRP_CALL) and instruction.operands[0].type == capstone.x86.X86_OP_IMM:
            result.append(('call', offset + instruction.imm_offset, instruction.imm_size, instruction.operands[0].imm))
        for operand in instruction.operands:
            if operand.type == capstone.x86.X86_OP_MEM and operand.mem.base == 0 and operand.mem.index == 0 and operand.mem.disp >= 0x400000:
                result.append(('import', offset + instruction.disp_offset, instruction.disp_size, operand.mem.disp))
    return result


def masked_pattern(body, address):
    masked = {index for _, offset, size, _ in code_references(body, address) for index in range(offset, offset + size)}
    return re.compile(b''.join(b'[\\s\\S]' if index in masked else re.escape(bytes([value])) for index, value in enumerate(body)))


def import_identity(pe, address):
    for library in pe.DIRECTORY_ENTRY_IMPORT:
        for item in library.imports:
            if item.address == address:
                return library.dll.decode('ascii').lower(), item.name.decode('ascii') if item.name else '#' + str(item.ordinal)
    raise ValueError('Absolute native reference is not a supported import: ' + hex(address))


def match_body(pe, original, public_address, candidates=None):
    pattern = masked_pattern(original, public_address)
    if candidates is None:
        candidates = [pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start()
            for section in pe.sections if section.Characteristics & 0x20000000
            for match in pattern.finditer(section.get_data())]
    matches = []
    for address in candidates:
        body = pe.get_data(address - pe.OPTIONAL_HEADER.ImageBase, len(original))
        if len(body) == len(original) and pattern.fullmatch(body):
            decode(body, address)
            matches.append((address, body))
    if len(matches) != 1:
        raise ValueError('Full-body correspondence is ambiguous/missing: ' + hex(public_address) + ' matches=' + str(len(matches)))
    return matches[0]


def digest_row(address, body):
    return {'va': address, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def verify(fixtures):
    import pefile
    string_profiles = json.loads((ROOT / 'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    paid = paid_source_target_profiles()
    # These are SDK-public roots with independently documented full extents:
    # NativeString_AssignNarrowCopy (127); raw-key payload lookup (109) and its
    # unsigned-key tree client (139). The latter contains no actor lifecycle.
    public_addresses = {'narrowAssign': (0x628240, 127), 'rawAttribute': (0x42d570, 109), 'attributeTree': (0x42d140, 139)}
    images = {}
    for branch in BRANCHES:
        path = fixtures[branch]
        detected = detect_majesty_branch(path)
        if detected is None or not (detected.key == branch or branch == 'gog' and detected.key.startswith('gog')):
            raise ValueError('Unsupported fixture identity: ' + branch)
        # Keep exact fixture provenance consistent with the already admitted
        # complete caller profiles, including the known local Public patches.
        if hashlib.sha256(path.read_bytes()).hexdigest() != string_profiles[branch]['fixtureSha256']:
            raise ValueError('Fixture changed since the provider-client proof: ' + branch)
        images[branch] = pefile.PE(str(path))
    original = {name: images['public'].get_data(address - 0x400000, size) for name, (address, size) in public_addresses.items()}
    result = {}
    # Source-derived constructor/dtor addresses are fixed existing profiles,
    # not candidates. Check complete ctor69/dtor33 against Public, with import
    # and outgoing call roles retained as opaque stock boundaries.
    string_addresses = {'public': (0x627a80, 0x627c30), 'beta2': (0x63a220, 0x63a3d0), 'gog': (0x63c370, 0x63c520)}
    ctor_template = images['public'].get_data(string_addresses['public'][0] - 0x400000, 69)
    dtor_template = images['public'].get_data(string_addresses['public'][1] - 0x400000, 33)
    public_imports = None
    for branch, pe in images.items():
        ctor, destructor = string_addresses[branch]
        _, ctor_body = match_body(pe, ctor_template, string_addresses['public'][0], [ctor])
        _, destructor_body = match_body(pe, dtor_template, string_addresses['public'][1], [destructor])
        ctor_calls = [target for kind, _, _, target in code_references(ctor_body, ctor) if kind == 'call']
        free_imports = [target for kind, _, _, target in code_references(destructor_body, destructor) if kind == 'import']
        if len(ctor_calls) != 2 or len(free_imports) != 1:
            raise ValueError('String client provider shape changed')
        free_identity = import_identity(pe, free_imports[0])
        if free_identity[1] != 'free':
            raise ValueError('String destructor does not request the expected free import')
        assign_address, assign_body = match_body(pe, original['narrowAssign'], public_addresses['narrowAssign'][0])
        assign_refs = code_references(assign_body, assign_address)
        if [target for kind, _, _, target in assign_refs if kind == 'call'] != ctor_calls:
            raise ValueError('Narrow assignment changed allocation/copy provider roles')
        if [target for kind, _, _, target in assign_refs if kind == 'import'] != free_imports:
            raise ValueError('Narrow assignment changed free import')
        attr_address = 0x400000 + paid[branch]['component_lookup']
        _, attr_body = match_body(pe, original['rawAttribute'], public_addresses['rawAttribute'][0], [attr_address])
        attr_refs = code_references(attr_body, attr_address)
        tree_calls = [target for kind, _, _, target in attr_refs if kind == 'call']
        if len(tree_calls) != 1:
            raise ValueError('Raw attribute lookup changed its tree request')
        tree_address, tree_body = match_body(pe, original['attributeTree'], public_addresses['attributeTree'][0], tree_calls)
        attr_imports = [target for kind, _, _, target in attr_refs if kind == 'import']
        tree_imports = [target for kind, _, _, target in code_references(tree_body, tree_address) if kind == 'import']
        if len(attr_imports) != 1 or attr_imports != tree_imports:
            raise ValueError('Attribute iterator diagnostic import differs')
        identities = [free_identity, import_identity(pe, attr_imports[0])]
        if public_imports is None:
            public_imports = identities
        if identities != public_imports:
            raise ValueError('Native import identities differ across these profiles')
        result[branch] = {'fixtureSha256': string_profiles[branch]['fixtureSha256'],
            'narrowAssign': digest_row(assign_address, assign_body),
            'rawAttribute': digest_row(attr_address, attr_body),
            'attributeTree': digest_row(tree_address, tree_body),
            'stringConstructor': digest_row(ctor, ctor_body),
            'stringDestructor': digest_row(destructor, destructor_body),
            'opaqueStringProviders': ctor_calls,
            'imports': [list(identity) for identity in identities]}
    return {'schema': 1, 'contract': 'panel-engine.data-clients.v1',
        'sources': ['SDK we_engine.cpp:YSTRING_SET/ATTR_RAW',
                    'runtime/PaidSourceTargetProfiles.h:component_lookup',
                    'research/docs/native-string-lifecycle.md',
                    'research/docs/smnu-secondary-text.md:63A9E0',
                    'research/functions.tsv:ObjectAttributes_FindPayloadByRawKey_Local/ObjectAttributeTree_FindUnsignedKeyIterator_Local'],
        'limits': 'Complete normal data clients and opaque provider identity; no exceptional, CRT, VM or actor lifecycle implementation proof.',
        'profiles': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({name: Path(os.environ['MAJESTY_' + name.upper() + '_EXE']) for name in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
