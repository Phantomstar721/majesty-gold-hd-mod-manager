"""Reuse the existing stock agent-reference-to-unit client on all builds.

Only the already used 43-byte resolver client is read. Registry, association,
actor construction/cleanup and callback implementations remain opaque. This
proves the deleted-byte guard and outgoing API boundaries, not full lifetime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, quest_board_profiles, map_query_profiles


def verify(fixtures):
    import pefile
    identities = json.loads((ROOT / 'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    resolvers = quest_board_profiles()
    roots = map_query_profiles()
    result = {}
    template = None
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != identities[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed resolver fixture: ' + branch)
        pe = pefile.PE(data=raw)
        address = 0x400000 + resolvers[branch]['liveAgentResolver']
        body = pe.get_data(address - 0x400000, 43)
        targets = []
        masked = bytearray(body)
        for offset, opcode in ((7, 0xe8), (14, 0xe8), (35, 0xe9)):
            if body[offset] != opcode:
                raise ValueError('Stock resolver outgoing request changed')
            targets.append(address + offset + 5 + struct.unpack_from('<i', body, offset + 1)[0])
            masked[offset + 1:offset + 5] = b'\0' * 4
        if targets[0] != 0x400000 + roots[branch]['engine']:
            raise ValueError('Stock resolver changed its GPL owner provider')
        if branch == 'public' and targets != [0x55eef0, 0x55e8e0, 0x55f2c0]:
            raise ValueError('Public source resolver anchors changed')
        if body[0x17:0x23] != bytes.fromhex('85c0740d8078380075078bc8'):
            raise ValueError('Null/deleted check no longer precedes unit association')
        if body[-3:] != bytes.fromhex('33c0c3'):
            raise ValueError('Stock resolver no longer returns null on rejection')
        if template is None:
            template = bytes(masked)
        if bytes(masked) != template:
            raise ValueError('Complete stock resolver client differs: ' + branch)
        result[branch] = {'fixtureSha256': identities[branch]['fixtureSha256'],
            'resolveReferenceVA': address, 'size': 43, 'sha256': hashlib.sha256(body).hexdigest(),
            'managerVA': targets[0], 'lookupAgentVA': targets[1], 'associatedUnitVA': targets[2],
            'deletedByteOffset': 0x38}
    return {'schema': 1, 'contract': 'panel-engine.stock-agent-resolution-client.v1',
        'sources': ['runtime/MajestyModManagerRuntime.cpp:QuestBoardBuildProfile.liveAgentResolver',
                    'runtime/MapQueryRuntime.cpp:Profile.engine', 'docs/branch-reader-implementation-status.md:bounded Public lookup'],
        'limits': 'Existing resolver caller only: null/deleted guard and opaque lookup/association boundaries; no full actor lifetime, registry or cleanup proof.',
        'profiles': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
