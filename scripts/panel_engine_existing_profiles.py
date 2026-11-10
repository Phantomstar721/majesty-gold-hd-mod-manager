"""Collect explicit existing profile columns; no address deltas or native discovery."""
from pathlib import Path
import re
from panel_engine_profile_sources import (manager_profiles, map_query_profiles, quest_board_profiles,
    paid_source_target_profiles, initializer, aggregate_values)

ROOT = Path(__file__).resolve().parents[1]

def existing_boundaries():
    profiles=[]


    def add(path,field,values):
     if all(isinstance(v,int) and v>=0x400000 for v in values):
      profiles.append({'source':path,'field':field,'profiles':dict(zip(('public','beta2','gog'),values))})

    p='runtime/FeatureParityProfiles.h';s=(ROOT/p).read_text(encoding='utf8')
    for b,a,g,name in re.findall(r'\{(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+)\}, // (\w+)',s.split('struct Range')[0]):
     add(p,name,[0x400000+int(v,16) for v in (a,b,g)])
    p='runtime/BooleanRuntimeProfiles.h';s=(ROOT/p).read_text(encoding='utf8')
    fields='context present lookup vm drain append rebuild construct addAgent execute resultAt destroy table getter'.split()
    values=[]
    for i in range(3):
     body=s.split('static const Profile profile'+str(i)+'{',1)[1].split('{',1)[0]
     row=[int(n,16) for n in re.findall(r'0x[0-9a-fA-F]+',body)]
     assert len(row)==len(fields)
     values.append(row)
    for i,field in enumerate(fields):add(p,field,[row[i] for row in values])

    def split_values(text):
     values=[];start=depth=0;quoted=False
     for i,c in enumerate(text):
      if c=='"':quoted=not quoted
      if quoted:continue
      if c=='{':depth+=1
      elif c=='}':depth-=1
      elif c==',' and depth==0:values.append(text[start:i].strip());start=i+1
     if text[start:].strip():values.append(text[start:].strip())
     return values

    p='runtime/MajestyModManagerRuntime.cpp';s=(ROOT/p).read_text(encoding='utf8')
    fields=re.findall(r'\b(\w+)(?:\[\d+\])?;',s.split('struct MajestyBuildProfile {',1)[1].split('};',1)[0])
    aggregate=[]
    for label in ('kPublicBuildProfile','kBeta2BuildProfile'):
     pattern=re.search(r'\b'+label+r'\s*\{',s)
     if not pattern:
      pattern=re.search(r'\b'+label+r'\s*=\s*\{',s)
     assert pattern,label
     text=s[pattern.end():];depth=1
     for end,c in enumerate(text):
      if c=='{':depth+=1
      elif c=='}':
       depth-=1
       if depth==0:break
     values=split_values(text[:end]);assert len(values)==len(fields),(label,len(values),len(fields))
     aggregate.append({field:int(value,0) for field,value in zip(fields,values) if re.fullmatch(r'0x[0-9A-Fa-f]+|\d+',value)})
    gog={field:int(value,0) for field,value in re.findall(r'p\.(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+);',s.split('constexpr MajestyBuildProfile MakeGogBuildProfile()',1)[1].split('return p;',1)[0])}
    for field in fields:
     if field.endswith('Rva') and field in aggregate[0] and field in aggregate[1] and field in gog:
      add(p,field,[0x400000+row[field] for row in (*aggregate,gog)])

    for field in map_query_profiles()['public']:
     add('runtime/MapQueryRuntime.cpp',field,[0x400000+map_query_profiles()[b][field] for b in ('public','beta2','gog')])
    for loader,path in ((quest_board_profiles,'runtime/MajestyModManagerRuntime.cpp:QuestBoardBuildProfile'),
                        (paid_source_target_profiles,'runtime/PaidSourceTargetProfiles.h')):
     rows=loader()
     for field in rows['public']:
      add(path,field,[0x400000+rows[b][field] for b in ('public','beta2','gog')])
    p='runtime/AttackObservationNativeProfiles.h';s=(ROOT/p).read_text(encoding='utf8')
    fields=re.findall(r'\b\w+\b',s.split('struct ObservationNativeProfile {',1)[1].split('};',1)[0].replace('std::uint32_t',''))
    rows=[initializer(s,label) for label in ('publicBuild','betaBuild','gogBuild')]
    assert all(len(row)==len(fields) for row in rows)
    for i,field in enumerate(fields):add(p,field,[int(row[i],0) for row in rows])
    p='runtime/FreestyleCamRuntime.cpp';s=re.sub(r'//[^\n]*','',(ROOT/p).read_text(encoding='utf8'))
    fields=re.findall(r'\b(\w+)(?:\[\d+\])?;',s.split('struct FreestyleCamProfile {',1)[1].split('};',1)[0])
    rows=[initializer(s,label) for label in ('kPublicFreestyleProfile','kBeta2FreestyleProfile','kGogFreestyleProfile')]
    assert all(len(row)==len(fields) for row in rows)
    for i,field in enumerate(fields):
     if all(re.fullmatch('0x[0-9a-fA-F]+|[0-9]+',row[i]) for row in rows):
      add(p,field,[0x400000+int(row[i],0) for row in rows])
    p='runtime/PrivateRecruitmentProfiles.h';s=(ROOT/p).read_text(encoding='utf8')
    rows=[[int(v.strip().rstrip('uU'),0) for v in re.search(label+r'\[\]\s*=\s*\{([^}]+)\}',s)[1].split(',')]
          for label in ('kPublicHelpers','kBetaHelpers','kGogHelpers')]
    assert all(len(row)==7 for row in rows)
    for i in range(7):add(p,'helpers['+str(i)+']',[0x400000+row[i] for row in rows])

    return profiles
