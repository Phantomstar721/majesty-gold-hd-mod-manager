"""Exercise production panel/text composition in memory, never build a profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from majesty_cam.package import load_package
from majesty_cam.compose import (
    SelectedMod, inventory_package, resolve_building_dialogs,
    resolve_controller_registry, merge_text_resources,
    discover_private_activity_texts,
    _validate_authored_controller_panel_controls,
    _validate_authored_building_toggle_controls,
    _validate_authored_private_recruitment,
)
from majesty_cam.manager.qol_service import detect_majesty_branch


def inventory(candidate):
    package=load_package(Path(candidate).resolve())
    return inventory_package(SelectedMod('panel-resource-regression',package))


def check(game,inv):
    inventories=(inv,)
    dialogs=resolve_building_dialogs(inventories)
    controllers=resolve_controller_registry(inventories,building_dialogs=dialogs)
    _validate_authored_controller_panel_controls(inventories,controllers.registry,controllers.panels)
    _validate_authored_building_toggle_controls(inventories,controllers.registry,controllers.toggles)
    _validate_authored_private_recruitment(game,inventories,controllers.registry)
    # This is the actual production materialization/renaming path, including
    # MX05 geometry, labels and required controls. No destination is created.
    activity_texts=discover_private_activity_texts(game,inventories)
    result=merge_text_resources(game,inventories,private_activity_texts=activity_texts,
        dialog_resolutions=dialogs,controller_panels=controllers.panels,
        controller_registry=controllers.registry,external_panel_behaviors=True)
    return {'panels':len(controllers.panels),'liveAgentLists':len(controllers.registry.live_agent_lists),
        'textResources':sum(len(s.entries) for s in result.text_archive.sections),
        'resolvedViews':[p.source_dialog_id.decode('ascii') for p in controllers.panels]}


def verify(candidate):
    inv=inventory(candidate)
    cases=[]
    for branch in ('public','beta2','gog'):
        exe=Path(os.environ['MAJESTY_'+branch.upper()+'_EXE'])
        profile=detect_majesty_branch(exe)
        if profile is None or ('gog' if profile.key.startswith('gog') else profile.key)!=branch:
            raise ValueError('Required executable fixture does not match '+branch)
        game=Path(os.environ['MAJESTY_BCD_GOG_GAME' if branch=='gog' else 'MAJESTY_BCD_GAME'])
        cases.append({'branch':branch,'executableSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
            'stockRoot':str(game),**check(game,inv)})
    return {'schema':1,'candidate':str(Path(candidate).resolve()),'cases':cases,
        'profileConstructed':False,'gameLaunched':False,
        'limits':'Production controller/control validation and text-resource composition only; not a full Prepare or native gameplay acceptance.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    output=args.receipt.resolve()
    if Path(__file__).resolve().parents[1]/'local' not in output.parents:
        raise ValueError('Receipt must remain under private local/')
    evidence=verify(args.candidate)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2)+'\n')
