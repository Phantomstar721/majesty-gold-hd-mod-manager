"""Reuse the shipped list presenter's guarded text/name/image API boundaries.

Whole normal method correspondence is checked at the explicit three-build
addresses. This does not follow their callees or import exceptional cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, quest_board_profiles
from verify_panel_engine_constructors import pattern
from verify_panel_engine_data_clients import decode


def verify(fixtures):
    import pefile
    identities = json.loads((ROOT / 'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    profiles = quest_board_profiles()
    roots = {'gameString': ('rowSummaryTextResolver', 0x424020, 41),
             'unitName': ('rowNameFormatter', 0x4422f0, 351),
             'imageDraw': ('rowStatusDraw', 0x672850, 34)}
    images = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != identities[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed UI caller fixture: ' + branch)
        images[branch] = pefile.PE(data=raw)
    output = {}
    for branch, pe in images.items():
        methods = {}
        for name, (field, public_va, size) in roots.items():
            address = 0x400000 + profiles[branch][field]
            original = images['public'].get_data(public_va - 0x400000, size)
            body = pe.get_data(address - 0x400000, size)
            if not pattern(original, public_va).fullmatch(body):
                raise ValueError('Whole UI method correspondence changed: ' + name + '/' + branch)
            decode(body, address)
            methods[name] = {'va': address, 'size': size, 'sha256': hashlib.sha256(body).hexdigest(),
                             'profileField': field}
        name_call = 0x400000 + profiles[branch]['rowNameFormatterCall']
        # Right-to-left cdecl args: mode0, selected unit EDI, address of local
        # native string. This is the SDK's UnitName_t, not a thiscall method.
        frame = pe.get_data(name_call - 0x400000 - 8, 13)
        if frame[:8] != bytes.fromhex('6a008d4c243c5751') or frame[8] != 0xe8:
            raise ValueError('Stock unit-name argument frame changed')
        target = name_call + 5 + struct.unpack_from('<i', frame, 9)[0]
        if target != methods['unitName']['va']:
            raise ValueError('Unit-name caller changed its provider')
        output[branch] = {'fixtureSha256': identities[branch]['fixtureSha256'],
                          'methods': methods, 'unitNameCallVA': name_call, 'unitNameCallBytes': frame.hex()}
    return {'schema': 1, 'contract': 'panel-engine.list-presenter-apis.v1',
        'source': 'runtime/MajestyModManagerRuntime.cpp:QuestBoardBuildProfile; SDK GAME_STRING/UNIT_NAME/ART_DRAW',
        'limits': 'Complete normal methods/existing typed presenter API and unit-name frame only; downstream/exception implementations stay opaque.',
        'profiles': output}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
