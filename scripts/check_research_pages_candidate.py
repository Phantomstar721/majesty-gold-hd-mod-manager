"""Validate actual sibling research resources/registry in memory; never Prepare."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from majesty_cam.package import load_package
from majesty_cam.manager.preflight import catalog_merge_preflight
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.compose import (SelectedMod, inventory_package,
    _require_controller_feature_evidence, _CONTROLLER_FEATURE_CLASSES)
from majesty_cam.scoped_descriptions import inventory_records
from majesty_cam.stock_controller_features import (StockAp10Ap69SecondaryPanel,
    StockAp99ResearchRow, StockAp17UpgradeResearchGate)
from majesty_cam.stock_controller_registry import (resolve_stock_controller_registry,
    encode_stock_controller_registry, decode_stock_controller_registry)


def validate_completion_storage(rows, mapping):
    # Charged actions borrow the descriptor, not its permanent completion bit.
    identities=[(mapping[r.panel_key][0],r.completion_template_control_id)
                for r in rows if not r.charge_ms]
    if len(identities)!=len(set(identities)):
        raise ValueError('Independent research rows share completion storage')


def check(candidate, game):
    hashes={p.relative_to(candidate).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in candidate.rglob('*') if p.is_file()}
    assert hashes == json.loads((candidate.parent/'verification.json').read_text())['package_files']
    inv=inventory_package(SelectedMod('research candidate',load_package(candidate)))
    package=inv.selected.package
    issues=catalog_merge_preflight(package.mod_id, package.display_name, candidate,
        registry=CompatibilityRegistry({}), game_path=game)
    if issues:
        raise ValueError('Full catalog preflight rejected candidate: '+repr(issues))
    features=inv.selected.package.definition.runtime_features
    _require_controller_feature_evidence(inv,tuple(f for f in features if isinstance(f,_CONTROLLER_FEATURE_CLASSES)))
    rows=tuple(f for f in features if isinstance(f,StockAp99ResearchRow))
    keys={f.panel_key for f in rows}
    panels=tuple(f for f in features if isinstance(f,StockAp10Ap69SecondaryPanel) and f.panel_key in keys)
    selected=tuple(f for f in features if isinstance(f,(StockAp10Ap69SecondaryPanel,StockAp99ResearchRow,StockAp17UpgradeResearchGate)) and f.panel_key in keys)
    descriptions=[r.to_element() for r in inventory_records(inv).values()]
    fourcc=lambda s:int.from_bytes(s.encode('ascii'),'little')
    mapping={}
    for panel in panels:
        dialogs={e.find('./Game/DialogID').get('value') for e in descriptions
            if e.get('subType')=='Building' and e.get('ID','').startswith(panel.building_family_id)}
        assert len(dialogs)==1, 'Research family must have one parent dialog across tiers'
        mapping[panel.panel_key]=(fourcc(dialogs.pop()),fourcc(panel.source_dialog_id))
    registry=resolve_stock_controller_registry(selected,mapping)
    payload=encode_stock_controller_registry(registry)
    assert decode_stock_controller_registry(payload)==registry
    validate_completion_storage(rows,mapping)
    return {'candidate':str(candidate),'package_files':hashes,
        'catalog_preflight': {'issues': [], 'game_path': str(game), 'compatibility_registry': 'empty; no trusted overrides'},
        'panels':[asdict(p) for p in panels],'rows':[asdict(r) for r in rows],
        'registry_sha256':hashlib.sha256(payload).hexdigest(),
        'resource_evidence':'Complete candidate controller resources validated; research registry encoded/decoded in memory',
        'profile_built':False,'gameplay_accepted':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('candidate',type=Path)
    parser.add_argument('--game',type=Path,default=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD'))
    args=parser.parse_args()
    print(json.dumps(check(args.candidate,args.game),indent=2))
