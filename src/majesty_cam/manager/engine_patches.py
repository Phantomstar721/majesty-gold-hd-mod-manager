"""Optional native-engine service contracts and explicit QoL actions."""
from ..engine_dependencies import SERVICE_NAMES
from dataclasses import dataclass
from pathlib import Path
from ..engine_dependencies import RequirementEvidence, from_effective_resources
from ..package import (load_standard_component, load_standard_definition,
    parse_mod_definition, _read_mod_definition, _same_mod_id, DEFINITION_FILE_NAME)
from ..cam import read_cam
from .. import engine_module
import hashlib
import json

PATCH_KEYS = {"window-engine.v1": "panel-engine", "script-functions.map-action.v1": "scripted-ground-actions"}

SERVICES={'panel-engine':'window-engine','scripted-ground-actions':'script-functions'}


def executable_path(executable):
    from .edition import panel_alpha
    if panel_alpha():
        from .alpha_executable import current_path
        return current_path(executable)
    return executable


def bundle_root(repo_root):
    from .paths import is_frozen_application
    return (repo_root/'payload/panel-engine/modules' if is_frozen_application()
            else repo_root/'local/panel-engine-alpha/native-modules')


def load_bundle(repo_root,key,branch):
    service=SERVICES[key]
    branch_key='gog' if branch.key.startswith('gog') else branch.key
    root=bundle_root(repo_root)
    index=json.loads((root/'modules.json').read_bytes())
    if index.get('schema')!=1 or index.get('ownershipABI')!=1:
        raise ValueError('Unsupported bundled native engine index')
    name=service+'-'+branch_key
    row=index['modules'][name]
    if row['file']!=name+'.mmne' or row['service']!=service or row['branch']!=branch_key or row['revision']!=1:
        raise ValueError('Bundled native engine index identity differs')
    data=(root/row['file']).read_bytes()
    if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Bundled native engine changed')
    metadata,_=engine_module.decode_bundle(data)
    if metadata['service']!=service or metadata['branch']!=branch_key:raise ValueError('Bundled engine build differs')
    return data,branch_key


def inspect_patch(repo_root,executable,key,branch):
    if branch is None:raise ValueError('Choose a supported Majesty executable')
    bundle,branch_key=load_bundle(repo_root,key,branch)
    data=executable_path(executable).read_bytes()
    # Full dry-run through the exact installer validates the occupied hook,
    # installed revision/relocations, descriptor and available section slot.
    engine_module.install(data,bundle,branch_key)
    header=engine_module.inspect(data,SERVICES[key],branch_key)
    return bool(header and header['active'])


def change_patch(repo_root,executable,key,branch,install,**publish_options):
    from .edition import panel_alpha
    if panel_alpha():
        from .alpha_executable import publish
    else:
        from .engine_executable import publish
    bundle,branch_key=load_bundle(repo_root,key,branch)
    data=executable_path(executable).read_bytes()
    changed=(engine_module.install(data,bundle,branch_key) if install else
             engine_module.remove(data,SERVICES[key],branch_key))
    publish(executable,changed,repo_root=repo_root,**publish_options)


def installed_revisions(repo_root,executable):
    from .qol_service import detect_majesty_branch
    branch=detect_majesty_branch(executable_path(executable))
    result={}
    for service,key in PATCH_KEYS.items():
        native=engine_module.inspect(executable_path(executable).read_bytes(),SERVICES[key])
        if native and inspect_patch(repo_root,executable,key,branch):result[service]=1
    return result


@dataclass(frozen=True)
class DependencyScan:
    evidence: tuple
    unresolved: tuple[str, ...]
    paths: tuple[Path, ...]


def _selected_definition(path, mod_id):
    if not path.is_file():
        return None
    value = _read_mod_definition(path)
    if 'mod_ids' in value:
        identifiers = value['mod_ids']
        if not isinstance(identifiers, list):
            raise ValueError('Standard mod_ids must be an array')
        if not any(isinstance(identifier, str) and _same_mod_id(identifier, mod_id)
                   for identifier in identifiers):
            return None
        return load_standard_definition(path, mod_id)
    identifier = value.get('mod_id')
    if not isinstance(identifier, str) or not _same_mod_id(identifier, mod_id):
        return None
    return parse_mod_definition(value)


def discover(entry):
    """Read one exact manifest component; no directory/text-content scanning."""
    package = load_standard_component(entry.package_root, manifest_path=entry.manifest_path,
                                     mod_id=entry.content_id, recover_project_sources=False)
    paths = [entry.manifest_path, entry.package_root / DEFINITION_FILE_NAME]
    definition = _selected_definition(paths[-1], entry.content_id)
    evidence, unknown = [], []
    for dataset in package.datasets:
        effective = {}
        for load in dataset.loads:
            for cam in load.cams:
                paths.append(cam.absolute_path)
                for section in read_cam(cam.absolute_path).sections:
                    if section.extension not in (b"SMNU", b"STRT"):
                        continue
                    for record in section.entries:
                        effective[section.extension, record.name[:4]] = record.data
            for gpl in load.gpl:
                paths.append(gpl.target.absolute_path)
                unknown.append("Native GPL call metadata is not yet verified for " + gpl.target.relative_path)
        if definition is not None:
            evidence.extend(RequirementEvidence(r, entry.content_id, entry.display_name,
                dataset.base, "explicit external_patches declaration") for r in definition.external_patches)
        evidence.extend(from_effective_resources(effective, owner_id=entry.content_id,
            owner_name=entry.display_name, dataset=dataset.base))
    return DependencyScan(tuple(evidence), tuple(unknown), tuple(dict.fromkeys(paths)))


def signature(paths):
    result = []
    for path in paths:
        try:
            stat = path.stat()
            result.append((str(path), stat.st_size, stat.st_mtime_ns))
        except FileNotFoundError:
            result.append((str(path), None, None))
    return tuple(result)
