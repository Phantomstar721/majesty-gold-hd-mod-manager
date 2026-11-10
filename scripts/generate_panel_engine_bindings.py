"""Assemble the reviewed three-build SDK API bindings from their owner evidence.

No scans or native calls occur here. Missing, conflicting or unreviewed bindings
fail instead of borrowing a Public or beta offset. Source SDK remains private.
"""
import argparse
import hashlib
import json
from pathlib import Path

from panel_engine_profile_sources import ROOT, BRANCHES, manager_profiles, map_query_profiles
from panel_engine_existing_profiles import existing_boundaries


DEFAULT_SDK = ROOT.parent / '.audits/flamey-window-engine-sdk-20261109/sdk'
DEFAULT_INVENTORY = ROOT / 'profiles/panel-engine/sdk-inventory.json'


def generate(inventory_path=DEFAULT_INVENTORY):
    inventory = json.loads(inventory_path.read_bytes())
    sources = existing_boundaries()
    by_public = {}
    for item in sources:
        by_public.setdefault(item['profiles']['public'], []).append(item)
    reports = {}
    def report(name):
        if name not in reports:
            reports[name] = json.loads((ROOT / 'profiles/panel-engine' / (name + '.json')).read_bytes())
        return reports[name]
    overrides = {}
    def add(public, name, path, selector, alias=False):
        rows = report(path)['profiles']
        values = {}
        for branch in BRANCHES:
            value = rows[branch]
            for key in selector:
                value = value[key]
            if not isinstance(value, int):
                raise ValueError('API evidence is not a native address: ' + name)
            values[branch] = value
        if not alias and values['public'] != public:
            raise ValueError('Public SDK source anchor differs: ' + name)
        overrides[public] = {'profiles': values, 'source': 'profiles/panel-engine/' + path + '.json',
                             'field': name, 'alias': alias}
    add(0x628240, 'YSTRING_SET', 'data-clients', ('narrowAssign','va'))
    add(0x562ea0, 'GDH_RESET', 'provider-clients', ('va',))
    for name, address, key in (('STATS_CTOR',0x4aea20,'statsWindow'), ('BUILDING_CTOR',0x495b10,'basicBuilding'),
                               ('LIST_CTOR',0x498f80,'unitList')):
        add(address, name, 'constructors', ('constructors',key,'va'))
    add(0x42a1f0, 'WINDOW_ID', 'navigation', ('windowIdVA',))
    for name, address, key in (('AGENT_BY_ID',0x55e8e0,'lookupAgentVA'), ('AGENT_UNIT',0x55f2c0,'associatedUnitVA')):
        add(address, name, 'agent-clients', (key,))
    for name, address, client, key in (
            ('GUILD_RECRUIT',0x4967a0,'recruitment','va'),
            ('STR_TEXT',0x562c10,'stringArgument','textGetterVA'),
            ('AGENTREF_SET',0x553fe0,'agentReturn','assignReferenceVA'),
            ('LIST_CTOR',0x4201a0,'recruitment','listConstructorVA'),
            ('LIST_DTOR',0x41fc30,'recruitment','listDestructorVA'),
            ('LIST_SET',0x6639d0,'buildingInput','listSetVA'),
            ('FLAG_MAKE',0x4db520,'agentReturn','flagMakeVA')):
        add(address, name, 'sdk-clients', ('clients',client,key))
    ui = report('ui-providers')['profiles']['public']['providers']
    for name, row in ui.items():
        public_address = 0x65cff0 if name == 'ADD_ROW' else row['va']
        add(public_address, name, 'ui-providers', ('providers',name,'va'), alias=name == 'ADD_ROW')
    components = {}
    for component, definition in inventory.items():
        functions = {}
        for binding in definition['macros']:
            if binding['category'] != 'native-function':
                continue
            public = int(binding['hex_values'][0], 16)
            evidence = overrides.get(public)
            if evidence is None:
                choices = by_public.get(public, ())
                if len({tuple(choice['profiles'][b] for b in BRANCHES) for choice in choices}) != 1:
                    raise ValueError('Missing/conflicting three-build API: ' + component + '/' + binding['name'])
                evidence = choices[0]
            functions[binding['name']] = evidence
        components[component] = {'sdkSource': definition['source'], 'sdkSha256': definition['sha256'], 'functions': functions}
    m, queries = manager_profiles(), map_query_profiles()
    extra = {}
    for branch in BRANCHES:
        v = report('vtables')['profiles'][branch]['classes']
        extra[branch] = {'integerVtable': v['gplInteger']['va'], 'listVtable': v['unitList']['va'],
            'cameraGlobal': report('ui-providers')['profiles'][branch]['clients']['cameraFrame']['cameraGlobalVA'],
            'systemAlertGlobal': 0x400000 + int(m[branch]['systemAlertOwnerRva'],0),
            'runtimeGlobal': 0x400000 + queries[branch]['worldGlobal'],
            'unitCatalog': next(item['profiles'][branch] for item in sources if item['source']=='runtime/AttackObservationNativeProfiles.h' and item['field']=='unitCatalog'),
            'boardExtents': 0x400000 + queries[branch]['boardExtents'],
            'listCopy': report('sdk-clients')['profiles'][branch]['clients']['recruitment']['listCopyVA'],
            'placeBuilding': report('sdk-clients')['profiles'][branch]['clients']['buildingInput']['placeBuildingVA'],
            'scriptContinuation': report('hook-sites')['profiles'][branch]['scriptRegistrationTail']['targetVA']}
    return {'schema':1, 'serviceRevision':1, 'ownershipABI':1,
            'components':components, 'extra':extra,
            'reports': {name:hashlib.sha256((ROOT/'profiles/panel-engine'/(name+'.json')).read_bytes()).hexdigest() for name in sorted(reports)},
            'limits':'Fixed native API boundaries and reviewed normal caller/data contracts; no claim of recovered actor/VM/driver/exception implementations.'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    result=generate()
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
