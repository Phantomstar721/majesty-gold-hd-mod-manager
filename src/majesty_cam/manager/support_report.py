"""Bounded, explicit support export. No scanning, upload, saves or game binaries."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
from datetime import datetime, timezone
from ..version import MANAGER_VERSION

LIMIT = 1024 * 1024
TOTAL = 8 * LIMIT


def identity(path):
    path = Path(path)
    result = {'path': str(path)}
    try:
        size = path.stat().st_size
        result['size'] = size
        if size > 128 * LIMIT:
            result['error'] = 'over identity size limit'
        else:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(LIMIT), b''):
                    digest.update(block)
            result['sha256'] = digest.hexdigest()
    except OSError as exc:
        result['error'] = type(exc).__name__
    return result


def record_launch(paths, active_ids, names):
    """Best effort; cannot prevent launch or change a prepared profile."""
    try:
        root = paths.runtime_root
        value = {'schema': 1, 'time_utc': datetime.now(timezone.utc).isoformat(),
                 'manager_version': MANAGER_VERSION,
                 'game': identity(paths.game_executable), 'runtime': identity(paths.runtime_dll),
                 'active_mods': [{'id': str(i), 'name': names.get(i, '')} for i in active_ids],
                 'prepared_report': identity(paths.merged_output_root / 'CAM-MERGE-REPORT.json')}
        data = json.dumps(value, indent=2).encode('utf-8')
        if len(data) > 128 * 1024:
            return
        target = root / 'manager-launch.json'
        for previous, next_ in (('manager-launch.json.1', 'manager-launch.json.2'),
                                 ('manager-launch.json', 'manager-launch.json.1')):
            if (root / previous).is_file():
                (root / previous).replace(root / next_)
        target.write_bytes(data)
    except OSError:
        pass


def record_error(paths, message, details):
    try:
        target = paths.runtime_root / 'manager-error.txt'
        if target.exists():
            target.replace(target.with_name('manager-error.txt.1'))
        target.write_text((datetime.now(timezone.utc).isoformat()+'\n'+message+'\n'+details)[-65536:], encoding='utf-8')
    except OSError:
        pass


def export_report(paths, destination):
    """Only known text artifacts; explicitly disclose missing/oversize inputs."""
    destination = Path(destination)
    inputs = []
    for suffix in ('', '.1', '.2', '.fault', '.fault.1', '.fault.2'):
        inputs.append(('runtime/MajestyBuildingRuntime.log'+suffix,
                       paths.runtime_root / ('MajestyBuildingRuntime.log'+suffix), LIMIT))
    for suffix in ('', '.1', '.2'):
        inputs.append(('launch/manager-launch.json'+suffix,
                       paths.runtime_root / ('manager-launch.json'+suffix), 128*1024))
    for suffix in ('', '.1'):
        inputs.append(('manager/manager-error.txt'+suffix, paths.runtime_root / ('manager-error.txt'+suffix), 256*1024))
    inputs.append(('current/CAM-MERGE-REPORT.json',
                   paths.merged_output_root / 'CAM-MERGE-REPORT.json', LIMIT))
    # Never overwrite a source or read an arbitrary archive tree.
    if destination.resolve() in {p.resolve() for _, p, _ in inputs}:
        raise ValueError('Choose a separate ZIP file for the support report.')
    inventory = {'schema': 1, 'time_utc': datetime.now(timezone.utc).isoformat(),
                 'manager_version': MANAGER_VERSION, 'files': [],
                 'current_game': identity(paths.game_executable),
                 'current_runtime': identity(paths.runtime_dll),
                 'notice': 'Current identities may differ from the captured launch. Paths and mod names may contain personal information. No saves, binary files or automatic upload.'}
    used = 0
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path, limit in inputs:
            entry = {'name': name}
            try:
                with path.open('rb') as stream:
                    data = stream.read(limit+1)
                if len(data) > limit or used+len(data) > TOTAL:
                    entry['status'] = 'omitted: size limit'
                else:
                    archive.writestr(name, data)
                    entry.update(status='included', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                    used += len(data)
            except OSError as exc:
                entry['status'] = 'unavailable: '+type(exc).__name__
            inventory['files'].append(entry)
        archive.writestr('REPORT.json', json.dumps(inventory, indent=2))
    return destination
