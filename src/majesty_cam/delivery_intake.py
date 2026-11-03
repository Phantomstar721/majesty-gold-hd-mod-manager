"""Explicit delivery contracts and review staging; never installs assets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import struct
import xml.etree.ElementTree as ET

from .art import parse_tile_palette_reference
from .cam import read_cam


def digest(data):
    return hashlib.sha256(data).hexdigest()


def confined(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Use a relative slash-separated delivery path')
    rel = Path(relative)
    if rel.is_absolute() or PureWindowsPath(relative).is_absolute() or '..' in rel.parts:
        raise ValueError('Delivery path must remain inside its declared root')
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Delivery path escapes its declared root')
    return path


def canonical_voice(data, normalize=False):
    """Reuse the existing voice gate: mono 22050 Hz, PCM16, bounded RIFF.

    Optional normalization removes metadata chunks only; no sample conversion,
    resampling, trimming, gain or performance selection is performed.
    """
    if len(data) < 44 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('Expected RIFF/WAVE')
    if struct.unpack_from('<I', data, 4)[0]+8 != len(data):
        raise ValueError('RIFF extent differs from file length')
    pos, chunks = 12, []
    while pos < len(data):
        if pos+8 > len(data):
            raise ValueError('Truncated WAV chunk header')
        tag, size = data[pos:pos+4], struct.unpack_from('<I', data, pos+4)[0]
        start, end = pos+8, pos+8+size
        if end+(size & 1) > len(data):
            raise ValueError('WAV chunk exceeds file/padding bounds')
        chunks.append((tag, data[start:end]))
        pos = end+(size & 1)
    formats = [value for tag, value in chunks if tag == b'fmt ']
    samples = [value for tag, value in chunks if tag == b'data']
    if len(formats) != 1 or len(samples) != 1:
        raise ValueError('Require exactly one fmt and data chunk')
    fmt, pcm = formats[0], samples[0]
    if len(fmt) != 16 or struct.unpack('<HHIIHH', fmt) != (1, 1, 22050, 44100, 2, 16):
        raise ValueError('Require mono 22050 Hz PCM16 with canonical alignment')
    if not pcm or len(pcm) % 2:
        raise ValueError('Empty or unaligned PCM samples')
    if not normalize and [tag for tag, _ in chunks] != [b'fmt ', b'data']:
        raise ValueError('Metadata/order requires explicit --normalize-wav')
    body = b'WAVEfmt '+struct.pack('<I', 16)+fmt+b'data'+struct.pack('<I', len(pcm))+pcm
    result = b'RIFF'+struct.pack('<I', len(body))+body
    return result, {'sample_count': len(pcm)//2, 'sample_sha256': digest(pcm),
                    'metadata_normalized': result != data, 'listening_reviewed': False}


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or not {'schema_version', 'checkpoint', 'approval_reference', 'items'} <= set(manifest) or set(manifest)-{'schema_version', 'checkpoint', 'approval_reference', 'items', 'deferred_requirements'}:
        raise ValueError('Invalid delivery manifest fields')
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or not all(isinstance(manifest[k], str) and manifest[k].strip()
                                               for k in ('checkpoint','approval_reference')):
        raise ValueError('Require schema 1, checkpoint and explicit approval reference')
    if not isinstance(manifest['items'], list) or not manifest['items']:
        raise ValueError('Require a nonempty explicit delivery inventory')
    if not isinstance(manifest.get('deferred_requirements',[]),list) or any(not isinstance(v,str) or not v for v in manifest.get('deferred_requirements',[])):
        raise ValueError('Invalid deferred requirements')
    ids, paths, events, frames = set(), set(), set(), set()
    for item in manifest['items']:
        base = {'id', 'kind', 'file', 'approved_sha256', 'placeholder_sha256'}
        kind = item.get('kind') if isinstance(item, dict) else None
        required = base | ({'bindings'} if kind == 'voice' else {'frame','size','anchor','palette_index'} if kind == 'tile-frame' else set())
        if kind not in ('voice','tile-frame') or set(item) != required:
            raise ValueError('Unsupported delivery item or fields')
        if not isinstance(item['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',item['id']) or item['id'].casefold() in ids:
            raise ValueError('Require unique simple delivery IDs')
        ids.add(item['id'].casefold())
        if not isinstance(item['file'],str) or item['file'].casefold() in paths:
            raise ValueError('Require distinct delivery paths')
        paths.add(item['file'].casefold())
        hashes = item['placeholder_sha256']
        if not isinstance(hashes,list) or any(not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h) for h in hashes):
            raise ValueError('Invalid placeholder hashes')
        approved=item['approved_sha256']
        if approved is not None and (not isinstance(approved,str) or not re.fullmatch('[a-f0-9]{64}',approved)):
            raise ValueError('Invalid approved asset hash')
        if approved in hashes:
            raise ValueError('A placeholder cannot be approved as a delivered asset')
        if kind == 'voice':
            if not isinstance(item['bindings'],list):
                raise ValueError('Voice bindings must be a list; empty means integration mapping pending')
            for binding in item['bindings']:
                if not isinstance(binding,dict) or set(binding)!={'xml','cam','descriptor_id','phase','wave_id'}:
                    raise ValueError('Voice binding requires explicit XML/CAM, descriptor, phase and wave ID')
                if any(not isinstance(v,str) or not v for v in binding.values()) or not re.fullmatch(r'[\x21-\x7e]{4}',binding['wave_id']):
                    raise ValueError('Invalid voice binding')
                event=(binding['xml'].casefold(),binding['descriptor_id'],binding['phase'])
                if event in events:raise ValueError('Two deliveries target the same voice event')
                events.add(event)
        else:
            frame=item['frame']
            if not isinstance(frame,list) or len(frame)!=3 or any(type(v) is not int or v<0 for v in frame):
                raise ValueError('Frame must explicitly identify set, direction and frame ordinal')
            if tuple(frame) in frames:raise ValueError('Duplicate sprite frame identity')
            frames.add(tuple(frame))
            for key,lo,hi in [('size',1,65535),('anchor',-32768,32767)]:
                value=item[key]
                if not isinstance(value,list) or len(value)!=2 or any(type(v) is not int or not lo<=v<=hi for v in value):
                    raise ValueError('Invalid explicit sprite '+key)
            if type(item['palette_index']) is not int or not 0<=item['palette_index']<=0xFFFFFFFF:
                raise ValueError('Invalid palette ordinal')


def voice_implementation(package, binding, payload):
    """Verify emitted XML event -> WAVE bytes, not native DSND/playback."""
    xml=confined(package,binding['xml']);cam=confined(package,binding['cam'])
    if not xml.is_file() or not cam.is_file():return False
    descriptions=[e for e in ET.parse(xml).getroot().iter('Description') if e.get('type')=='Sound' and e.get('ID')==binding['descriptor_id']]
    if len(descriptions)!=1:return False
    phases=[e for e in descriptions[0].findall('Engine/Phase') if e.get('ID')==binding['phase']]
    if len(phases)!=1:return False
    waves=phases[0].findall('Wave')
    if len(waves)!=1 or waves[0].get('value')!=binding['wave_id']:return False
    archive=read_cam(cam)
    matches=[e.data for s in archive.sections if s.extension==b'WAVE' for e in s.entries if e.name[:4]==binding['wave_id'].encode()]
    return len(matches)==1 and matches[0]==payload


def validate_tile_rows(data, width, height):
    """Bounded v3 row validation from the existing guild handoff verifier.

    No palette-index/shadow-presence or perceptual rules are imported here.
    Unsupported wider span flags require the owning importer, not guesswork.
    """
    base=26
    if base+height*4>len(data):raise ValueError('Truncated sprite row directory')
    offsets=struct.unpack_from('<'+'I'*height,data,base)
    for y,offset in enumerate(offsets):
        pos=base+offset;end=base+offsets[y+1] if y+1<height else len(data)
        if not base+height*4<=pos<end<=len(data):raise ValueError('Invalid sprite row extent')
        occupied=[];ended=False
        while pos+4<=end:
            right,flags=struct.unpack_from('<HH',data,pos);pos+=4
            if flags & 0x7800:raise ValueError('Sprite span flags outside this handoff contract')
            count=flags & 2047;left=right-count
            if left<0 or right>width or pos+count>end:raise ValueError('Invalid sprite run extent')
            if any(left<b and a<right for a,b in occupied):raise ValueError('Overlapping sprite runs')
            occupied.append((left,right));pos+=count
            if flags & 32768:ended=True;break
        if not ended or pos!=end:raise ValueError('Invalid sprite row termination')


def intake(manifest_path: Path, incoming: Path, output: Path, *, package=None, normalize_wav=False):
    manifest_bytes=manifest_path.read_bytes();manifest=json.loads(manifest_bytes)
    validate_manifest(manifest)
    incoming=incoming.resolve(strict=True);output=output.resolve()
    package=package.resolve(strict=True) if package is not None else None
    if output.exists():raise ValueError('Intake output already exists; never overwrite a receipt')
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in (incoming,package) if p is not None):
        raise ValueError('Review output must be separate from delivery and package roots')
    # Validate all paths before writes; only explicitly listed files are read.
    inputs=[confined(incoming,i['file']) for i in manifest['items']]
    for item in manifest['items']:
        if item['kind']=='voice':
            for binding in item['bindings']:
                for field in ('xml','cam'):confined(package or incoming,binding[field])
    records=[];copies=[]
    for item,path in zip(manifest['items'],inputs):
        row={'id':item['id'],'file':item['file'],'kind':item['kind'],'approved':False,'implemented':False,'externally_missing':not path.is_file(),
             'native_unverified':True,'structurally_valid':False,'errors':[]}
        records.append(row)
        if row['externally_missing']:continue
        data=path.read_bytes();sha=digest(data);row['source_sha256']=sha
        copies.append(('originals/'+item['id']+path.suffix,data))
        if sha in item['placeholder_sha256']:
            row['errors'].append('Known placeholder supplied; real delivery still required');continue
        row['approved']=sha==item['approved_sha256']
        if item['approved_sha256'] is not None and not row['approved']:
            row['errors'].append('Delivery differs from the approved asset hash')
        try:
            if item['kind']=='voice':
                prepared,detail=canonical_voice(data,normalize_wav)
                row.update(detail)
                if digest(prepared) in item['placeholder_sha256']:
                    row['approved']=False
                    raise ValueError('Normalized data matches a known placeholder')
                row['implementation_source_matches']=bool(package and item['bindings'] and all(voice_implementation(package,binding,data) for binding in item['bindings']))
                row['implementation_staged_matches']=bool(package and item['bindings'] and all(voice_implementation(package,binding,prepared) for binding in item['bindings']))
                row['implemented']=row['implementation_source_matches'] or row['implementation_staged_matches']
                row['bindings']=item['bindings']
            else:
                if len(data)<26 or struct.unpack_from('<H',data)[0]!=3:
                    raise ValueError('Expected the explicitly supported version-3 TILE handoff; use the owning importer for other formats')
                height,width=struct.unpack_from('<HH',data,2)
                if [width,height]!=item['size'] or list(struct.unpack_from('<hh',data,10))!=item['anchor']:
                    raise ValueError('Sprite frame dimensions/anchor differ from approved contract')
                palette=parse_tile_palette_reference(data,tile_index=0)
                if palette is None or palette.palette_index!=item['palette_index']:
                    raise ValueError('Sprite frame palette reference differs from contract')
                validate_tile_rows(data,width,height)
                prepared=data;row['frame']=item['frame']
                row['limits']='Bounded v3 rows, explicit registration and hash only; use the owning sprite importer for IMAG timing, then validate-output presentation contract'
            row['structurally_valid']=True;row['staged_sha256']=digest(prepared)
            if not row['errors']:copies.append(('review/'+item['id']+('.wav' if item['kind']=='voice' else '.tile'),prepared))
        except (ValueError,struct.error,ET.ParseError) as exc:row['errors'].append(str(exc))
    report={'schema_version':1,'checkpoint':manifest['checkpoint'],'approval_reference':manifest['approval_reference'],
            'incoming_root':str(incoming),'package_root':str(package) if package else None,'normalization_requested':normalize_wav,
            'manifest_sha256':digest(manifest_bytes),'items':records,
            'summary':{key:[r['id'] for r in records if r[key]] for key in ('approved','implemented','externally_missing','native_unverified')},
            'specification_pending':manifest.get('deferred_requirements',[])+[
                i['id']+': final voice XML/CAM mapping pending' for i in manifest['items'] if i['kind']=='voice' and not i['bindings']],
            'invalid':[r['id'] for r in records if r['errors']],
            'awaiting_asset_approval':[r['id'] for r in records if not r['approved'] and not r['externally_missing']],
            'ready_for_native_acceptance':False,
            'implementation_scope':'Voice XML/WAVE byte mapping only. Sprite import, DSND identity, listening, motion and native acceptance remain separate.'}
    output.mkdir(parents=True)
    for name,data in copies:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (output/'manifest.json').write_bytes(manifest_bytes)
    (output/'readiness.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report
