"""Whole-script interception at the stock terminal missile impact boundary."""
from dataclasses import asdict, dataclass
import hashlib
import re
import struct
from pathlib import Path
from .gpl import DefinitionKind
from .spell_policy import signature

FEATURE_TYPE = 'stock.projectile-interception.v1'
CAPABILITY = 'manager.projectile-interception.v1'
OBSERVATION_CAPABILITY = 'manager.attack-projectile-observation.v1'
RELATIVE_PATH = 'DataMX/majesty_mod_manager_projectile_interception.bin'
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}\Z')
_DESCRIPTION = re.compile(r'[\x20-\x7e]{1,128}\Z')
AUDITED_IMAGES = frozenset((
    '255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4',
    '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82',
    '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792',
))

def require_exact_profile(executable):
    """Admit the supported build and consumed code, not unrelated file bytes."""
    from .manager.qol_service import detect_majesty_branch
    from .native_impact_profiles import PROFILES
    try:
        path = Path(executable)
        branch = detect_majesty_branch(path)
        if branch is None or branch.key not in PROFILES:
            raise ValueError('Native projectile interception requires a supported Majesty executable build')
        data = path.read_bytes()
    except (OSError, TypeError):
        raise ValueError('Cannot read the Majesty executable for projectile interception') from None
    for address, size, expected in PROFILES[branch.key]['bodies']:
        rva = address - 0x400000
        section = next((s for s in branch.stock_sections
                        if s.rva <= rva and rva + size <= s.rva + s.raw_size), None)
        if section is None:
            raise ValueError('Projectile interception code is outside the supported executable layout')
        offset = section.raw_offset + rva - section.rva
        body = data[offset:offset + size]
        if len(body) != size or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(f'Projectile interception requires unchanged native code at 0x{address:08X}; another executable patch changes this specific helper')

@dataclass(frozen=True)
class ProjectileInterception:
    feature_key: str
    callback_symbol: str
    direct_projectile_callbacks: tuple[str, ...]
    physical_projectile_callbacks: tuple[str, ...]
    area_or_periodic_projectile_callbacks: tuple[str, ...]
    other_exempt_projectile_callbacks: tuple[str, ...]
    type: str = FEATURE_TYPE

def parse_feature(value):
    if not isinstance(value, dict) or set(value) != set(ProjectileInterception.__dataclass_fields__) or value.get('type') != FEATURE_TYPE:
        raise ValueError('projectile interception requires its exact versioned fields')
    value = dict(value)
    if not isinstance(value['feature_key'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', value['feature_key']):
        raise ValueError('projectile interception feature_key is invalid')
    callback = value['callback_symbol']
    if not isinstance(callback, str) or not _NAME.fullmatch(callback) or callback.casefold().startswith('mm_'):
        raise ValueError('projectile interception callback is invalid')
    groups = []
    for field in (k for k in value if k.endswith('_callbacks')):
        names = value[field]
        if not isinstance(names, (list, tuple)) or len(names) > 512 or any(not isinstance(n, str) or not _NAME.fullmatch(n) for n in names):
            raise ValueError('projectile interception classification requires bounded callback names')
        keys = {n.casefold() for n in names}
        if len(keys) != len(names):
            raise ValueError('duplicate projectile classification')
        groups.append(keys)
        value[field] = tuple(names)
    if sum(map(len, groups)) != len(set().union(*groups)):
        raise ValueError('conflicting projectile classifications')
    return ProjectileInterception(**value)

def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    return {k: list(v) if isinstance(v, tuple) else v for k, v in value.items()}

def selected(inventories):
    return any(isinstance(f, ProjectileInterception) for i in inventories
               for f in getattr(getattr(getattr(i.selected, 'package', None), 'definition', None), 'runtime_features', ()))

@dataclass(frozen=True, order=True)
class ImpactBinding:
    provider: str
    projectile: str
    resource_id: int
    script: str

def resolve(features, descriptions, functions, *, stock_functions=None):
    """Resolve effective descriptors, not edits to each impact function body.

    Unclassified/unsupported carriers stay on stock handling. An included
    callback with an incompatible ABI is a real declaration error.
    """
    features, descriptions = tuple(features), tuple(descriptions)
    functions = {f.normalized_name: f for f in functions if f.kind is DefinitionKind.FUNCTION}
    if stock_functions is not None:
        direct = {n.casefold() for f in features for n in f.direct_projectile_callbacks}
        missing = set()
        for record in descriptions:
            element = record.to_element()
            if element.get('type') != 'Unit' or element.get('subType') != 'Projectile':continue
            for script in element.findall('./Engine/Script'):
                name = script.get('GPLFunction', '')
                if name.casefold() in direct and name.casefold() not in functions:missing.add(name)
        if missing:
            functions.update({key[1]: item for key, item in stock_functions(tuple(sorted(missing))).items()})
    result = set()
    for feature in features:
        feature_mapping(feature)
        provider = functions.get(feature.callback_symbol.casefold())
        if provider is None:
            raise ValueError('missing projectile provider: ' + feature.callback_symbol)
        signature(provider, ('agent', 'agent'), 'boolean')
        direct = {s.casefold() for s in feature.direct_projectile_callbacks}
        for record in descriptions:
            element = record.to_element()
            if element.get('type') != 'Unit' or element.get('subType') != 'Projectile':
                continue
            scripts = element.findall('./Engine/Script')
            if len(scripts) != 1:
                continue
            script = scripts[0]
            name = script.get('GPLFunction', '')
            if name.casefold() not in direct or script.get('cProc') != '0' or script.get('type') != '0' or name.casefold() == 'make_attack':
                continue
            function = functions.get(name.casefold())
            if function is None:
                raise ValueError('missing effective projectile callback: ' + name)
            signature(function, ('agent', 'agent'), '')
            resource = element.get('ID', '')
            if len(resource) != 4 or not resource.isascii():
                raise ValueError('projectile has no four-byte resource ID: ' + element.get('Name', ''))
            result.add(ImpactBinding(feature.callback_symbol, element.get('Name', ''),
                                     int.from_bytes(resource.encode('ascii'), 'little'), name))
    return tuple(sorted(result))

def resolve_bundle(game_path, inventories, bundle, descriptions, description_patches):
    """Resolve the same effective dataset views emitted by production composition."""
    from .compose import _parse_inventory_gpl_sources, _load_effective_stock_descriptions, _feature_stock_functions
    from .gpl import parse_gpl
    features = tuple(f for i in inventories for f in i.selected.package.definition.runtime_features
                     if isinstance(f, ProjectileInterception))
    if not features:
        return ()
    for inventory in inventories:
        for feature in inventory.selected.package.definition.runtime_features:
            if not isinstance(feature, ProjectileInterception):
                continue
            own = [item for source in _parse_inventory_gpl_sources(inventory) for item in source.items
                   if item.kind is DefinitionKind.FUNCTION and item.normalized_name == feature.callback_symbol.casefold()]
            if not own:
                raise ValueError('projectile provider must be package-owned: ' + feature.callback_symbol)
            for item in own:
                signature(item, ('agent', 'agent'), 'boolean')
    common = parse_gpl(bundle.common.source_set.gpl_text or '').items
    patches = dict(bundle.patches)
    result = set()
    for scope in ('Majesty', 'MajestyExpansion'):
        functions = (*common, *parse_gpl(patches[scope].source_set.gpl_text or '').items) if scope in patches else common
        records = {k: v[0] for k, v in _load_effective_stock_descriptions(game_path, scope.casefold()).items()}
        records.update(descriptions.document.index)
        if scope.casefold() in description_patches:
            records.update(description_patches[scope.casefold()].document.index)
        result.update(resolve(features, tuple(records.values()), functions,
            stock_functions=lambda names, scope=scope: _feature_stock_functions(game_path,names,dataset=scope.casefold())))
    if not result:
        raise ValueError('projectile interception has no supported effective missile bindings')
    return tuple(sorted(result))


def encode(bindings, proof):
    bindings = tuple(sorted(set(bindings)))
    if not bindings or len(bindings) > 1024:
        raise ValueError('projectile interception requires 1..1024 effective bindings')
    chunks = [struct.pack('<4sII', b'MMIP', 1, len(bindings)), hashlib.sha256(proof).digest()]
    for b in bindings:
        if not 0 < b.resource_id <= 0xFFFFFFFF:
            raise ValueError('invalid projectile resource ID')
        chunks.append(struct.pack('<I', b.resource_id))
        for name, pattern in ((b.provider, _NAME), (b.projectile, _DESCRIPTION), (b.script, _NAME)):
            if not isinstance(name, str) or not pattern.fullmatch(name):
                raise ValueError('invalid projectile binding name')
            raw = name.encode('ascii');chunks.extend((struct.pack('<I', len(raw)), raw))
    return b''.join(chunks)

def decode(data, proof):
    if len(data) < 44 or data[:4] != b'MMIP':
        raise ValueError('invalid projectile interception registry')
    version, count = struct.unpack_from('<II', data, 4)
    if version != 1 or not 1 <= count <= 1024 or data[12:44] != hashlib.sha256(proof).digest():
        raise ValueError('projectile registry does not match its output proof')
    pos = 44;rows = []
    def word():
        nonlocal pos
        if pos + 4 > len(data):raise ValueError('truncated projectile registry')
        value, = struct.unpack_from('<I', data, pos);pos += 4;return value
    for _ in range(count):
        resource = word();names = []
        for index in range(3):
            size = word()
            if not 1 <= size <= (128 if index==1 else 64) or pos+size > len(data):raise ValueError('truncated projectile name')
            names.append(data[pos:pos+size].decode('ascii'));pos += size
        rows.append(ImpactBinding(names[0], names[1], resource, names[2]))
    if pos != len(data) or encode(rows, proof) != data:
        raise ValueError('projectile registry is not canonical')
    return tuple(rows)
