"""Close the remaining ordinary UI API boundaries used by the source SDK.

Uses complete normal methods, the actual stock row-rendering client and
byte-identical position-independent helper aliases. No rendering driver,
exception, actor or shared registry implementation is followed. Alias admission
is whole-machine-code equivalence, never a choice between plausible offsets.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, manager_profiles, quest_board_profiles, freestyle_profiles, paid_source_target_profiles
from verify_panel_engine_sdk_clients import pattern, matches, target, instructions
from verify_panel_engine_data_clients import decode, import_identity, code_references


def row(address, body):
    return {'va': address, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def all_matches(pe, original, public_va):
    template = pattern(original, public_va)
    return [(pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start(), match.group())
            for section in pe.sections if section.Characteristics & 0x20000000
            for match in template.finditer(section.get_data())]


def verify(fixtures):
    import capstone
    import pefile
    q, m, f, p = quest_board_profiles(), manager_profiles(), freestyle_profiles(), paid_source_target_profiles()
    ctor = json.loads((ROOT / 'profiles/panel-engine/constructors.json').read_bytes())['profiles']
    navigation = json.loads((ROOT / 'profiles/panel-engine/navigation.json').read_bytes())['profiles']
    sdk = json.loads((ROOT / 'profiles/panel-engine/sdk-clients.json').read_bytes())['profiles']
    images = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != qid(ctor, branch):
            raise ValueError('Unsupported/changed UI provider fixture: ' + branch)
        images[branch] = pefile.PE(data=raw)
    public = images['public']
    normal = {'SHOW_MSG': (0x46ac00, 222, 0), 'LIST_BUTTONS': (0x498100, 100, 0),
              'WATCH': (0x467650, 27, 8), 'FOLLOW': (0x454dc0, 40, 8),
              'VEC_INSERT': (0x49d9c0, 331, 16), 'TB_CTOR': (0x66e700, 175, 0),
              'TB_TEXT': (0x66fb00, 232, 4), 'TB_DTOR': (0x66f190, 164, 0),
              'FRAME_TALL': (0x4af420, 123, 4)}
    originals = {name: public.get_data(address - 0x400000, size) for name, (address, size, _) in normal.items()}
    draw_address, draw_size = 0x6baabd, 0x6babdc - 0x6baabd
    draw_original = public.get_data(draw_address - 0x400000, draw_size)
    output = {}
    imports_expected = None
    for branch, pe in images.items():
        providers, evidence = {}, {}
        draw_va, draw = matches(pe, draw_original, draw_address,
            {0: 0x400000 + q[branch]['rowStatusDraw'],
             0x64: 0x400000 + f[branch]['wrapperAssignRva']})
        evidence['stockRowDraw'] = row(draw_va, draw)
        for name, offset, public_target in (('TB_FONT', 0x64, 0x66c740),
                ('TB_ALPHA', 0xb8, 0x66c780), ('ITEM_COLOUR', 0xc2, 0x65c580),
                ('TB_COLOUR', 0xca, 0x66c770), ('TB_DRAW', 0xe0, 0x66e7b0)):
            if target(draw_original, draw_address, offset) != public_target:
                raise ValueError('Public SDK row-rendering source anchor changed: ' + name)
            address = target(draw, draw_va, offset)
            providers[name] = {'va': address, 'source': 'stockRowDraw', 'callOffset': offset}
        # The SDK's scalar alpha/colour setters and 45-byte font binding are
        # additionally compared at the actual caller-resolved target, not at
        # an arbitrary identical setter elsewhere in the image.
        for name, public_va, size in (('TB_ALPHA', 0x66c780, 10), ('TB_COLOUR', 0x66c770, 10),
                                      ('TB_FONT', 0x66c740, 45), ('ITEM_COLOUR', 0x65c580, 131)):
            address = providers[name]['va']
            original = public.get_data(public_va - 0x400000, size)
            body = pe.get_data(address - 0x400000, size)
            if not pattern(original, public_va).fullmatch(body):
                raise ValueError('Caller-bound UI method changed: ' + name + '/' + branch)
            decode(body, address)
            providers[name].update(row(address, body))
        basic = ctor[branch]['constructors']['basicBuilding']['va']
        basic_body = pe.get_data(basic - 0x400000, 138)
        watch_target = target(basic_body, basic, 0x68)
        anchors = {'SHOW_MSG': {0x23: 0x400000 + int(m[branch]['uiManagerRva'], 0),
                               0x75: 0x400000 + int(m[branch]['streamControlLookupRva'], 0),
                               0x96: 0x400000 + q[branch]['stringDestructor']},
                   'WATCH': {0x10: watch_target}}
        import_rows = []
        imports = {item.address for library in pe.DIRECTORY_ENTRY_IMPORT for item in library.imports}
        for name, (public_va, _, purge) in normal.items():
            va, body = matches(pe, originals[name], public_va, anchors.get(name, {}))
            decode(body, va)
            expected_return = b'\xc2' + struct.pack('<H', purge) if purge else b'\xc3'
            if not body.endswith(expected_return):
                raise ValueError('Native UI API stack contract changed: ' + name)
            providers[name] = {**row(va, body), 'stackBytes': purge, 'source': 'complete normal method correspondence'}
            for kind, _, _, reference in code_references(body, va):
                if kind == 'import':
                    if reference in imports:
                        import_rows.append([name, *import_identity(pe, reference)])
                    else:
                        # These are native caller data operands, not imports.
                        # Keep them qualified and opaque; their values are
                        # never sampled or accepted for looking plausible.
                        providers[name].setdefault('opaqueDataVAs', []).append(reference)
        if imports_expected is None:
            imports_expected = import_rows
        if import_rows != imports_expected:
            raise ValueError('Native UI import roles differ across versions')
        handler = navigation[branch]['commandHandlerVA']
        camera_frame = pe.get_data(handler - 0x400000 + 0x13d, 16)
        if camera_frame[:7] != bytes.fromhex('8b086a01518b0d'):
            raise ValueError('Stock list camera argument frame changed')
        follow = target(camera_frame, handler + 0x13d, 11)
        if follow != providers['FOLLOW']['va']:
            raise ValueError('Camera frame does not use the SDK follow provider')
        evidence['cameraFrame'] = {'va': handler + 0x13d, 'bytes': camera_frame.hex(),
                                   'cameraGlobalVA': struct.unpack_from('<I', camera_frame, 7)[0]}
        # Both native row append helpers are literally identical, contain only
        # virtual calls and use no PC-relative or absolute code/data address.
        # Reuse the shipped HeroAppend API instead of selecting a lookalike.
        append_original = public.get_data(0x65cff0 - 0x400000, 54)
        existing_append = existing_hero_append(branch)
        append_body = pe.get_data(existing_append - 0x400000, 54)
        if append_body != append_original:
            raise ValueError('Native row append alias is not byte-identical')
        for item in instructions(append_body, existing_append):
            if item.group(capstone.CS_GRP_CALL) and item.operands[0].type == capstone.x86.X86_OP_IMM:
                raise ValueError('Row append alias depends on its code position')
        providers['ADD_ROW'] = {**row(existing_append, append_body), 'source': 'verified existing HeroAppend; whole byte-identical alias'}
        # Debug STL instantiations have two equivalent erase entry points. All
        # candidates must be exactly byte-identical within this build, with no
        # external relative transfer or address literal; the only absolute
        # reference must resolve to the same native diagnostic import.
        erase_original = public.get_data(0x49d280 - 0x400000, 139)
        aliases = all_matches(pe, erase_original, 0x49d280)
        if not aliases or any(body != aliases[0][1] for _, body in aliases):
            raise ValueError('Vector erase aliases are not whole-code equivalents')
        alias_imports = []
        for va, body in aliases:
            decode(body, va)
            for item in instructions(body, va):
                if item.group(capstone.CS_GRP_CALL) and item.operands[0].type == capstone.x86.X86_OP_IMM:
                    raise ValueError('Vector erase alias has an external relative call')
            refs = code_references(body, va)
            if any(kind != 'import' for kind, *_ in refs):
                raise ValueError('Vector erase alias has a positional dependency')
            alias_imports.append([list(import_identity(pe, address)) for kind, _, _, address in refs])
        if any(value != alias_imports[0] for value in alias_imports) or alias_imports[0] != [['msvcr90.dll', '_invalid_parameter_noinfo']]:
            raise ValueError('Vector erase alias diagnostic import changed')
        va, body = min(aliases)
        providers['VEC_ERASE'] = {**row(va, body), 'source': 'whole position-independent code equivalence',
                                  'equivalentVAs': sorted(address for address, _ in aliases)}
        # The placement settings object is borrowed synchronously by the
        # stock input client. Compare its full normal getter, keeping its
        # allocator and normal constructor opaque.
        settings = sdk[branch]['clients']['buildingInput']['placeSettingsVA']
        original = public.get_data(0x45c320 - 0x400000, 108)
        settings_body = pe.get_data(settings - 0x400000, 108)
        if not pattern(original, 0x45c320).fullmatch(settings_body) or target(settings_body, settings, 0x2c) != 0x400000 + p[branch]['allocate']:
            raise ValueError('Placement settings borrowed getter changed')
        decode(settings_body, settings)
        providers['PLACE_SETTINGS'] = {**row(settings, settings_body), 'source': 'stock building input client and complete normal getter'}
        output[branch] = {'fixtureSha256': qid(ctor, branch), 'providers': providers, 'clients': evidence, 'imports': import_rows}
    return {'schema': 1, 'contract': 'panel-engine.ordinary-ui-providers.v1',
        'limits': 'Native normal API/client correspondence and explicit equivalent aliases; no driver, actor, exception or shared registry implementation expansion.',
        'sources': ['SDK we_engine.cpp native UI declarations and row-draw citation6BAABD',
                    'Manager QuestBoardBuildProfile, FreestyleCamProfile and FeatureParityProfiles',
                    'research TextLayout_ConstructEmptyDefaultsWithoutParsing_Local/ReleaseMembersNormalEntry/ReplaceParsedNarrow'],
        'profiles': output}


def qid(profiles, branch):
    return profiles[branch]['fixtureSha256']


def existing_hero_append(branch):
    import re
    source = (ROOT / 'runtime/FeatureParityProfiles.h').read_text(encoding='utf8')
    match = re.search(r'\{(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\}, // HeroAppend', source)
    if match is None:
        raise ValueError('Missing existing row append profile')
    beta, public, gog = (int(value, 0) for value in match.groups())
    return 0x400000 + {'public': public, 'beta2': beta, 'gog': gog}[branch]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
