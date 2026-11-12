"""Pinned updated SDK inputs and explicit owner-evidence bindings.

This is a separate source contract: the accepted legacy SDK inventory and
release payload remain reproducible. No source revision is admitted by title,
date, directory layout or a matching service ID.
"""
import hashlib
import json
from pathlib import Path
import re

from generate_panel_engine_bindings import generate
from panel_engine_profile_sources import ROOT, BRANCHES

SDK_ROOT = ROOT.parent/'.audits/flamey-sdk-update-20261111/sdk/Custom building side-panel and scripted ground-targeting engine SDK'
SOURCE_PINS = {
    'src/we_engine.cpp':'440f35c579d3af10392b955bf77ec916ba845776732a9617f10f72acd5f1325b',
    'src/sf_functions.cpp':'fdcd3cd2c13b8cc50c43a5219a62f05896dbda7857de6f71becc111d35955b20',
    'src/sf_windows.cpp':'3b2b8338cde7c7719d4dd489d1e2a4cfe9d607a5bf863d7c49a08934c829c60d',
    'src/sf_explore.cpp':'8a0828d771e4d1dcfcff65a59396370a2ca98f2a637e863b25070c70483c50c1',
    'Tools/we_link.py':'648563b4fe9888343f2d7c9cd83f97b2e077650bc048890ec840561d774f1b1e',
}
UNITS = {'window-engine':'src/we_engine.cpp','script-functions':'src/sf_functions.cpp',
         'script-windows':'src/sf_windows.cpp','script-explore':'src/sf_explore.cpp'}


def inventory(sdk=SDK_ROOT):
    result = {}
    for name, digest in SOURCE_PINS.items():
        raw = (sdk/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Updated SDK source identity differs: '+name)
        if name.endswith('.cpp'):
            source = raw.decode('utf8')
            macros = []
            for line, text in enumerate(source.splitlines(),1):
                if not text.startswith('#define '):
                    continue
                code = text.split('//',1)[0].strip()
                macros.append({'line':line, 'code':code})
            result[name] = {'sha256':digest,'normalizedSha256':hashlib.sha256(
                source.replace('\r\n','\n').replace('\r','\n').encode('utf8')).hexdigest(),'macros':macros}
    return result


def bindings(client_report, sdk=SDK_ROOT):
    pins = inventory(sdk)
    legacy = generate()
    by_public = {}
    for component in legacy['components'].values():
        for value in component['functions'].values():
            public = value['profiles']['public']
            if public in by_public and by_public[public]['profiles'] != value['profiles']:
                raise ValueError('Existing native bindings disagree')
            by_public[public] = value
    # Keep the reviewed position-independent aliases, including ADD_ROW whose
    # source address differs from the existing Manager presenter entry.
    old_inventory = json.loads((ROOT/'profiles/panel-engine/sdk-inventory.json').read_bytes())
    for component, rows in old_inventory.items():
        for macro in rows['macros']:
            if macro['category'] == 'native-function':
                by_public[int(macro['hex_values'][0],16)] = legacy['components'][component]['functions'][macro['name']]
    for name, value in client_report['profiles']['public']['providers'].items():
        by_public[value['va']] = {'source':'updated-sdk-clients', 'field':name,
            'profiles':{branch:client_report['profiles'][branch]['providers'][name]['va'] for branch in BRANCHES}}
    units = {}
    for component, path in UNITS.items():
        functions = {}
        source = (sdk/path).read_text(encoding='utf8')
        for name, address in re.findall(r'^#define\s+(\w+)\s+\(\(\w+_t\)(0x[0-9a-fA-F]+)\)',source,re.M):
            address = int(address,16)
            if address not in by_public:
                raise ValueError('Unproved updated native API: '+component+'/'+name)
            functions[name] = by_public[address]
        units[component] = {'sdkSource':path,'sdkSha256':pins[path]['sha256'],
            'normalizedSha256':pins[path]['normalizedSha256'],'functions':functions}
    return {'schema':1,'units':units,'legacy':legacy,
        'extra':{branch:{'virtualSlots':client_report['profiles'][branch]['virtualSlots'],
            'actionCatalogGlobal':client_report['profiles'][branch]['actionCatalogGlobal']}
            for branch in BRANCHES}, 'sourcePins':SOURCE_PINS,
        'limits':'Private integration inputs; not admission of a native module or full gameplay lifecycle.'}


def transform_unit(source, unit, branch, contract, tables):
    from build_panel_engine_modules import transform
    definition = contract['units'][unit]
    if hashlib.sha256(source.encode('utf8')).hexdigest() != definition['normalizedSha256']:
        raise ValueError('Unreviewed updated source passed to adapter')
    legacy = contract['legacy']
    adapted = {**legacy,'components':{**legacy['components']}}
    if unit in ('window-engine','script-functions'):
        adapted['components'][unit] = definition
        if unit == 'window-engine':
            def constant(name, original, replacement):
                nonlocal source
                match = re.compile(r'^(#define\s+'+name+r'\s+)'+re.escape(original)+r'\b',re.M)
                source, count = match.subn(lambda m:m[1]+replacement,source)
                if count != 1:
                    raise ValueError('Updated native constant changed: '+name)
            for name, value in contract['extra'][branch]['virtualSlots'].items():
                public = contract['extra']['public']['virtualSlots'][name]
                constant(name,hex(public),hex(value))
            constant('ACT_LIST_PTR','0x7c545cu',hex(contract['extra'][branch]['actionCatalogGlobal'])+'u')
            hero = [row for row in tables['profiles'][branch]['tables']
                    if row['name'] == '.?AVHeroSpellsController@@']
            if len(hero) != 1:
                raise ValueError('Missing primary spell-panel class')
            constant('VT_HERO_SPELLS','0x73d6e0u',hex(hero[0]['va'])+'u')
        return transform(source,unit,branch,adapted,tables)
    functions = definition['functions']; seen = set()
    def function(match):
        name, type_name = match[1],match[2]
        if name not in functions:
            raise ValueError('Unreviewed updated native macro: '+name)
        seen.add(name)
        return '#define '+name+' (('+type_name+')'+hex(functions[name]['profiles'][branch])+')'
    source = re.sub(r'^#define\s+(\w+)\s+\(\((\w+_t)\)0x[0-9a-fA-F]+\)',function,source,flags=re.M)
    if seen != set(functions):
        raise ValueError('Updated native macro inventory differs')
    # Retain the accepted registration-tail register/flags contract for every
    # added stage, not only for the original SF_Hook at the end of the chain.
    hook = 'Windows' if unit == 'script-windows' else 'Explore'
    old = '        call SF_'+hook+'Register\n        jmp SF_'+('Hook' if hook=='Windows' else 'WindowsHook')
    new = ('        pushfd\n        pushad\n        call SF_'+hook+
           'Register\n        popad\n        popfd\n        jmp SF_'+('Hook' if hook=='Windows' else 'WindowsHook'))
    if source.count(old) != 1:
        raise ValueError('Updated registration-chain source anchor changed')
    return source.replace(old,new)
