"""Read-only candidate/resource parity; no Manager package construction."""
import argparse
import hashlib
import json
from pathlib import Path
from majesty_cam.cam import read_cam
from majesty_cam.package import load_package
from majesty_cam.panel_engine import find_panels
from majesty_cam.engine_dependencies import RequirementEvidence, missing
from verify_panel_resource_contracts import verify as verify_resources


def verify(candidate, baseline, output):
    candidate,baseline=Path(candidate),Path(baseline)
    package=load_package(candidate)
    current=json.loads((candidate/'mod-definition.json').read_bytes())
    prior=json.loads((baseline/'mod-definition.json').read_bytes())
    assert current['runtime_features']==prior['runtime_features']
    assert current['custom_buildings']==prior['custom_buildings']
    requirement=next(r for r in package.definition.external_patches if r.service=='window-engine.v1')
    assert requirement.minimum_revision==2
    evidence=(RequirementEvidence(requirement,package.mod_id,package.display_name,'Any','candidate metadata'),)
    assert missing(evidence,{'window-engine.v1':1}) and not missing(evidence,{'window-engine.v1':2})
    resources={}; changed={}; preserved=[]
    files=sorted(p.relative_to(baseline) for p in baseline.rglob('*') if p.is_file())
    assert files==sorted(p.relative_to(candidate) for p in candidate.rglob('*') if p.is_file())
    for name in files:
        before=(baseline/name).read_bytes(); after=(candidate/name).read_bytes()
        if before==after:
            preserved.append(str(name));continue
        changed[str(name)]=hashlib.sha256(after).hexdigest()
        if name.name=='mod-definition.json':continue
        assert name.suffix.lower()=='.cam', 'unexpected gameplay/resource change: '+str(name)
        a,b=read_cam(before),read_cam(after)
        assert len(a.sections)==len(b.sections)
        for old,new in zip(a.sections,b.sections):
            assert old.extension==new.extension
            if old.extension not in (b'SMNU',b'STRT'):
                assert old==new, 'non-panel CAM change: '+str(name)
            else:
                assert [e.name for e in old.entries]==[e.name for e in new.entries]
                resources.update(((new.extension,e.name[:4]),e.data) for e in new.entries)
    panels=find_panels(resources)
    assert panels
    for rows in panels.values():
        assert len(rows)==1 and rows[0].kind=='LABEL' and rows[0].fields[3]=='8005'
    resource_contracts=verify_resources(candidate)
    receipt={'schema':1,'candidate':str(candidate.resolve()),'baseline':str(baseline.resolve()),
             'manifestSha256':hashlib.sha256(package.manifest_path.read_bytes()).hexdigest(),
             'changed':changed,'unchangedFiles':preserved,
             'views':{k.decode('latin1'):[r.text() for r in v] for k,v in panels.items()},
             'resourceContracts':resource_contracts,
             'requiredWindowRevision':2,'privateRecipes':sum(f['type']=='stock.ap99-research-row.v1' for f in current['runtime_features']),
             'limits':'Resource/action-declaration parity, dependency admission and production controller/text composition. Separate native fixtures validate the handoff; no gameplay/save-load acceptance.',
             'profileConstructed':False,'deployed':False}
    output=Path(output).resolve()
    boundary=Path(__file__).resolve().parents[1]/'local'
    if boundary not in output.parents: raise ValueError('Receipt must remain in private local evidence')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();verify(a.candidate,a.baseline,a.output)
