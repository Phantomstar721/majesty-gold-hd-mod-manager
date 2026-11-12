"""Versioned independently reversible native engine sections.

Pure byte operations: callers own file I/O and selected-executable approval.
Only the module's guarded hook and section/header fields change. Restoration
in either order preserves other sections; an owned inactive suffix is pruned
only when exact truncation back to its recorded input is possible.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import struct

BUNDLE_MAGIC = b'MMNEOBJ1'
SECTION_MAGIC = b'MMENG001'
HEADER_SIZE = 256
BRANCH_IDS = {'public':0,'beta2':1,'gog':2}
SERVICE_IDS = {'window-engine':1,'script-functions':2}
SERVICE_REVISIONS = {'window-engine':(1,2,3),'script-functions':(1,2)}
SECTIONS = {'window-engine':b'.weng','script-functions':b'.sfun'}
# Fixed native header layout, also consumed by PanelEngineModules.h.
HEADER = struct.Struct('<8s12I5s5s2x32s32s6I')


class EngineModuleError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    name:bytes
    virtual_size:int
    rva:int
    raw_size:int
    raw_offset:int
    characteristics:int
    header_offset:int


def pe(data):
    if len(data)<0x100 or data[:2]!=b'MZ':raise EngineModuleError('Not a supported PE image')
    offset=struct.unpack_from('<I',data,0x3c)[0]
    if offset+248>len(data) or data[offset:offset+4]!=b'PE\0\0':raise EngineModuleError('Invalid PE header')
    machine,count,_,_,_,optional,_=struct.unpack_from('<HHIIIHH',data,offset+4)
    if machine!=0x14c or optional<224 or struct.unpack_from('<H',data,offset+24)[0]!=0x10b:
        raise EngineModuleError('Native engines require the supported 32-bit executable')
    base,section_align,file_align=struct.unpack_from('<III',data,offset+52)
    if base!=0x400000 or file_align!=0x200 or section_align!=0x1000:
        raise EngineModuleError('Unsupported native image layout')
    start=offset+24+optional
    if not 1<=count<=96 or start+count*40>len(data):raise EngineModuleError('Invalid section table')
    sections=[]
    for index in range(count):
        at=start+index*40
        name=data[at:at+8].rstrip(b'\0')
        size,rva,raw_size,raw_offset=struct.unpack_from('<IIII',data,at+8)
        flags=struct.unpack_from('<I',data,at+36)[0]
        if raw_size and (raw_offset<start+count*40 or raw_offset+raw_size>len(data)):
            raise EngineModuleError('Invalid PE section file extent')
        sections.append(Section(name,size,rva,raw_size,raw_offset,flags,at))
    return offset,start,base,section_align,file_align,tuple(sections)


def rva_offset(data,rva,size=1):
    for section in pe(data)[-1]:
        if section.rva<=rva and rva+size<=section.rva+section.raw_size:
            return section.raw_offset+rva-section.rva
    raise EngineModuleError('Engine hook is outside backed native code')


def _strict(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise EngineModuleError('Duplicate module metadata field')
        result[key]=value
    return result


def runtime_files(root):
    """The module index is the runtime allowlist; build sources never ship."""
    from pathlib import Path
    root=Path(root).resolve()
    index=json.loads((root/'modules.json').read_bytes(),object_pairs_hook=_strict)
    if index.get('schema')!=1 or index.get('ownershipABI')!=1:
        raise EngineModuleError('Unsupported engine runtime index')
    required={service+'-'+branch for service in SERVICE_IDS for branch in BRANCH_IDS}
    if set(index.get('modules',{}))!=required:
        raise EngineModuleError('Incomplete three-version engine runtime index')
    files=['modules.json']
    for history,rows in ((False,index['modules']),(True,index.get('history',{}))):
        for name,row in rows.items():
            service,branch,revision=row['service'],row['branch'],row['revision']
            if service not in SERVICE_IDS or branch not in BRANCH_IDS or revision not in SERVICE_REVISIONS[service]:
                raise EngineModuleError('Invalid indexed engine identity')
            stem=service+'-'+branch+('-r'+str(revision) if history else '')
            relative=('history/' if history else '')+stem+'.mmne'
            if name!=stem or row['file']!=relative:
                raise EngineModuleError('Invalid indexed engine runtime path')
            data=(root/relative).read_bytes()
            if hashlib.sha256(data).hexdigest()!=row['sha256']:
                raise EngineModuleError('Indexed engine runtime changed')
            meta,_=decode_bundle(data)
            if (meta['service'],meta['branch'],meta['revision'])!=(service,branch,revision):
                raise EngineModuleError('Indexed engine runtime build differs')
            files.append(relative)
    return tuple(files)


def decode_bundle(data):
    if len(data)<16 or data[:8]!=BUNDLE_MAGIC:raise EngineModuleError('Unsupported engine module bundle')
    metadata_size,blob_size=struct.unpack_from('<II',data,8)
    if not 1<=metadata_size<=0x40000 or not 1<=blob_size<=0x100000 or len(data)!=16+metadata_size+blob_size:
        raise EngineModuleError('Invalid engine module bundle size')
    try:metadata=json.loads(data[16:16+metadata_size],object_pairs_hook=_strict)
    except (UnicodeError,json.JSONDecodeError) as exc:raise EngineModuleError('Invalid engine metadata') from exc
    blob=data[16+metadata_size:]
    if not isinstance(metadata,dict):raise EngineModuleError('Invalid engine metadata object')
    if metadata.get('schema')!=1 or metadata.get('ownershipABI')!=1:
        raise EngineModuleError('Unsupported engine module revision')
    service,branch=metadata.get('service'),metadata.get('branch')
    revision=metadata.get('revision')
    if revision not in SERVICE_REVISIONS.get(service, ()):
        raise EngineModuleError('Unsupported engine module revision')
    if service not in SERVICE_IDS or branch not in BRANCH_IDS or metadata.get('blobSize')!=blob_size:
        raise EngineModuleError('Invalid engine module service/build')
    if hashlib.sha256(blob).hexdigest()!=metadata.get('blobSha256'):raise EngineModuleError('Engine module payload changed')
    if type(metadata.get('base'))is not int or metadata['base']!=0x10000000 or type(metadata.get('hookRva'))is not int or not 0<metadata['hookRva']<0x400000:
        raise EngineModuleError('Invalid native engine address contract')
    required={'entry','ownsView','ownsController'} if service=='window-engine' else {'entry'}
    if service=='window-engine' and revision>=2: required.add('bindHandoff')
    if set(metadata.get('exports',{}))!=required or any(type(v)is not int or not 0<=v<blob_size for v in metadata['exports'].values()):
        raise EngineModuleError('Invalid native engine exports')
    seen=set()
    relocations=metadata.get('relocations')
    if not isinstance(relocations,list):raise EngineModuleError('Missing native engine relocations')
    for row in relocations:
        if not isinstance(row,list) or len(row)!=2:raise EngineModuleError('Invalid engine relocation shape')
        offset,direction=row
        if type(offset)is not int or not 0<=offset<=blob_size-4 or direction not in (-1,1) or any(i in seen for i in range(offset,offset+4)):
            raise EngineModuleError('Invalid engine relocation record')
        seen.update(range(offset,offset+4))
    try:original=bytes.fromhex(metadata['originalHook']);source=bytes.fromhex(metadata['sdkSha256'])
    except (KeyError,ValueError,TypeError) as exc:raise EngineModuleError('Invalid engine source/hook identity') from exc
    if len(source)!=32 or len(original)!=5 or original[0]!=(0xe8 if service=='window-engine' else 0xe9):
        raise EngineModuleError('Invalid engine hook contract')
    guards=metadata.get('guards')
    if not isinstance(guards,list) or not guards:raise EngineModuleError('Missing native API proof guards')
    for row in guards:
        if not isinstance(row,list) or len(row)!=3:raise EngineModuleError('Invalid API guard shape')
        rva,size,digest=row
        if type(rva)is not int or type(size)is not int or not 0<rva<0x400000 or not 0<size<=0x10000 or not isinstance(digest,str) or len(digest)!=64:
            raise EngineModuleError('Invalid API guard bounds')
    return metadata,blob


def relocated(metadata,blob,address):
    result=bytearray(blob);delta=address-metadata['base']
    for offset,direction in metadata['relocations']:
        value=struct.unpack_from('<I',result,offset)[0]
        struct.pack_into('<I',result,offset,(value+direction*delta)&0xffffffff)
    return bytes(result)


def fnv(data):
    value=2166136261
    for byte in data:value=((value^byte)*16777619)&0xffffffff
    return value


def _header(data,section):
    if section.raw_size<HEADER_SIZE or section.virtual_size<HEADER_SIZE:raise EngineModuleError('Engine section is truncated')
    values=HEADER.unpack_from(data,section.raw_offset)
    encoded=data[section.raw_offset:section.raw_offset+HEADER.size]
    if struct.unpack_from('<I',data,section.raw_offset+HEADER.size)[0]!=fnv(encoded):
        raise EngineModuleError('Native engine descriptor changed')
    magic,*rest=values
    if magic!=SECTION_MAGIC:raise EngineModuleError('Existing engine section is not a recognized Manager module; restore it with its original installer first')
    (schema,service,branch,revision,header_size,blob_size,entry,view,controller,hook,active,ownership,
     original,patched,source,digest,checksum,old_file,old_image,old_code,old_count,old_checksum)=rest
    revisions = {1:(1,2,3),2:(1,2)}
    if (schema,header_size,ownership)!=(1,HEADER_SIZE,1) or revision not in revisions.get(service,()) or service not in SERVICE_IDS.values() or branch not in BRANCH_IDS.values() or active not in (0,1):
        raise EngineModuleError('Unknown native engine section version')
    padding=section.raw_offset+160
    bind=0
    if service==1 and revision>=2:
        bind,seal=struct.unpack_from('<II',data,padding)
        if bind>=blob_size or seal!=fnv(data[section.raw_offset:padding+4]):
            raise EngineModuleError('Native engine handoff descriptor changed')
        padding+=8
    if any(data[padding:section.raw_offset+HEADER_SIZE]):
        raise EngineModuleError('Native engine descriptor changed')
    if section.virtual_size!=HEADER_SIZE+blob_size or blob_size>section.raw_size-HEADER_SIZE or not 0<=entry<blob_size:
        raise EngineModuleError('Invalid native engine section bounds')
    if not 0<old_file<=section.raw_offset or not 4<=old_count<len(pe(data)[-1]) or old_image>section.rva:
        raise EngineModuleError('Invalid native engine restoration bounds')
    if service==1 and (not 0<=view<blob_size or not 0<=controller<blob_size):raise EngineModuleError('Invalid native ownership exports')
    blob=data[section.raw_offset+HEADER_SIZE:section.raw_offset+HEADER_SIZE+blob_size]
    if hashlib.sha256(blob).digest()!=digest or fnv(blob)!=checksum:raise EngineModuleError('Installed native engine module bytes changed')
    at=rva_offset(data,hook,5)
    if data[at:at+5]!=(patched if active else original):raise EngineModuleError('Another patch changed the native engine hook')
    if original[0]!=(0xe8 if service==1 else 0xe9) or patched[0]!=original[0]:raise EngineModuleError('Invalid native engine transfer')
    actual=hook+5+struct.unpack_from('<i',patched,1)[0]
    if actual!=section.rva+HEADER_SIZE+entry:raise EngineModuleError('Native engine hook does not target its entry')
    return {'service':service,'branch':branch,'active':bool(active),'revision':revision,'bindHandoff':bind,'hook':hook,
        'original':original,'patched':patched,'source':source.hex(),'entry':entry,'view':view,'controller':controller,
        'old_file':old_file,'old_image':old_image,'old_code':old_code,'old_count':old_count,'old_checksum':old_checksum,
        'section':section,'blob':blob,'raw':values}


def inspect(data,service,branch=None):
    sections=[s for s in pe(data)[-1] if s.name==SECTIONS[service]]
    if not sections:return None
    if len(sections)!=1:raise EngineModuleError('Duplicate native engine sections')
    header=_header(data,sections[0])
    if header['service']!=SERVICE_IDS[service] or branch is not None and header['branch']!=BRANCH_IDS[branch]:
        raise EngineModuleError('Native engine module belongs to another service/build')
    return header


def install(data,bundle,branch):
    metadata,blob=decode_bundle(bundle);service=metadata['service']
    if metadata['branch']!=branch:raise EngineModuleError('Native engine module does not support this selected executable')
    nt=pe(data)[0]
    # GOG and beta share the version/timestamp; their distinct native API
    # proof windows below (and independent hook bytes) distinguish their ABI.
    from .manager.qol_service import SUPPORTED_BRANCHES
    timestamp=next(b.coff_timestamp for b in SUPPORTED_BRANCHES if ('gog' if b.key.startswith('gog') else b.key)==branch)
    if struct.unpack_from('<I',data,nt+8)[0]!=timestamp:raise EngineModuleError('Native engine executable build differs')
    for rva,size,digest in metadata['guards']:
        at=rva_offset(data,rva,size)
        if hashlib.sha256(data[at:at+size]).hexdigest()!=digest:
            raise EngineModuleError('A native engine API boundary was changed by another executable patch (RVA '+hex(rva)+')')
    existing=inspect(data,service,branch)
    if existing:
        expected=relocated(metadata,blob,0x400000+existing['section'].rva+HEADER_SIZE)
        if expected!=existing['blob'] or existing['source']!=metadata['sdkSha256']:
            raise EngineModuleError('Installed engine revision differs; remove it before changing revisions')
        if existing['active']:return data
        result=bytearray(data)
        struct.pack_into('<I',result,existing['section'].raw_offset+8+10*4,1)
        _seal_header(result,existing['section'].raw_offset)
        at=rva_offset(result,existing['hook'],5);result[at:at+5]=existing['patched']
        return bytes(result)
    nt,start,base,section_align,file_align,sections=pe(data)
    slot=start+len(sections)*40
    first=min(s.raw_offset for s in sections if s.raw_size)
    if slot+40>first or any(data[slot:slot+40]):raise EngineModuleError('No unused PE section-header slot is available')
    def align(value,to):return (value+to-1)//to*to
    rva=align(max(struct.unpack_from('<I',data,nt+80)[0],max(s.rva+max(s.virtual_size,s.raw_size) for s in sections)),section_align)
    offset=align(len(data),file_align)
    linked=relocated(metadata,blob,base+rva+HEADER_SIZE)
    virtual_size=HEADER_SIZE+len(linked);raw_size=align(virtual_size,file_align)
    if rva+virtual_size>=0x80000000:raise EngineModuleError('Native module address is outside supported x86 image range')
    at=rva_offset(data,metadata['hookRva'],5)
    original=bytes.fromhex(metadata['originalHook'])
    if data[at:at+5]!=original:raise EngineModuleError('Native engine hook is occupied by an unknown executable patch')
    entry=metadata['exports']['entry']
    patched=bytes([original[0]])+struct.pack('<i',rva+HEADER_SIZE+entry-(metadata['hookRva']+5))
    header=HEADER.pack(SECTION_MAGIC,1,SERVICE_IDS[service],BRANCH_IDS[branch],metadata['revision'],HEADER_SIZE,len(linked),entry,
        metadata['exports'].get('ownsView',0),metadata['exports'].get('ownsController',0),metadata['hookRva'],1,1,
        original,patched,bytes.fromhex(metadata['sdkSha256']),hashlib.sha256(linked).digest(),fnv(linked),len(data),
        struct.unpack_from('<I',data,nt+80)[0],struct.unpack_from('<I',data,nt+28)[0],len(sections),struct.unpack_from('<I',data,nt+88)[0])
    result=bytearray(data);result+=b'\0'*(offset-len(result))
    descriptor=bytearray(header+struct.pack('<I',fnv(header))+b'\0'*(HEADER_SIZE-len(header)-4))
    if service=='window-engine' and metadata['revision']>=2:
        struct.pack_into('<I',descriptor,160,metadata['exports']['bindHandoff'])
        struct.pack_into('<I',descriptor,164,fnv(descriptor[:164]))
    result+=descriptor+linked+b'\0'*(raw_size-virtual_size)
    struct.pack_into('<8sIIIIIIHHI',result,slot,SECTIONS[service].ljust(8,b'\0'),virtual_size,rva,raw_size,offset,0,0,0,0,0xe0000060)
    struct.pack_into('<H',result,nt+6,len(sections)+1)
    struct.pack_into('<I',result,nt+80,align(rva+virtual_size,section_align))
    struct.pack_into('<I',result,nt+28,struct.unpack_from('<I',data,nt+28)[0]+raw_size)
    struct.pack_into('<I',result,nt+88,0)
    result[at:at+5]=patched
    inspect(result,service,branch)
    return bytes(result)


def remove(data,service,branch):
    header=inspect(data,service,branch)
    if header is None:return data
    result=bytearray(data)
    at=rva_offset(result,header['hook'],5);result[at:at+5]=header['original']
    struct.pack_into('<I',result,header['section'].raw_offset+8+10*4,0)
    _seal_header(result,header['section'].raw_offset)
    while True:
        nt,start,_,_,_,sections=pe(result)
        last=sections[-1]
        if last.name not in SECTIONS.values():break
        owned=_header(result,last)
        if owned['active'] or last.raw_offset+last.raw_size!=len(result) or owned['old_count']!=len(sections)-1:break
        if any(result[last.raw_offset+last.virtual_size:last.raw_offset+last.raw_size]):break
        struct.pack_into('<H',result,nt+6,owned['old_count'])
        struct.pack_into('<I',result,nt+80,owned['old_image'])
        struct.pack_into('<I',result,nt+28,owned['old_code'])
        struct.pack_into('<I',result,nt+88,owned['old_checksum'])
        result[last.header_offset:last.header_offset+40]=b'\0'*40
        del result[owned['old_file']:]
    return bytes(result)


def _seal_header(data,offset):
    struct.pack_into('<I',data,offset+HEADER.size,fnv(data[offset:offset+HEADER.size]))
    service=struct.unpack_from('<I',data,offset+12)[0]
    revision=struct.unpack_from('<I',data,offset+20)[0]
    if service==1 and revision>=2:
        struct.pack_into('<I',data,offset+164,fnv(data[offset:offset+164]))
