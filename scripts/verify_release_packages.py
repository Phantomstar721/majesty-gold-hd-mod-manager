"""Actual installed-package release gate; no profile creation or deployment.

Uses production admission, catalog checks and in-memory composition. Compiler
fixtures are disposable, outside the user's Mods folder. Native execution is
not certified by this report. Preferences exhaust all consistent owner orders.
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from majesty_cam import compose as c
from majesty_cam.manager.compatibility import load_compatibility_registry
from majesty_cam.manager.preflight import prepare_merge_package, prepared_catalog_merge_preflight
from majesty_cam.manager.runtime_profiles import unsupported_runtime_capabilities
from majesty_cam.manager.qol_service import detect_majesty_branch
from majesty_cam.script_review import ScriptReviewSession, group_conflicts
from majesty_cam.description_composition import prepare_description_views
from majesty_cam.spell_discovery import discover, transform_descriptions
from majesty_cam.native_impact import resolve_bundle, selected, ProjectileInterception, encode as encode_impact
from majesty_cam.attack_observation_proof import from_composed_output, encode as encode_proof
from majesty_cam.scoped_output import complete_observer_patches


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    roots = json.loads((ROOT / 'release/package-regression-inputs.json').read_text())
    registry = load_compatibility_registry(repo_root=ROOT)
    report = {'liveGameplayAcceptance': False, 'packages': [], 'combinations': [], 'profiles': {}}
    prepared = []
    for branch in ('PUBLIC', 'BETA2', 'GOG'):
        path = Path(os.environ['MAJESTY_' + branch + '_EXE'])
        report['profiles'][branch] = {'path': str(path), 'sha256': digest(path)}
    for label, value in roots.items():
        root = Path(value)
        row = {'label': label, 'root': str(root)}
        report['packages'].append(row)
        try:
            manifests = sorted(root.glob('*.mmxml'))
            if len(manifests) != 1:
                raise ValueError('expected one actual package manifest')
            mod = ET.parse(manifests[0]).getroot().find('Mod')
            item = prepare_merge_package(content_id=mod.attrib['id'], display_name=label,
                source_root=root, registry=registry)
            row['effectiveRoot'] = str(item.effective_root)
            row['inputs'] = [{'path': str(p), 'sha256': digest(p)}
                for p in sorted(item.effective_root.rglob('*')) if p.is_file()]
            errors = [i.message for i in item.issues]
            if errors:
                raise ValueError('; '.join(errors))
            row['profiles'] = {}
            for branch, info in report['profiles'].items():
                exe = Path(info['path'])
                issues = prepared_catalog_merge_preflight(item, game_path=args.game, executable=exe)
                features = c.resolve_runtime_feature_registry((item.inventory,),item.runtime_capabilities)
                controller = c.resolve_controller_registry((item.inventory,),item.runtime_capabilities,
                    building_dialogs=c.resolve_building_dialogs((item.inventory,)))
                capabilities, _ = c._derive_runtime_capabilities(item.runtime_capabilities,
                    has_private_activity_text=bool(c.discover_private_activity_texts(args.game,(item.inventory,))),
                    runtime_feature_registry=features,controller_registry=controller.registry,
                    has_source_exploration=c.exploration_selected((item.inventory,)),
                    has_spell_origin=c.spell_origin_selected((item.inventory,)),
                    has_projectile_interception=selected((item.inventory,)))
                unavailable = unsupported_runtime_capabilities(detect_majesty_branch(exe), capabilities)
                if issues or unavailable:
                    row.setdefault('profileErrors', {})[branch] = '; '.join([i.message for i in issues] + list(unavailable))
                    row['profiles'][branch] = 'blocked'
                else:
                    row['profiles'][branch] = 'admitted'
                row['capabilities'] = capabilities
            prepared.append(item)
        except Exception as exc:
            row['error'] = str(exc)
    if len(prepared) == len(roots):
        art_cache = {}
        stock = {k: v[0] for k,v in c._load_effective_stock_descriptions(args.game).items()}
        for size in range(1, len(prepared)+1):
            for subset in itertools.combinations(prepared,size):
                for order in itertools.permutations(subset):
                    row = {'preferredOrder': [i.display_name for i in order]}
                    report['combinations'].append(row)
                    try:
                        inventories = tuple(i.inventory for i in order)
                        art_key = tuple(sorted(i.package.mod_id for i in order))
                        if art_key not in art_cache:
                            art_cache[art_key] = [
                                {'domain': a.domain, 'sha256': hashlib.sha256(a.archive.to_bytes()).hexdigest()}
                                for a in c.merge_art_resource_domains(args.game,inventories)]
                        row['art'] = art_cache[art_key]
                        ranks = {i.package.mod_id.strip('{}').casefold(): n for n,i in enumerate(order)}
                        def resolver(conflicts):
                            return {p.identity: min(json.loads(p.identity), key=lambda o: ranks[o])
                                    for p in group_conflicts(conflicts)}
                        review = ScriptReviewSession()
                        descriptions, patches, _ = prepare_description_views(args.game,inventories,(),review,resolver)
                        descriptions, potion = c.prepare_potion_descriptions(descriptions,stock,c.potion_policies(inventories))
                        policy = discover(c._spell_policy_bindings(inventories),
                            tuple(r.to_element() for r in descriptions.document.records))
                        descriptions = transform_descriptions(descriptions,policy)
                        texts = c.discover_private_activity_texts(args.game,inventories)
                        bundle = c.prepare_gpl_bundle(args.game,inventories,script_review=review,
                            script_conflict_resolver=resolver,spell_policy_plan=policy,potion_plan=potion,
                            source_context_descriptions=descriptions,private_activity_texts=texts)
                        features = tuple(f for i in inventories for f in i.selected.package.definition.runtime_features
                                         if isinstance(f,ProjectileInterception))
                        if features:
                            bundle = complete_observer_patches(bundle,tuple(f.callback_symbol for f in features))
                        bindings = resolve_bundle(args.game,inventories,bundle,descriptions,patches)
                        outputs = []
                        with tempfile.TemporaryDirectory(prefix='manager-release-gpl-') as tmp:
                            for scope, output in bundle.outputs:
                                result = c.compile_gpl(output.source_set,args.game/'SDK/Gplbcc.exe',Path(tmp)/scope)
                                outputs.append(result.target.read_bytes())
                        row['compiledOutputSha256'] = [hashlib.sha256(b).hexdigest() for b in outputs]
                        row['modPreferences'] = review.decisions
                        if bindings:
                            proof = from_composed_output(args.game,(),outputs,shared_only=True,
                                required_functions=tuple(f.callback_symbol for f in features),
                                protected_functions=tuple(b.script for b in bindings))
                            row['interceptionRegistrySha256'] = hashlib.sha256(encode_impact(bindings,encode_proof(proof))).hexdigest()
                    except Exception as exc:
                        row['error'] = str(exc)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    failures = [r for section in ('packages','combinations') for r in report[section] if 'error' in r or 'profileErrors' in r]
    for row in failures:
        print(str(row.get('label',row.get('preferredOrder'))) + ': ' + str(row.get('error',row.get('profileErrors'))), file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
