"""Bounded ordinary SDK clients for the updated engine, with exact three-build fixtures.

No actor factory, cleanup, callback, registry, VM or exception helper is followed.
Targets remain opaque APIs. This receipt is not a complete native port contract.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct

from panel_engine_profile_sources import ROOT, BRANCHES, map_query_profiles, manager_profiles
from verify_panel_engine_sdk_clients import instructions, pattern, matches, target
from verify_panel_engine_vtables import aligned_references, words, table_data, typename


def named_table(pe, name):
    """Primary RTTI data only; no constructor or native factory traversal."""
    types = []
    for section in pe.sections:
        if section.Characteristics & 0x20000000 or not section.Characteristics & 0x40:
            continue
        for match in re.finditer(re.escape(name.encode('ascii')+b'\0'), section.get_data()):
            va = pe.OPTIONAL_HEADER.ImageBase+section.VirtualAddress+match.start()-8
            if va % 4 == 0 and typename(pe, va) == name:
                types.append(va)
    if len(types) != 1:
        raise ValueError('Missing or ambiguous native type: '+name)
    tables = []
    for reference in aligned_references(pe, types[0]):
        locator = reference-12
        try:
            if words(pe,locator,3) != (0,0,0):
                continue
            for reference in aligned_references(pe,locator):
                va = reference+4
                if table_data(pe,va,9)['name'] != name:
                    continue
                count = 0
                while count < 128:
                    value = words(pe,va+count*4,1)[0]
                    section = pe.get_section_by_rva(value-pe.OPTIONAL_HEADER.ImageBase)
                    if not section or not section.Characteristics & 0x20000000:
                        break
                    count += 1
                if not 9 <= count < 128:
                    raise ValueError('Unsupported native data-table length')
                tables.append(table_data(pe,va,count))
        except ValueError:
            continue
    if len(tables) != 1:
        raise ValueError('Missing or ambiguous primary table: '+name)
    return tables[0]


def record(va, data):
    instructions(data, va)
    return {'va':va, 'size':len(data), 'sha256':hashlib.sha256(data).hexdigest()}


def verify(fixtures):
    import pefile
    identities = json.loads((ROOT/'profiles/panel-engine/provider-clients.json').read_bytes())['profiles']
    bindings = json.loads((ROOT/'profiles/panel-engine/engine-bindings.json').read_bytes())
    images = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != identities[branch]['fixtureSha256']:
            raise ValueError('Changed updated-engine fixture: '+branch)
        images[branch] = pefile.PE(data=raw)
    public = images['public']; query = map_query_profiles(); managers = manager_profiles(); output = {}
    def read(pe, va, size):
        return pe.get_data(va-0x400000, size)
    for branch, pe in images.items():
        clients = {}; providers = {}
        def compare(label, public_va, va, size, *, view_offsets=()):
            original = read(public, public_va, size); body = read(pe, va, size)
            if view_offsets:
                # Existing Manager profile, confirmed by all three actual
                # message callers. GOG's stream adds three virtual methods.
                original = bytearray(original)
                slot = int(managers[branch]['streamMessageSlot'], 0)
                for offset, opcode in view_offsets:
                    if original[offset:offset+3] != bytes.fromhex(opcode+'68'):
                        raise ValueError('Stock Items message frame changed')
                    original[offset+2] = slot
                original = bytes(original)
            if not pattern(original, public_va).fullmatch(body):
                raise ValueError('Updated SDK ordinary client differs: '+label+'/'+branch)
            clients[label] = record(va, body)
            return body
        def function(name, public_va, va, size, source):
            body = compare(name, public_va, va, size)
            providers[name] = {**record(va, body), 'source':source}
            return body
        # These exact stock Items-list bodies are already owned by
        # InventoryItemDisplay.inl. Use the actual calls, not one of the 33
        # byte-identical map iterator instantiations elsewhere in the image.
        item_va = {'public':0x4a2e30, 'beta2':0x4a3710, 'gog':0x4a3cc0}[branch]
        items = compare('stockItems', 0x4a2e30, item_va, 0x1a1,
            view_offsets=((0x51,'8b42'),(0x6a,'8b42'),(0x7f,'8b42')))
        test = target(items, item_va, 0xef)
        name = target(items, item_va, 0x11a)
        step = target(items, item_va, 0x143)
        test_body = function('ITEM_TEST', 0x51e9c0, test, 62, 'stockItems+0xef')
        name_body = function('ITEM_NAME', 0x51e920, name, 149, 'stockItems+0x11a')
        function('MAP_NEXT', 0x4199e0, step, 108, 'stockItems+0x143')
        lookup = target(test_body, test, 0x20)
        if target(name_body, name, 0x3a) != lookup:
            raise ValueError('Item APIs disagree on the stock description lookup')
        function('ACT_LOOKUP', 0x40bd00, lookup, 110, 'ITEM_TEST+0x20 and ITEM_NAME+0x3a')
        hidden_va = 0x400000+query[branch]['nearestHidden']
        hidden = compare('hiddenCoordinateArgumentAndPosition', 0x5bea17, hidden_va+0x27, 0x5bea91-0x5bea17)
        # The client begins at argument capture, ends before its error path.
        # It proves the coordinate-ref slot and unit/map/position frame only.
        unit_pos = target(hidden, hidden_va+0x27, 0x43)
        function('UNIT_POS', 0x5c1f00, unit_pos, 162, 'GetNearestHiddenCoord+0x6a')
        compare('stockCoordinateResultFields',0x5beb76,hidden_va+0x186,12)
        compare('stockBooleanSuccessResult',0x5beb9e,hidden_va+0x1ae,12)
        compare('stockBooleanFalseResult',0x5bebc9,hidden_va+0x1d9,12)
        registration=compare('stockHiddenCoordinateRegistration',0x5c1206,
            0x400000+query[branch]['registration']+0x7f6,35)
        if registration[22:24]!=bytes.fromhex('6a06') or struct.unpack_from('<I',registration,25)[0]!=hidden_va:
            raise ValueError('Stock native boolean return-type registration changed')
        argument_at = bindings['components']['script-functions']['functions']['ARG_AT']['profiles'][branch]
        engine = bindings['components']['script-functions']['functions']['AGENT_MGR']['profiles'][branch]
        random_va, random_body = matches(pe, read(public,0x5bd1c0,70),0x5bd1c0,
            {0xa:argument_at,0x15:argument_at,0x35:engine})
        clients['stockRandomNumber'] = record(random_va, random_body)
        random = target(random_body, random_va, 0x3c)
        wrapper = read(pe,random,8)
        if wrapper[:4] != bytes.fromhex('83c120e9'):
            raise ValueError('Stock random API owner frame changed')
        providers['GAME_RANDOM'] = {**record(random,wrapper), 'source':'stockRandomNumber+0x3c',
            'limits':'Stock wrapper API; random-generator implementation not followed.'}
        # The literal SMNU and virtual find/release argument frames tie the
        # singleton provider to a real LoadDialog client. Do not reconstruct
        # its constructor or the resource/allocator implementations.
        layout_va, layout = matches(pe,read(public,0x638a38,0x76),0x638a38,{})
        clients['stockLayoutFindAndRelease'] = record(layout_va,layout)
        manager = target(layout,layout_va,0x65)
        function('LIB_MANAGER',0x626aa0,manager,108,'stockLayoutFindAndRelease+0x65')

        # The complete ordinary stock display methods retain the same spell,
        # effect and item traversal instructions on each build. Only GOG's
        # already-proven stream-message slot differs. This never follows an
        # actor callback, overlay cleanup, or a called helper implementation.
        for label, root, size, message_offset, opcode in (
                ('stockHeroSpells',0x4a3320,0x50f,0x49c,'8b42'),
                ('stockHeroEffects',0x4a3830,0x910,0x89f,'8b50')):
            original = read(public,root,size)
            va, _ = matches(pe,original[:0x38],root,{})
            body = compare(label,root,va,size,view_offsets=((message_offset,opcode),))
            if label == 'stockHeroSpells':
                import capstone
                field = [(i.address-root+i.disp_offset) for i in instructions(original,root)
                         for op in i.operands if op.type == capstone.x86.X86_OP_MEM
                         and op.mem.disp == 0x7c545c]
                if len(field) != 1:
                    raise ValueError('Stock spell action-catalog reference changed')
                offset = field[0]
                action_global = struct.unpack_from('<I',body,offset)[0]

        dialog = named_table(pe,'.?AVCYDialog@@')
        view = named_table(pe,'.?AVDialogView@@')
        slots = {}
        for label, root, size, offsets in (
                ('VIEW_SETVISIBLE',0x4b3d20,110,((0x12,'8b50'),(0x32,'8b50'),(0x55,'8b50'))),
                ('VIEW_LINKBAR',0x4b4440,261,()),
                ('VIEW_SETTEXT_C',0x4b4840,27,()),
                ('VIEW_SENDITEM',0x4b3db0,10,())):
            original = bytearray(read(public,root,size))
            for offset, opcode in offsets:
                if original[offset:offset+3] != bytes.fromhex(opcode+'68'):
                    raise ValueError('Stock view message frame changed')
                original[offset+2] = int(managers[branch]['streamMessageSlot'],0)
            candidates = [(index*4,va) for index,va in enumerate(view['slots'])
                if pattern(bytes(original),root).fullmatch(read(pe,va,size))]
            if len(candidates) != 1:
                raise ValueError('View API slot differs/ambiguous: '+label+'/'+branch)
            slot, va = candidates[0]
            slots[label] = slot
            clients[label] = record(va,read(pe,va,size))
        if slots['VIEW_SENDITEM'] != int(managers[branch]['streamMessageSlot'],0):
            raise ValueError('View message slot contradicts existing Manager profile')
        compare('dialogSetArt',0x64f6d0,dialog['slots'][0xc4//4],33)
        slots['DLG_SETART'] = 0xc4
        art_key = bindings['components']['window-engine']['functions']['ART_KEY']['profiles'][branch]
        background_va, background = matches(pe,read(public,0x4a29a8,41),0x4a29a8,{36:art_key})
        clients['stockHeroBackground'] = record(background_va,background)
        setter_va, setter = matches(pe,read(public,0x42e9f5,19),0x42e9f5,{})
        clients['stockSetAttributeCall'] = record(setter_va,setter)
        imports=[]
        for name in ('malloc','free'):
            found=[(library.dll.decode('ascii').lower(),entry.name.decode('ascii'),entry.address)
                for library in pe.DIRECTORY_ENTRY_IMPORT for entry in library.imports
                if entry.name==name.encode('ascii')]
            if len(found)!=1 or found[0][:2]!=('msvcr90.dll',name):
                raise ValueError('Updated SDK allocator import identity differs')
            imports.append(found[0])
        output[branch] = {'fixtureSha256':identities[branch]['fixtureSha256'],
            'providers':providers, 'clients':clients,
            'viewSendItemSlot':int(managers[branch]['streamMessageSlot'], 0),
            'actionCatalogGlobal':action_global,
            'virtualSlots':slots, 'tables':{'dialog':dialog,'view':view},'imports':imports}
    return {'schema':1, 'contract':'panel-engine.updated-sdk-opaque-clients.v1',
        'sources':['SDK src/we_engine.cpp/src/sf_windows.cpp/src/sf_explore.cpp',
            'runtime/InventoryItemDisplay.inl:InventoryItemBody',
            'runtime/MapQueryRuntime.cpp:Profile.nearestHidden',
            'profiles/panel-engine/engine-bindings.json'],
        'limits':'Bounded ordinary client/API correspondence only. Does not prove new aggregate traversal, vtable slots, imports, registration chaining or managed-handoff source rebase.',
        'profiles':output}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    result = verify({b:Path(os.environ['MAJESTY_'+b.upper()+'_EXE']) for b in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
