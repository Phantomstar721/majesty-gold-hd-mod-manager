"""Build reproducible, relocatable private-alpha modules from the pinned SDK.

No game/Manager profile is created and no executable is patched. Output stays
under local/panel-engine-alpha. The SDK and its linker remain private inputs;
the installed application needs only versioned binary modules and relocation
records. Unsupported source revisions or unresolved bindings fail the build.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import zlib

from panel_engine_profile_sources import ROOT, BRANCHES
from generate_panel_engine_bindings import DEFAULT_SDK, generate

LINK_BASE = 0x10000000
MAGIC = b'MMNEOBJ1'


def bounded_class_copy(source,maximum,classes):
    source,count=re.subn(r'(#define VT_COPY_SLOTS\s+)40\b',lambda m:m[1]+str(maximum),source)
    if count!=1:raise ValueError('SDK table-copy capacity changed')
    source,count=re.subn(r'(#define MAX_CLASSES\s+)50\b',lambda m:m[1]+str(classes),source)
    if count!=1:raise ValueError('SDK class capacity changed')
    old='for (int i = 0; i <= VT_COPY_SLOTS; i++) c->vt[i] = vt[i - 1];'
    if source.count(old)!=1:raise ValueError('SDK table copy changed')
    return source.replace(old,'int count=MMWE_VtableLength(vt); if(count<9 || count>VT_COPY_SLOTS) { --g_nclasses; return 0; }\n        for (int i=0;i<=count;++i) c->vt[i]=vt[i-1];')


def cpp_tables(profile, maximum):
    rows = profile['tables']
    text = ['struct MMWE_Table { void** table; unsigned count; void* words['+str(maximum+1)+']; };',
            'static const MMWE_Table MMWE_Tables[] = {']
    for row in rows:
        locator = row.get('locatorVA')
        # The preceding RTTI locator pointer is independently read from the
        # fixed fixture; producer supplies it below, never derives a delta.
        values = [locator, *row['slots']]
        text.append('{(void**)'+hex(row['va'])+','+str(row['entryCount'])+', {'+
                    ','.join('(void*)'+hex(value) for value in values)+'}},')
    text += ['};', 'static int MMWE_VtableLength(void** table) {',
             'for (unsigned n=0;n<sizeof(MMWE_Tables)/sizeof(MMWE_Tables[0]);++n) {',
             'const MMWE_Table& row=MMWE_Tables[n]; if(row.table!=table) continue;',
             'for(unsigned i=0;i<=row.count;++i) if(table[(int)i-1]!=row.words[i]) return 0;',
             'return row.count; } return 0; }']
    return '\n'.join(text)


def transform(source, component, branch, bindings, tables):
    functions = bindings['components'][component]['functions']
    seen = set()
    def function(match):
        name, type_name = match.group(1), match.group(2)
        if name not in functions:
            raise ValueError('Unreviewed native function macro: '+name)
        seen.add(name)
        address = functions[name]['profiles'][branch]
        if component == 'window-engine' and name == 'AGENT_UNIT':
            return 'static void* __fastcall MMWE_LiveAgentUnit(void*,void*);\n#define AGENT_UNIT MMWE_LiveAgentUnit'
        return '#define '+name+' (('+type_name+')'+hex(address)+')'
    source = re.sub(r'^#define\s+(\w+)\s+\(\((\w+_t)\)0x[0-9a-fA-F]+\)',function,source,flags=re.M)
    if seen != set(functions):
        raise ValueError('SDK native macro inventory changed')
    extra = bindings['extra'][branch]
    if component == 'window-engine':
        replacements = {'0x7463f4u':hex(extra['integerVtable'])+'u',
                        '0x73d204u':hex(extra['listVtable'])+'u',
                        '0x7c12f0':hex(extra['cameraGlobal']),
                        '0x7c1394':hex(extra['systemAlertGlobal'])}
        for original,value in replacements.items():
            if sum(line.split('//',1)[0].count(original) for line in source.splitlines()) != 1:
                raise ValueError('SDK global source anchor changed: '+original)
            source=source.replace(original,value)
        source,count=re.subn(r'^#define GPL_DEBUGGER_ON .*$', '#define GPL_DEBUGGER_ON 0',source,flags=re.M)
        if count!=1:raise ValueError('SDK diagnostic gate changed')
        maximum=max(p['maximumEntries'] for p in tables['profiles'].values())
        classes=50  # retain the SDK's bounded class capacity for composed tables
        source=bounded_class_copy(source,maximum,classes)
        header=cpp_tables(tables['profiles'][branch],maximum)
        agent_header=ROOT/'runtime/PanelEngineAgentClient.h'
        source=header+'\n#include '+json.dumps(agent_header.as_posix())+'\n'+source
        raw=functions['AGENT_UNIT']['profiles'][branch]
        source+='\nstatic void* __fastcall MMWE_LiveAgentUnit(void* agent,void*) { return MajestyPanelEngine::ResolveLiveAgentUnit(agent,(MajestyPanelEngine::AssociatedUnit)'+hex(raw)+'); }\n'
        source+='\n#include '+json.dumps((ROOT/'runtime/PanelEngineOwnerProbe.inl').as_posix())+'\n'
        from panel_engine_handoff_source import adapt
        source=adapt(source)
    else:
        for original,key in (('0x7c5304','unitCatalog'),('0x7c544c','runtimeGlobal'),
                             ('0x5bc9c0','boardExtents'),('0x663da0','listCopy'),('0x4c3740','placeBuilding')):
            if sum(line.split('//',1)[0].count(original) for line in source.splitlines())!=1:
                raise ValueError('SDK source address anchor changed: '+original)
            source=source.replace(original,hex(extra[key]))
        hook='''extern "C" unsigned MM_SF_Continuation = '''+hex(extra['scriptContinuation'])+''';
extern "C" __declspec(naked) void SF_Hook(void) {
    __asm { pushfd
            pushad
            call SF_Register
            popad
            popfd
            jmp dword ptr [MM_SF_Continuation] }
}
'''
        source,count=re.subn(r'extern "C" __declspec\(naked\) void SF_Hook\(void\)\s*\{[\s\S]*\}\s*\Z',lambda _:hook,source)
        if count!=1:raise ValueError('SDK registration hook changed')
    source+='''\nextern "C" void* __cdecl memcpy(void* d,const void* s,unsigned n) {
volatile unsigned char* out=(volatile unsigned char*)d;
const unsigned char* in=(const unsigned char*)s; while(n--) *out++=*in++; return d; }
'''
    return source


def relocation_records(linker,obj):
    secs,syms=linker.read_coff(obj)
    order=[i for i,s in enumerate(secs) if linker.keep(s) and s['ch']&linker.IMAGE_SCN_CNT_CODE]+[
        i for i,s in enumerate(secs) if linker.keep(s) and not s['ch']&linker.IMAGE_SCN_CNT_CODE and not s['ch']&linker.IMAGE_SCN_CNT_UNINITIALIZED_DATA]+[
        i for i,s in enumerate(secs) if linker.keep(s) and s['ch']&linker.IMAGE_SCN_CNT_UNINITIALIZED_DATA]
    place={};size=0
    for i in order:
        alignment=max(secs[i]['align'],4);size=(size+alignment-1)//alignment*alignment
        place[i]=size;size+=len(secs[i]['data'])
    defined={s['name']:s for s in syms if s and s['sec']>0 and s['cls']==2}
    records=[]
    for i in order:
        for offset,index,kind in secs[i]['relocs']:
            symbol=syms[index]
            if symbol['sec']==0 and symbol['name'] in defined:symbol=defined[symbol['name']]
            internal=symbol['sec']>0
            if kind in (6,7) and internal:records.append([place[i]+offset,1])
            elif kind==0x14 and not internal:records.append([place[i]+offset,-1])
            elif kind not in (6,7,0x14):raise ValueError('Unsupported module relocation')
    if len({r[0] for r in records})!=len(records):raise ValueError('Overlapping module relocations')
    return records


def build(sdk_root,work,fixtures):
    import pefile
    work=work.resolve()
    if not work.is_relative_to((ROOT/'local/panel-engine-alpha').resolve()):raise ValueError('Module output escapes alpha workspace')
    work.mkdir(parents=True,exist_ok=True)
    bindings=generate()
    expected=json.loads((ROOT/'profiles/panel-engine/engine-bindings.json').read_bytes())
    if bindings!=expected:raise ValueError('Native binding evidence changed; review before building')
    tables=json.loads((ROOT/'profiles/panel-engine/controller-tables.json').read_bytes())
    hooks=json.loads((ROOT/'profiles/panel-engine/hook-sites.json').read_bytes())
    linker_path=sdk_root/'Window Engine/Tools/we_link.py'
    spec=importlib.util.spec_from_file_location('alpha_sdk_linker',linker_path)
    linker=importlib.util.module_from_spec(spec);spec.loader.exec_module(linker)
    compiler=Path('C:/Program Files (x86)/Microsoft Visual Studio/2017/BuildTools/VC/Tools/MSVC/14.16.27023/bin/Hostx86/x86/cl.exe')
    index={'schema':1,'ownershipABI':1,'modules':{}}
    for branch in BRANCHES:
        raw=fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest()!=tables['profiles'][branch]['fixtureSha256']:raise ValueError('Fixture changed: '+branch)
        pe=pefile.PE(data=raw)
        guards={}
        def collect(value):
            if isinstance(value,dict):
                if {'va','size','sha256'}<=value.keys():
                    va,size=value['va'],value['size']
                    if type(va)is int and type(size)is int and size>0:
                        key=(va-0x400000,size)
                        if key in guards and guards[key]!=value['sha256']:raise ValueError('Conflicting API guard')
                        guards[key]=value['sha256']
                for child in value.values():collect(child)
            elif isinstance(value,list):
                for child in value:collect(child)
        for report in bindings['reports']:
            collect(json.loads((ROOT/'profiles/panel-engine'/(report+'.json')).read_bytes())['profiles'][branch])
        for (rva,size),digest in guards.items():
            if hashlib.sha256(pe.get_data(rva,size)).hexdigest()!=digest:raise ValueError('Native API proof guard differs')
        for table in tables['profiles'][branch]['tables']:
            table['locatorVA']=struct.unpack('<I',pe.get_data(table['va']-0x400000-4,4))[0]
        for component,definition in bindings['components'].items():
            sdk_source=sdk_root/definition['sdkSource']
            if hashlib.sha256(sdk_source.read_bytes()).hexdigest()!=definition['sdkSha256']:raise ValueError('SDK source revision changed')
            name=component+'-'+branch
            generated=transform(sdk_source.read_text(encoding='utf8'),component,branch,bindings,tables)
            cpp=work/(name+'.cpp');cpp.write_text(generated,encoding='utf8')
            obj=work/(name+'.obj')
            compiled=subprocess.run([str(compiler),'/nologo','/c','/O2','/Os','/GS-','/GR-','/EHs-c-','/Zl','/Oi-','/W3','/TP',str(cpp),'/Fo'+str(obj)],capture_output=True,text=True,timeout=60)
            if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
            object_bytes=obj.read_bytes()
            external=linker.imp_map(raw,object_bytes)
            blob,exports=linker.link_object(object_bytes,LINK_BASE,external)
            relocations=relocation_records(linker,object_bytes)
            # Independently replay actual COFF relocation metadata and compare
            # with a fresh link at a different base. No guessed pointer scan.
            delta=0x100000
            alternate,_=linker.link_object(object_bytes,LINK_BASE+delta,external)
            replay=bytearray(blob)
            for offset,direction in relocations:
                value=struct.unpack_from('<I',replay,offset)[0]
                struct.pack_into('<I',replay,offset,(value+direction*delta)&0xffffffff)
            if bytes(replay)!=alternate:raise ValueError('Module relocation replay differs from COFF linker')
            names=({'entry':'@WE_Factory@24','ownsView':'_MMWE_OwnsView','ownsController':'_MMWE_OwnsController'} if component=='window-engine' else {'entry':'_SF_Hook'})
            if component=='window-engine': names['bindHandoff']='_MMWE_BindHandoff'
            # MSVC decorates fastcall entries with the physical stack/type
            # signature; resolve one exact name, never an approximate symbol.
            if component=='window-engine' and names['entry'] not in exports:
                names['entry']='@WE_Factory@24'
            for symbol in names.values():
                if symbol not in exports:raise ValueError('Missing module export '+symbol+'; available='+str(sorted(exports)))
            h=hooks['profiles'][branch]['windowFactoryCall' if component=='window-engine' else 'scriptRegistrationTail']
            revision=2 if component=='window-engine' else 1
            metadata={'schema':1,'service':component,'branch':branch,'revision':revision,'ownershipABI':1,
                'base':LINK_BASE,'blobSize':len(blob),'blobSha256':hashlib.sha256(blob).hexdigest(),
                'exports':{k:exports[v]-LINK_BASE for k,v in names.items()},'relocations':relocations,
                'hookRva':h['rva'],'originalHook':h['bytes'],
                'guards':[[rva,size,digest] for (rva,size),digest in sorted(guards.items())],
                'sdkSha256':definition['sdkSha256'],'generatedSha256':hashlib.sha256(generated.encode()).hexdigest(),
                'compiler':str(compiler),'linkerSha256':hashlib.sha256(linker_path.read_bytes()).hexdigest(),
                'bindingsSha256':hashlib.sha256((ROOT/'profiles/panel-engine/engine-bindings.json').read_bytes()).hexdigest()}
            encoded=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()
            artifact=MAGIC+struct.pack('<II',len(encoded),len(blob))+encoded+blob
            path=work/(name+'.mmne');path.write_bytes(artifact)
            index['modules'][name]={'file':path.name,'sha256':hashlib.sha256(artifact).hexdigest(),
                'blobSha256':metadata['blobSha256'],'service':component,'branch':branch,'revision':revision}
    (work/'modules.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
    return index


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root',type=Path,default=DEFAULT_SDK)
    parser.add_argument('--work',type=Path,default=ROOT/'local/panel-engine-alpha/native-modules')
    args=parser.parse_args()
    build(args.sdk_root,args.work,{b:Path(os.environ['MAJESTY_'+b.upper()+'_EXE']) for b in BRANCHES})
