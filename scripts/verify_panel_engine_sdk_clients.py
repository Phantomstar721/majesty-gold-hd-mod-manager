"""Map SDK helpers through stock argument/return and recruitment clients.

No helper implementation is followed. The bounded gameplay clients already
cited by the supplied SDK are matched against complete instruction spans with
known typed API targets as anchors. This does not certify actor birth/cleanup,
VM internals, exception handling or a full originating gameplay function.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, paid_source_target_profiles, quest_board_profiles, manager_profiles


def instructions(body, address):
    import capstone
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    result = tuple(decoder.disasm(body, address))
    if sum(item.size for item in result) != len(body):
        raise ValueError('SDK client span ends inside an instruction')
    return result


def pattern(body, address):
    import capstone
    masks = set()
    for item in instructions(body, address):
        offset = item.address - address
        if item.group(capstone.CS_GRP_CALL) and item.operands[0].type == capstone.x86.X86_OP_IMM:
            masks.update(range(offset + item.imm_offset, offset + item.imm_offset + item.imm_size))
        for operand in item.operands:
            if operand.type == capstone.x86.X86_OP_MEM and 0x400000 <= operand.mem.disp < 0x900000:
                masks.update(range(offset + item.disp_offset, offset + item.disp_offset + item.disp_size))
            if operand.type == capstone.x86.X86_OP_IMM and not (item.group(capstone.CS_GRP_CALL) or item.group(capstone.CS_GRP_JUMP)) and 0x400000 <= operand.imm < 0x900000:
                masks.update(range(offset + item.imm_offset, offset + item.imm_offset + item.imm_size))
    return re.compile(b''.join(b'[\\s\\S]' if index in masks else re.escape(bytes([value])) for index, value in enumerate(body)))


def target(body, address, offset):
    if body[offset] != 0xe8:
        raise ValueError('SDK client direct-call opcode changed')
    return address + offset + 5 + struct.unpack_from('<i', body, offset + 1)[0]


def matches(pe, original, address, anchors):
    template = pattern(original, address)
    result = []
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        for match in template.finditer(section.get_data()):
            va = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start()
            body = match.group()
            if all(target(body, va, offset) == expected for offset, expected in anchors.items()):
                instructions(body, va)
                result.append((va, body))
    if len(result) != 1:
        raise ValueError('Stock SDK client match is ambiguous/missing: ' + hex(address) + ' count=' + str(len(result)))
    return result[0]


def verify(fixtures):
    import pefile
    identities = json.loads((ROOT / 'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    q, p, m = quest_board_profiles(), paid_source_target_profiles(), manager_profiles()
    images = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != identities[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed SDK client fixture: ' + branch)
        images[branch] = pefile.PE(data=raw)
    # Only the already-cited argument-reading span and post-creation result
    # marshalling. No actor creation branch or helper body is expanded.
    roots = {'stringArgument': (0x433415, 0x4334c3 - 0x433415),
             'agentReturn': (0x432fb4, 0x433010 - 0x432fb4),
             'recruitment': (0x4967a0, 262),
             'buildingInput': (0x433eba, 0x433fbe - 0x433eba),
             'buildingOrderInput': (0x4c3a00, 0x37)}
    originals = {name: images['public'].get_data(address - 0x400000, size) for name, (address, size) in roots.items()}
    # Check Public source anchors before deriving any other build's targets.
    assert target(originals['stringArgument'], 0x433415, 0xa9) == 0x562c10
    assert target(originals['agentReturn'], 0x432fb4, 0x3a) == 0x553fe0
    assert target(originals['recruitment'], 0x4967a0, 0x73) == 0x4201a0
    assert target(originals['recruitment'], 0x4967a0, 0x90) == 0x663da0
    assert target(originals['recruitment'], 0x4967a0, 0xe2) == 0x41fc30
    output = {}
    for branch, pe in images.items():
        anchors = {
            'stringArgument': {0x26: 0x400000 + q[branch]['liveAgentResolver']},
            'agentReturn': {4: 0x400000 + q[branch]['resultAt'],
                            0x13: 0x400000 + p[branch]['component_lookup'],
                            0x1d: 0x400000 + p[branch]['reference_ctor'],
                            0x57: 0x400000 + p[branch]['reference_destroy']},
            'recruitment': {0x29: 0x400000 + int(m[branch]['getPanelContextRva'], 0),
                            0x5d: 0x400000 + p[branch]['allocate']},
        }
        spans = {}
        for name, (public_va, _) in roots.items():
            if name == 'buildingInput':
                recruitment = spans['recruitment']
                anchors[name] = {0x7a: recruitment['listConstructorVA'],
                                 0xb5: recruitment['listCopyVA']}
            elif name == 'buildingOrderInput':
                anchors[name] = {0x32: spans['buildingInput']['placeBuildingVA']}
            address, body = matches(pe, originals[name], public_va, anchors[name])
            spans[name] = {'va': address, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                'knownCallAnchors': {str(offset): expected for offset, expected in anchors[name].items()}}
            if name == 'stringArgument':
                spans[name]['textGetterVA'] = target(body, address, 0xa9)
            elif name == 'agentReturn':
                spans[name]['assignReferenceVA'] = target(body, address, 0x3a)
                # This exact call/cleanup/null-result suffix directly precedes
                # the already anchored result marshalling. Keep the native
                # flag API opaque; no creation/economics implementation read.
                prefix = pe.get_data(address - 0x400000 - 14, 14)
                if prefix[5:] != bytes.fromhex('8bf883c42485ff745c'):
                    raise ValueError('Stock flag caller/result ordering changed')
                spans[name]['flagMakeVA'] = target(prefix, address - 14, 0)
                spans[name]['flagCallBytes'] = prefix.hex()
            elif name == 'recruitment':
                spans[name]['listConstructorVA'] = target(body, address, 0x73)
                spans[name]['listCopyVA'] = target(body, address, 0x90)
                spans[name]['listDestructorVA'] = target(body, address, 0xe2)
            elif name == 'buildingInput':
                spans[name]['placeSettingsVA'] = target(body, address, 0)
                spans[name]['listSetVA'] = target(body, address, 0x95)
                if target(body, address, 0xa6) != spans[name]['listSetVA']:
                    raise ValueError('Stock input attributes use different setters')
                spans[name]['placeBuildingVA'] = target(body, address, 0xff)
            elif name == 'buildingOrderInput':
                spans[name]['placeBuildingVA'] = target(body, address, 0x32)
        output[branch] = {'fixtureSha256': identities[branch]['fixtureSha256'], 'clients': spans}
    return {'schema': 1, 'contract': 'panel-engine.sdk-typed-callers.v1',
        'sources': ['SDK sf_functions.cpp arg_str/return_unit/build_at citations',
                    'SDK we_engine.cpp GUILD_RECRUIT', 'runtime/PaidSourceTargetProfiles.h',
                    'runtime/MajestyModManagerRuntime.cpp:QuestBoardBuildProfile/MajestyBuildProfile'],
        'limits': 'Bounded client correspondence and opaque API targets only; no actor, registry, VM, allocator or exception implementation expansion.',
        'profiles': output}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
