"""Verify the SDK hook call sites using existing three-build owner profiles.

Reads disk fixtures only. Native factory, registration and continuation bodies
remain opaque. This report establishes hook placement, not module readiness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

from panel_engine_profile_sources import ROOT, BRANCHES, manager_profiles, map_query_profiles, byte_array

sys.path.insert(0, str(ROOT / 'src'))
from majesty_cam.manager.qol_service import detect_majesty_branch


def transfer(pe, rva, opcode, target=None):
    code = pe.get_data(rva, 5)
    if len(code) != 5 or code[0] != opcode:
        raise ValueError("Unexpected native transfer at RVA " + hex(rva))
    destination = pe.OPTIONAL_HEADER.ImageBase + rva + 5 + struct.unpack_from('<i', code, 1)[0]
    if target is not None and destination != target:
        raise ValueError("Native transfer target differs at RVA " + hex(rva))
    return {'rva': rva, 'bytes': code.hex(), 'targetVA': destination}


def verify(fixtures):
    import pefile
    owners, registrations = manager_profiles(), map_query_profiles()
    rows = {}
    for branch in BRANCHES:
        path = fixtures[branch]
        detected = detect_majesty_branch(path)
        if detected is None or not (detected.key == branch or branch == 'gog' and detected.key.startswith('gog')):
            raise ValueError("Unsupported fixture identity for " + branch)
        raw = path.read_bytes()
        pe = pefile.PE(data=raw)
        base = pe.OPTIONAL_HEADER.ImageBase
        if base != 0x400000 or pe.FILE_HEADER.Machine != 0x14c:
            raise ValueError("Panel SDK requires the verified x86 image layout")
        owner = owners[branch]
        result_rva = int(owner['secondaryControllerResultRva'], 0)
        result_guard = byte_array(owner['expectedResultSite'])
        factory_rva = int(owner['dialogFactoryRva'], 0)
        factory_guard = byte_array(owner['expectedFactoryEntry'])
        if pe.get_data(result_rva, len(result_guard)) != result_guard:
            raise ValueError("Post-factory owner site differs: " + branch)
        if pe.get_data(factory_rva, len(factory_guard)) != factory_guard:
            raise ValueError("Factory entry owner guard differs: " + branch)
        window = transfer(pe, result_rva - 5, 0xe8, base + factory_rva)
        registration = registrations[branch]
        register_call = transfer(pe, registration['registrationCall'], 0xe8, base + registration['registration'])
        action = transfer(pe, registration['registrationCall'] + 5, 0xe9)
        # The source's Public hook/continuation is an independent anchor, not
        # evidence for translating the other builds by an address delta.
        if branch == 'public' and (window['rva'] != 0x25945 or action['rva'] != 0x198eec or action['targetVA'] != 0x434060):
            raise ValueError("Public SDK hook anchors changed")
        continuation_rva = action['targetVA'] - base
        section = pe.get_section_by_rva(continuation_rva)
        if section is None or not section.Characteristics & 0x20000000:
            raise ValueError("Stock continuation is not executable")
        rows[branch] = {
            'fixtureSha256': hashlib.sha256(raw).hexdigest(),
            'windowFactoryCall': window,
            'factoryOwnerEntry': {'rva': factory_rva, 'bytes': factory_guard.hex()},
            'postFactoryOwnerSite': {'rva': result_rva, 'bytes': result_guard.hex()},
            'stockRegistrationCall': register_call,
            'scriptRegistrationTail': action,
            'registerFunctionRva': registration['registerFunction'],
            'boardExtentsRva': registration['boardExtents'],
        }
    return {'schema': 1, 'contract': 'panel-engine.hook-sites.v1',
        'sources': ['runtime/MajestyModManagerRuntime.cpp:MajestyBuildProfile',
                    'runtime/MapQueryRuntime.cpp:Profile',
                    'SDK we_engine.cpp:WE_Factory; sf_functions.cpp:SF_Hook'],
        'limits': 'Hook bytes and targets only; no native callee/lifecycle or engine admission claim.',
        'profiles': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({name: Path(os.environ['MAJESTY_' + name.upper() + '_EXE']) for name in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
