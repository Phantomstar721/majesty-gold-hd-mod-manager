"""Offline regression of the reported Standard/guild conflict path; no profile writes."""
import sys, json, tempfile
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from majesty_cam import compose as c
from majesty_cam.standard_scripts import read
from majesty_cam.manager.compatibility import load_compatibility_registry
from majesty_cam.manager.preflight import prepare_merge_package
from majesty_cam.script_review import ScriptReviewSession,group_conflicts
from majesty_cam.description_composition import prepare_description_views
from majesty_cam.spell_discovery import discover,transform_descriptions
from majesty_cam.native_impact import ProjectileInterception,resolve_bundle,encode as encode_impact
from majesty_cam.attack_observation_proof import from_composed_output,encode as encode_proof
from majesty_cam.scoped_output import complete_observer_patches

def main():
    game=Path(sys.argv[1])
    workshop=game.parents[1]/'workshop/content/73230'
    # Fixed regression loadout; never read a user's saved profile/selections.
    selected={identity: True for identity in (
        'DC034C13-BB90-4AA9-ABF4-55BE8C378C93',
        '709D51C7-FC4F-4EB2-B5B1-79B764BBEF1C',
        '97781481-45AB-4F64-9B40-ED662B603AE9',
        '4D4A4D50-4C42-4153-5400-000000000001')}
    standards=[]
    for folder in ('1965892371','3818059294'):
        root=workshop/folder
        for manifest in root.glob('*.mmxml'):
            for mod in ET.parse(manifest).getroot().findall('Mod'):
                identity=mod.attrib['id'].strip('{}').upper()
                if selected.get(identity):
                    standards.append(read(SimpleNamespace(package_root=root,manifest_path=manifest,
                        content_id=identity,display_name=mod.findtext('DisplayName'))))
    if {s.package.mod_id.strip('{}').upper() for s in standards} != set(selected):
        raise ValueError('Required Standard regression components missing')
    registry=load_compatibility_registry(repo_root=ROOT)
    packages=[]
    for label,folder in json.loads((ROOT/'release/package-regression-inputs.json').read_text()).items():
        root=Path(folder); manifest=next(root.glob('*.mmxml')); mod=ET.parse(manifest).getroot().find('Mod')
        packages.append(prepare_merge_package(content_id=mod.attrib['id'],display_name=label,
            source_root=root,registry=registry))
    inventories=tuple(p.inventory for p in packages)
    stock={k:v[0] for k,v in c._load_effective_stock_descriptions(game).items()}
    owners=[p.package.mod_id.strip('{}').casefold() for p in packages]+[s.package.mod_id.strip('{}').casefold() for s in standards]
    report=[]
    for order in (owners,list(reversed(owners))):
        ranks={owner:index for index,owner in enumerate(order)}
        def resolve(conflicts):
            return {p.identity:min(json.loads(p.identity),key=lambda owner:ranks[owner]) for p in group_conflicts(conflicts)}
        review=ScriptReviewSession()
        descriptions,patches,_=prepare_description_views(game,inventories,standards,review,resolve)
        descriptions,potions=c.prepare_potion_descriptions(descriptions,stock,c.potion_policies(inventories))
        policy=discover(c._spell_policy_bindings(inventories),tuple(r.to_element() for r in descriptions.document.records))
        descriptions=transform_descriptions(descriptions,policy)
        bundle=c.prepare_gpl_bundle(game,inventories,standard_script_inputs=tuple(standards),
            script_review=review,script_conflict_resolver=resolve,spell_policy_plan=policy,potion_plan=potions,
            source_context_descriptions=descriptions,private_activity_texts=c.discover_private_activity_texts(game,inventories))
        features=tuple(f for i in inventories for f in i.selected.package.definition.runtime_features if isinstance(f,ProjectileInterception))
        if features:bundle=complete_observer_patches(bundle,tuple(f.callback_symbol for f in features))
        bindings=resolve_bundle(game,inventories,bundle,descriptions,patches)
        outputs=[]
        with tempfile.TemporaryDirectory(prefix='reported-standard-regression-') as tmp:
            for scope,output in bundle.outputs:
                if output.source_set.files:
                    compiled=c.compile_gpl(output.source_set,game/'SDK/Gplbcc.exe',Path(tmp)/scope)
                    outputs.append(compiled.target.read_bytes())
        if bindings:
            proof=from_composed_output(game,(),outputs,shared_only=True,
                required_functions=tuple(f.callback_symbol for f in features),protected_functions=tuple(b.script for b in bindings))
            encode_impact(bindings,encode_proof(proof))
        report.append({'preferredOrder':order,'decisions':review.decisions,'standards':[s.name for s in standards]})
    (ROOT/'local/reported-standard-regression.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
