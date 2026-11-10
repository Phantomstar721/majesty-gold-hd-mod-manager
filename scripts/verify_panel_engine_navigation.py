"""Verify the stock list-panel Back route on every supported build.

The route is selected through its verified RTTI class/command slot. Only this
owned command block is compared; no whole-function size is borrowed from a
different version and no target implementation is expanded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, manager_profiles


def call(body, address, offset, expected=None):
    if body[offset] != 0xe8:
        raise ValueError('Back route no longer uses a stock direct call')
    target = address + offset + 5 + struct.unpack_from('<i', body, offset + 1)[0]
    if expected is not None and target != expected:
        raise ValueError('Back route stock provider changed')
    return target


def verify(fixtures):
    import pefile
    tables = json.loads((ROOT / 'profiles/panel-engine/vtables.json').read_bytes())['profiles']
    owners = manager_profiles()
    result = {}
    template = None
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != tables[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed navigation fixture: ' + branch)
        pe = pefile.PE(data=raw)
        handler = tables[branch]['classes']['unitList']['slots'][3]
        # Follow the explicit 0x1f4d Back comparison, not a nearby list-unit
        # activation arm. That neighboring arm also writes UI+48, while Back
        # deliberately enters the shared tail after that write.
        front = pe.get_data(handler - 0x400000, 0x23)
        dispatch = None
        if branch == 'public':
            if front[0x12:0x17] != bytes.fromhex('3d4d1f0000') or front[0x1d:0x1f] != b'\x0f\x84':
                raise ValueError('Public list Back control route changed')
            back = handler + 0x23 + struct.unpack_from('<i', front, 0x1f)[0]
        else:
            if front[0x12:0x1d][:7] != bytes.fromhex('3d401f00000f8f'):
                raise ValueError('Beta/GOG list control dispatch changed')
            dispatch_address = handler + 0x1d + struct.unpack_from('<i', front, 0x19)[0]
            dispatch = pe.get_data(dispatch_address - 0x400000, 15)
            # For Back=1f4d, the signed >1f40 arm subtracts1f41 and then12.
            # The second equality is exactly the Back branch. This distinction
            # is present in beta/GOG; Public uses the direct equality above.
            if dispatch != bytes.fromhex('8bc881e9411f0000741c83e90c7410'):
                raise ValueError('Beta/GOG Back equality route changed')
            back = dispatch_address + 15 + struct.unpack_from('<b', dispatch, 14)[0]
        stub = pe.get_data(back - 0x400000, 7)
        if stub[:3] != bytes.fromhex('6a00e9'):
            raise ValueError('Stock Back no longer supplies a null opener target')
        address = back + 7 + struct.unpack_from('<i', stub, 3)[0]
        body = pe.get_data(address - 0x400000, 34)
        context = 0x400000 + int(owners[branch]['uiManagerRva'], 0)
        call(front, handler, 7, 0x400000 + int(owners[branch]['getPanelContextRva'], 0))
        calls = (1, 8, 16)
        call(body, address, 1, context)
        window_id = call(body, address, 8)
        opener = call(body, address, 16, 0x400000 + int(owners[branch]['openDialogRva'], 0))
        masked = bytearray(body)
        for offset in calls:
            masked[offset + 1:offset + 5] = b'\0' * 4
        if template is None:
            template = bytes(masked)
        if bytes(masked) != template:
            raise ValueError('Stock Back control/context/return ordering differs: ' + branch)
        if body[-3:] != bytes.fromhex('c20400') or b'\xbb\x01\x00\x00\x00' not in body or body[-6:-4] != bytes.fromhex('8bc3'):
            raise ValueError('Back no longer returns its stock close result')
        if branch == 'public' and (window_id != 0x42a1f0 or opener != 0x4b03f0):
            raise ValueError('SDK Public navigation anchor changed')
        result[branch] = {'fixtureSha256': tables[branch]['fixtureSha256'],
            'commandHandlerVA': handler, 'frontBytes': front.hex(), 'backArmVA': back,
            'backArmBytes': stub.hex(), 'backBlockVA': address, 'backBlockBytes': body.hex(),
            'extendedBackDispatch': dispatch.hex() if dispatch else None,
            'uiContextVA': context, 'windowIdVA': window_id, 'openSubwindowVA': opener}
    return {'schema': 1, 'contract': 'panel-engine.stock-back-route.v1',
        'source': 'SDK go_back and actual Base_UnitListController command route',
        'limits': 'Verified owned caller block and opaque callee roles; not full handler or target implementation coverage.',
        'profiles': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
