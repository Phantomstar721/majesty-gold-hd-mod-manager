"""Native generated Mod records: shared resources, optional scoped GPL deltas.

No runtime dispatch is involved. Majesty filters these records by quest dataset
and applies them in active-ID order, after the shared record.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
import uuid
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from .gpl import SemanticMergeResult, parse_gpl, parse_dat, _mask_non_code
from .gpl_function_merge import _tokens
from .package import (ModPackage, PackageFormatError, GplLoad, _resolve_package_root,
                      _select_manifest, _select_definition, _parse_manifest, _same_mod_id)

SCOPES = ('Majesty', 'MajestyExpansion')
if TYPE_CHECKING:
    from .compose import GplComposeResult


def scoped_mod_id(common_id, scope):
    if scope not in SCOPES:
        raise ValueError(f'unsupported generated scope: {scope}')
    return '{' + str(uuid.uuid5(uuid.UUID(common_id.strip('{}')),
                               'cam-manager-script-scope-v1:' + scope)) + '}'


def source_items(source_set):
    return (*parse_dat(source_set.dat_text).items, *parse_gpl(source_set.gpl_text).items)


@dataclass(frozen=True)
class ScriptBundle:
    common: GplComposeResult
    patches: tuple[tuple[str, GplComposeResult], ...] = ()

    @property
    def outputs(self):
        return (('Any', self.common), *self.patches)


def partition(base, expansion):
    """Only definitions emitted identically in both validated views are shared.

    A definition omitted from one view belongs solely to the other view. Never
    fill the omission with the opposite scope's body or an empty placeholder.
    Dependencies are closed and validated before partitioning, so common code
    can call a scoped definition only when both effective views supply it.
    """
    left = {i.key: i for i in source_items(base.source_set)}
    right = {i.key: i for i in source_items(expansion.source_set)}
    common = {key for key in left.keys() & right.keys()
              if _tokens(left[key].text) == _tokens(right[key].text)}

    def subset(result, items):
        return replace(result, source_set=SemanticMergeResult(tuple(items), ()).emit_project_source_set())

    patches = tuple((scope, subset(result, (i for key, i in values.items() if key not in common)))
                    for scope, result, values in ((SCOPES[0], base, left), (SCOPES[1], expansion, right))
                    if values.keys() - common)
    return ScriptBundle(subset(base, (i for key, i in left.items() if key in common)), patches)


def audit_scope_dependencies(result, providers, stock):
    """Reject known opposite-scope native references, including callback names.

    Quest/VM names outside our known source inputs remain the engine's domain.
    This is a linkage check, not an attempt to interpret arbitrary GPL code.
    """
    from .standard_scripts import for_dataset
    items = source_items(result.source_set)
    own = {i.key for i in items}
    eligible = for_dataset(providers.inputs, providers.dataset)
    available = {key for p in eligible for key in p.items} | own
    opposite = {key for p in providers.inputs if p not in eligible for key in p.items} - available
    from .gpl import DefinitionKind
    stock_functions = (stock.base_functions if providers.dataset == 'majesty' else stock.expansion_functions)
    stock_expressions = (stock.base_expressions if providers.dataset == 'majesty' else stock.expansion_expressions)
    missing = {name for kind, name in opposite
               if (kind is DefinitionKind.FUNCTION and name not in stock_functions)
               or (kind is DefinitionKind.EXPRESSION and name not in stock_expressions)}
    if not missing:
        return
    for item in items:
        references = {name.lstrip('$') for name in re.findall(
            r'[#$][a-z_][a-z_0-9]*', _mask_non_code(item.text).casefold())}
        bad = sorted(references & missing)
        if bad:
            raise ValueError(f'{providers.dataset}: {item.kind.value}:{item.name} references '
                             'Standard definitions available only in the other dataset: ' + ', '.join(bad))


def load_generated_bundle(root, *, manifest_path=None):
    """Read generated records without relaxing the single-Mod author contract."""
    root = _resolve_package_root(root)
    manifest = _select_manifest(root, manifest_path)
    payload = manifest.read_bytes()
    if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise PackageFormatError('generated manifest DTD/entity declarations are not allowed')
    try:
        document = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise PackageFormatError(f'invalid generated manifest: {exc}') from exc
    nodes = document.findall('./Mod')
    if (document.tag != 'Majesty' or not 1 <= len(nodes) <= 3
            or list(document) != nodes or document.findall('.//Mod') != nodes):
        raise PackageFormatError('generated manifest must contain one common Mod and at most two patches')
    definition = _select_definition(root, None)
    if definition is None or definition.schema_version != 2:
        raise PackageFormatError('generated bundle requires its schema-version 2 definition')
    packages = []
    scopes = []
    for index, node in enumerate(nodes):
        metadata = _parse_manifest(root, manifest, selected_mod_id=node.get('id', ''), allow_strings=True)
        if len(metadata.datasets) != 1 or len(metadata.datasets[0].loads) != 1:
            raise PackageFormatError('generated Mod must have exactly one Dataset/Load')
        scope = metadata.datasets[0].base
        if index == 0:
            if scope != 'Any' or not _same_mod_id(metadata.mod_id, definition.mod_id):
                raise PackageFormatError('generated common Mod must match its definition and use Any')
        else:
            if scope not in SCOPES or scope in scopes:
                raise PackageFormatError('generated patch scope is invalid or duplicated')
            if not _same_mod_id(metadata.mod_id, scoped_mod_id(definition.mod_id, scope)):
                raise PackageFormatError('generated patch ID does not match its common profile and scope')
            load = metadata.datasets[0].loads[0]
            if len(load.directives) != 1 or not isinstance(load.directives[0], GplLoad):
                raise PackageFormatError('generated dataset patch may contain only one GPL load')
        scopes.append(scope)
        load = metadata.datasets[0].loads[0]
        if len(load.gpl) > 1:
            raise PackageFormatError('generated Mod has multiple GPL targets')
        for gpl in load.gpl:
            target = 'Data/Merged.bcd' if scope == 'Any' else f'Data/Merged-{scope}.bcd'
            prefix = 'GPL/' if scope == 'Any' else f'GPL/{scope}/'
            if gpl.target.relative_path.replace('\\', '/') != target:
                raise PackageFormatError('generated GPL target is not owned by its scope')
            sources = [s.relative_path.replace('\\', '/') for s in gpl.sources]
            expected = [prefix + name for name in ('Merged.dat', 'Merged.gpl') if prefix + name in sources]
            if not sources or sources != expected:
                raise PackageFormatError('generated GPL sources are not unique, data-first scope-owned files')
        packages.append(ModPackage(root, manifest, metadata, definition if index == 0 else None))
    if scopes != ['Any', *(scope for scope in SCOPES if scope in scopes)]:
        raise PackageFormatError('generated patches are not in canonical active order')
    return tuple(packages)
