"""Read-only consumer admission and isolated GPL compiler check; never Prepare."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from majesty_cam.package import load_package
from majesty_cam.compose import (SelectedMod, inventory_package,
    _require_controller_feature_evidence, _parse_inventory_gpl_sources, compile_gpl,
    _CONTROLLER_FEATURE_CLASSES)
from majesty_cam.building_employment import (BuildingEmployment, compose_service,
    validate_panel_resources, resolve_travel_text)
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.action_callback_bridge import bridge_source
from majesty_cam.stock_controller_registry import (resolve_stock_controller_registry,
    encode_stock_controller_registry, decode_stock_controller_registry, LiveAgentListTextIds)


def check(candidate, game):
    receipt = json.loads((candidate.parent/'verification.json').read_text())
    actual = {p.relative_to(candidate).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in candidate.rglob('*') if p.is_file()}
    assert actual == receipt['package_files'], 'Candidate no longer matches owner receipt'
    inventory = inventory_package(SelectedMod('employment candidate', load_package(candidate)))
    features = tuple(resolve_travel_text(f, inventory.selected.package.mod_id)
                     for f in inventory.selected.package.definition.runtime_features
                     if isinstance(f, BuildingEmployment))
    assert len(features) == 1
    feature = features[0]
    admission_features = tuple(f for f in inventory.selected.package.definition.runtime_features
                               if isinstance(f, _CONTROLLER_FEATURE_CLASSES))
    _require_controller_feature_evidence(inventory, admission_features)
    def payload(section, key):
        rows = [r for r in inventory.resources if r.section == section and r.key == key]
        assert len(rows) == 1
        return rows[0].entry.data
    validate_panel_resources(feature, game, payload(b'SMNU', b'WSPN'),
                             payload(b'SMNU', b'WSHR'), payload(b'STRT', b'WSHR'))
    registry = resolve_stock_controller_registry(features,
        {feature.panel_key: (int.from_bytes(b'WSPN','little'), int.from_bytes(b'WSHR','little'))},
        list_text_ids={feature.panel_key: LiveAgentListTextIds(0,0,0)})
    assert decode_stock_controller_registry(encode_stock_controller_registry(registry)) == registry
    record = registry.live_agent_lists[0]
    assert record.action_uses_pair
    assert record.gated_control_ids == tuple(sorted(feature.gated_control_ids))
    owner = SemanticMergeResult(tuple(i for s in _parse_inventory_gpl_sources(inventory)
                                     for i in s.items), ())
    generated_counts = {}
    for dataset in ('GPL', 'GPLMx'):
        prefix = 'mx_' if dataset == 'GPLMx' else ''
        root = game/'SDK/OriginalQuests'/dataset/'TaskModules/Characters'
        stock = parse_gpl('\n'.join((root/(prefix+n+'.gpl')).read_text(encoding='cp1252')
                                   for n in ('use_building','travel_to')))
        loader = lambda names: {(i.kind,i.normalized_name):i for i in stock.items
                                 if i.normalized_name in names}
        result = compose_service(owner, features, loader)
        generated = result.items[len(owner.items):]
        assert result.items[:len(owner.items)] == owner.items
        source = '\n'.join(i.text for i in generated) + bridge_source(feature.action_callback_symbol, paired=True)
        with TemporaryDirectory() as temporary:
            compile_gpl(SemanticMergeResult(parse_gpl(source).items,()).emit_project_source_set(),
                        game/'SDK/Gplbcc.exe', Path(temporary)/'compiler', stem='EmploymentCandidate')
        generated_counts[dataset] = len(generated)
    return {'candidate': str(candidate), 'feature': feature.feature_key,
            'hire': feature.open_command_id, 'research_gate': list(record.gated_control_ids),
            'paired_action': record.action_callback_symbol, 'admission': record.admission_callback_symbol,
            'generated_functions': generated_counts, 'profile_built': False, 'native_accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--game', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD'))
    args = parser.parse_args()
    print(json.dumps(check(args.candidate, args.game), indent=2))
