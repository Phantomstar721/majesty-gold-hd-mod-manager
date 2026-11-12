"""Build the separately pinned updated SDK; no game or Manager profile writes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

from build_panel_engine_modules import LINK_BASE, MAGIC, relocation_records
from panel_engine_profile_sources import ROOT, BRANCHES
from updated_panel_engine_sources import SDK_ROOT, SOURCE_PINS, bindings, transform_unit
from verify_updated_panel_engine_clients import verify


def link_parts(linker, objects, raw, base):
    combined = bytearray(); symbols = {}; relocations = []
    for obj in objects:
        offset = (len(combined)+15)//16*16
        combined += b'\xcc'*(offset-len(combined))
        imported = linker.imp_map(raw,obj)
        if imported.keys() & symbols.keys():
            raise ValueError('Module symbols shadow an executable import')
        blob, exports = linker.link_object(obj,base+offset,{**imported,**symbols})
        relocations.extend((offset+at,direction) for at,direction in
            relocation_records(linker,obj,symbols))
        if exports.keys() & symbols.keys():
            raise ValueError('Duplicate module export')
        symbols.update(exports); combined += blob
    return bytes(combined), symbols, relocations


def build(sdk, work, fixtures):
    import pefile
    work = work.resolve()
    if not work.is_relative_to((ROOT/'local/panel-engine-alpha').resolve()):
        raise ValueError('Updated native module output escapes private workspace')
    work.mkdir(parents=True,exist_ok=True)
    clients = verify(fixtures)
    contract = bindings(clients,sdk)
    (work/'native-clients.json').write_text(json.dumps(clients,indent=2)+'\n',encoding='utf8')
    (work/'source-bindings.json').write_text(json.dumps(contract,indent=2)+'\n',encoding='utf8')
    linker_path = sdk/'Tools/we_link.py'
    spec = importlib.util.spec_from_file_location('updated_sdk_linker',linker_path)
    linker = importlib.util.module_from_spec(spec); spec.loader.exec_module(linker)
    compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio/2017/BuildTools/VC/Tools/MSVC/14.16.27023/bin/Hostx86/x86/cl.exe')
    tables = json.loads((ROOT/'profiles/panel-engine/controller-tables.json').read_bytes())
    hooks = json.loads((ROOT/'profiles/panel-engine/hook-sites.json').read_bytes())
    index = {'schema':1,'ownershipABI':1,'modules':{}}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes(); pe = pefile.PE(data=raw)
        guards = {}
        def collect(value):
            if isinstance(value,dict):
                if {'va','size','sha256'} <= value.keys():
                    va,size=value['va'],value['size']
                    if type(va)is int and type(size)is int and size>0:
                        key=(va-0x400000,size)
                        if key in guards and guards[key]!=value['sha256']:
                            raise ValueError('Conflicting updated API guard')
                        guards[key]=value['sha256']
                for child in value.values():collect(child)
            elif isinstance(value,list):
                for child in value:collect(child)
        for report in contract['legacy']['reports']:
            collect(json.loads((ROOT/'profiles/panel-engine'/(report+'.json')).read_bytes())['profiles'][branch])
        collect(clients['profiles'][branch])
        for (rva,size),digest in guards.items():
            if hashlib.sha256(pe.get_data(rva,size)).hexdigest()!=digest:
                raise ValueError('Updated API proof guard differs')
        for row in tables['profiles'][branch]['tables']:
            row['locatorVA']=struct.unpack('<I',pe.get_data(row['va']-0x400000-4,4))[0]
        objects={}; generated={}
        for unit,definition in contract['units'].items():
            source=(sdk/definition['sdkSource']).read_text(encoding='utf8')
            generated[unit]=transform_unit(source,unit,branch,contract,tables)
            cpp=work/(unit+'-'+branch+'.cpp'); cpp.write_text(generated[unit],encoding='utf8')
            obj=work/(unit+'-'+branch+'.obj')
            result=subprocess.run([str(compiler),'/nologo','/c','/O2','/Os','/GS-','/GR-','/EHs-c-',
                '/Zl','/Oi-','/W3','/TP',str(cpp),'/Fo'+str(obj)],capture_output=True,text=True,timeout=60)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
            objects[unit]=obj.read_bytes()
        for service,units,revision,exports in (
                ('window-engine',('window-engine',),3,{'entry':'@WE_Factory@24',
                    'ownsView':'_MMWE_OwnsView','ownsController':'_MMWE_OwnsController','bindHandoff':'_MMWE_BindHandoff'}),
                ('script-functions',('script-functions','script-windows','script-explore'),2,
                    {'entry':'_SF_ExploreHook'})):
            inputs=[objects[unit] for unit in units]
            blob,symbols,relocs=link_parts(linker,inputs,raw,LINK_BASE)
            alternate,_,_=link_parts(linker,inputs,raw,LINK_BASE+0x100000)
            replay=bytearray(blob)
            for at,direction in relocs:
                struct.pack_into('<I',replay,at,(struct.unpack_from('<I',replay,at)[0]+direction*0x100000)&0xffffffff)
            if bytes(replay)!=alternate:
                raise ValueError('Updated multipart relocation replay differs from COFF linker')
            if any(name not in symbols for name in exports.values()):
                raise ValueError('Missing updated native export')
            chain=[]
            if service=='script-functions':
                for stage,next_stage in (('Explore','WindowsHook'),('Windows','Hook')):
                    entry=symbols['_SF_'+stage+'Hook']-LINK_BASE
                    code=blob[entry:entry+14]
                    call=entry+7+struct.unpack_from('<i',code,3)[0]
                    tail=entry+14+struct.unpack_from('<i',code,10)[0]
                    if (code[:3]!=bytes.fromhex('9c60e8') or code[7:10]!=bytes.fromhex('619de9')
                            or call!=symbols['_SF_'+stage+'Register']-LINK_BASE
                            or tail!=symbols['_SF_'+next_stage]-LINK_BASE):
                        raise ValueError('Updated registration chain does not preserve the accepted CPU frame')
                    chain.append({'entry':entry,'register':call,'next':tail})
            h=hooks['profiles'][branch]['windowFactoryCall' if service=='window-engine' else 'scriptRegistrationTail']
            pins={contract['units'][unit]['sdkSource']:contract['units'][unit]['sdkSha256'] for unit in units}
            source_digest=(contract['units']['window-engine']['sdkSha256'] if service=='window-engine' else
                hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            meta={'schema':1,'service':service,'branch':branch,'revision':revision,'ownershipABI':1,
                'base':LINK_BASE,'blobSize':len(blob),'blobSha256':hashlib.sha256(blob).hexdigest(),
                'exports':{key:symbols[name]-LINK_BASE for key,name in exports.items()},
                'relocations':[list(r) for r in relocs], 'hookRva':h['rva'],'originalHook':h['bytes'],
                'guards':[[rva,size,digest] for (rva,size),digest in sorted(guards.items())],
                'sdkSha256':source_digest,'sdkSources':pins,
                'generatedSha256':hashlib.sha256(''.join(generated[u] for u in units).encode()).hexdigest(),
                'compiler':str(compiler),'linkerSha256':SOURCE_PINS['Tools/we_link.py'],
                'bindingsSha256':hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()}
            if chain:meta['registrationChain']=chain
            encoded=json.dumps(meta,sort_keys=True,separators=(',',':')).encode()
            artifact=MAGIC+struct.pack('<II',len(encoded),len(blob))+encoded+blob
            name=service+'-'+branch; path=work/(name+'.mmne'); path.write_bytes(artifact)
            index['modules'][name]={'file':path.name,'sha256':hashlib.sha256(artifact).hexdigest(),
                'blobSha256':meta['blobSha256'],'service':service,'branch':branch,'revision':revision}
    # Retain only the reviewed older patch bundles needed for transactional
    # upgrades. These are runtime inputs, not application/profile backups.
    from majesty_cam.engine_module import decode_bundle
    history = {}
    originals = ROOT/'payload/panel-engine/modules'
    previous = json.loads((originals/'modules.json').read_bytes())
    candidates = [(originals/row['file'],row['sha256']) for row in
                  (*previous['modules'].values(),*previous.get('history',{}).values())]
    candidates += [(ROOT/'local/fixtures/panel-engine-revision1'/(service+'-'+branch+'.mmne'),None)
                   for service in ('window-engine','script-functions') for branch in BRANCHES]
    for path,expected in candidates:
        raw=path.read_bytes()
        if expected and hashlib.sha256(raw).hexdigest()!=expected:
            raise ValueError('Changed released native upgrade input')
        meta,_=decode_bundle(raw); service=meta['service']; branch=meta['branch']; revision=meta['revision']
        if revision >= (3 if service=='window-engine' else 2):continue
        old_source=('d6049b8021575241027677db2df441cdb50bd0038735c3fda6058b70d1a40b9b' if service=='window-engine'
                    else '1c342d54eed816f5e85bdda326786d91cd82dea0e989caab56113e09eb1eba6b')
        if meta['sdkSha256']!=old_source:raise ValueError('Unreviewed legacy upgrade source')
        name=service+'-'+branch+'-r'+str(revision); relative='history/'+name+'.mmne'
        digest=hashlib.sha256(raw).hexdigest()
        if name in history and history[name]['sha256']!=digest:
            raise ValueError('Conflicting legacy native upgrade inputs')
        (work/'history').mkdir(exist_ok=True)
        (work/relative).write_bytes(raw)
        history[name]={'file':relative,'sha256':digest,'blobSha256':meta['blobSha256'],
            'service':service,'branch':branch,'revision':revision}
    required={service+'-'+branch+'-r'+str(rev) for service,revs in
              (('window-engine',(1,2)),('script-functions',(1,))) for rev in revs for branch in BRANCHES}
    if set(history)!=required:raise ValueError('Incomplete released native upgrade coverage')
    index['history']=history
    (work/'modules.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
    return index


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root',type=Path,default=SDK_ROOT)
    parser.add_argument('--work',type=Path,default=ROOT/'local/panel-engine-alpha/updated-native-modules')
    args=parser.parse_args()
    build(args.sdk_root,args.work,{b:Path(os.environ['MAJESTY_'+b.upper()+'_EXE']) for b in BRANCHES})
