"""Read actual candidate; compose GPL in memory and compile temporary sources, never Prepare."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from majesty_cam.package import load_package
from majesty_cam.compose import (SelectedMod, inventory_package, merge_gpl_resources,
    _feature_stock_functions, compile_gpl)
from majesty_cam.hero_combat_policy import HeroCombatPolicy, ROOTS
from majesty_cam.damage_contributions import DamageContribution
from majesty_cam.gpl import parse_gpl, DefinitionKind
from majesty_cam.script_review import ScriptReviewSession


def check(candidate, game):
    receipt = json.loads((candidate.parent/'verification.json').read_text())
    hashes = {p.relative_to(candidate).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in candidate.rglob('*') if p.is_file()}
    assert hashes == receipt['package_files'], 'Candidate differs from owner verification receipt'
    package = load_package(candidate)
    features = tuple(f for f in package.definition.runtime_features
                     if isinstance(f, (HeroCombatPolicy, DamageContribution)))
    assert sum(isinstance(f, HeroCombatPolicy) for f in features) == 1
    # Exercise the production GPL review/finish path for this change only.
    # The complete package is admitted above; unrelated native features are not regenerated here.
    package = replace(package, definition=replace(package.definition, runtime_features=features))
    inventory = inventory_package(SelectedMod('candidate', package))
    outputs = {}
    for scope in ('majesty', 'majestyexpansion'):
        loader = lambda names: _feature_stock_functions(game, names, dataset=scope)
        review = ScriptReviewSession()
        result = merge_gpl_resources((inventory,), stock_function_loader=loader,
            script_review=review, script_dataset=scope)
        assert not review.unresolved
        if hasattr(result, 'resume'): result = result.resume()
        parsed = parse_gpl(result.source_set.gpl_text)
        for name in ROOTS:
            assert 'mm_hcp_is_' in parsed.require(DefinitionKind.FUNCTION, name).text.lower()
        damage = parsed.require(DefinitionKind.FUNCTION, 'MM_Damage_Spell').text.lower()
        assert '$whp_spelldamagescale' in damage
        with TemporaryDirectory() as temporary:
            compile_gpl(result.source_set, game/'SDK/Gplbcc.exe', Path(temporary)/'compiler', stem='CombatCandidate')
        outputs[scope] = hashlib.sha256(result.source_set.gpl_text.encode()).hexdigest()
    return {'candidate': str(candidate), 'candidate_files': hashes, 'generated_gpl_sha256': outputs,
            'coverage': 'Actual package admission; production GPL review/finish for combat and damage features; isolated compiler',
            'profile_built': False, 'native_gameplay_accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--game', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD'))
    args = parser.parse_args()
    print(json.dumps(check(args.candidate, args.game), indent=2))
