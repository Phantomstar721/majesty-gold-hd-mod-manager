"""Opt-in launch settings and read-only, build-guarded window QoL preflight.

These settings never alter MajXPrefs or a prepared mod/profile. Native guards
are checked again before Majesty's main thread resumes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import tempfile
import xml.etree.ElementTree as ET

from ..engine_module import pe, rva_offset
from .profile import default_profile_path

ENVIRONMENT = {'borderless-window': 'MAJESTY_MANAGER_BORDERLESS_WINDOW',
               'cursor-confinement': 'MAJESTY_MANAGER_CURSOR_CONFINEMENT'}
SHORTCUT = 'Ctrl+Shift+F11'
ABI_MARKER = b'WindowQoL ABI 1'
_STOCK_UI_ROOTS = {'$(MajestyDataPath)': 'Data', '$(MajestyExpansionDataPath)': 'DataMX'}
_XML_ENCODING = re.compile(rb'<\?xml\s[^?]*\bencoding\s*=')


def settings_path():
    return default_profile_path().parent / 'window-qol.json'


def _key(executable):
    return str(Path(executable).resolve()).replace('\\', '/').casefold()


def _read(path):
    try:
        value = json.loads(Path(path).read_bytes())
    except FileNotFoundError:
        return {'schema': 1, 'installs': {}}
    if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('installs'), dict):
        raise ValueError('Invalid window QoL settings; restore window-qol.json or remove it to use defaults.')
    return value


def options(executable, path=None):
    value = _read(path or settings_path())['installs'].get(_key(executable), {})
    if not isinstance(value, dict) or any(type(v) is not bool for k, v in value.items() if k in ENVIRONMENT):
        raise ValueError('Window QoL options must be true or false.')
    return {key: value.get(key, False) for key in ENVIRONMENT}


def change(executable, key, enabled, path=None):
    if key not in ENVIRONMENT or type(enabled) is not bool:
        raise ValueError('Unknown window QoL option.')
    path = Path(path or settings_path())
    document = _read(path)
    current = options(executable, path)
    current[key] = enabled
    document['installs'][_key(executable)] = current
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='window-qol-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(document, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _fnv(data):
    result = 2166136261
    for byte in data:
        result = ((result ^ byte) * 16777619) & 0xffffffff
    return result


def verify(executable, root, branch):
    rows = json.loads((Path(root) / 'profiles/window-qol.json').read_bytes())['profiles']
    if branch not in rows:
        raise ValueError('Window options require a supported Majesty executable.')
    row = rows[branch]
    data = Path(executable).read_bytes()
    pe(data)  # Explicit x86, image-base and backed-section validation.
    def at(rva, size):
        offset = rva_offset(data, rva, size)
        return data[offset:offset + size]
    if _fnv(at(row['creationRva'], row['creationSize'])) != row['creationFnv']:
        raise ValueError('The native window-creation code differs from its verified profile.')
    for rva, content in (('windowedPreferenceGuardRva', 'windowedPreferenceGuard'),
                         ('mainWindowGuardRva', 'mainWindowGuard')):
        expected = bytes.fromhex(row[content])
        if at(row[rva], len(expected)) != expected:
            raise ValueError('The native window ownership/display preference code differs from its verified profile.')
    # Independent literal token tables in each fixture substantiate the packed
    # conservative SMNU check. This does not claim a portable gameplay key route.
    for name, code in (('F11', 0xE01A), ('SHIFT', 4), ('CONTROL', 8)):
        address, value = struct.unpack('<II', at(row['shortcutTokenRecords'][name], 8))
        if value != code or at(address - 0x400000, len(name) + 1) != name.encode() + b'\0':
            raise ValueError('The native shortcut token table differs from its verified profile.')
    if row['gogClipRva'] and _fnv(at(row['gogClipRva'], row['gogClipSize'])) != row['gogClipFnv']:
        raise ValueError('The native GOG cursor owner differs from its verified profile.')
    for token, value in (('F11', 0xE01A), ('SHIFT', 4), ('CONTROL', 8)):
        pointer, code = struct.unpack('<II', at(row['shortcutTokenRecords'][token], 8))
        if code != value or at(pointer - 0x400000, len(token) + 1) != token.encode() + b'\0':
            raise ValueError('The native cursor shortcut token mapping differs from its verified profile.')
    return row


def runtime_available(root):
    from .edition import panel_alpha
    path = Path(root) / ('payload/panel-engine/runtime' if panel_alpha() else 'payload/runtime') / 'MajestyBuildingRuntime.dll'
    return path.is_file() and ABI_MARKER in path.read_bytes()


class _ManifestTree(ET.TreeBuilder):
    def doctype(self, name, public_id, system_id):
        raise ValueError('Manifest DTD/entity declarations are not allowed.')


def _shortcut_manifest(raw):
    try:
        return ET.fromstring(raw, parser=ET.XMLParser(target=_ManifestTree()))
    except ET.ParseError:
        if raw.startswith(b'\xef\xbb\xbf') or b'\x00' in raw or _XML_ENCODING.match(raw):
            raise
        # Legacy quests sometimes contain Windows-1252 prose without an XML
        # encoding declaration. Preserve valid UTF-8 and its parse errors.
        try:
            raw.decode('utf-8')
        except UnicodeDecodeError:
            return ET.fromstring(raw, parser=ET.XMLParser(encoding='windows-1252', target=_ManifestTree()))
        raise


def _ui_resources(game, manifest):
    from ..package import _local_name, _resolve_relative_file

    tree = _shortcut_manifest(manifest.read_bytes())
    package_root = manifest.parent.resolve()
    for load in tree.iter():
        if _local_name(load.tag) != 'Load':
            continue
        for node in load:
            if _local_name(node.tag) not in ('CAM', 'Interface'):
                continue
            targets = [child for child in node if _local_name(child.tag) == 'Target']
            path = (node.text or '').strip()
            if len(targets) > 1 or (targets and path):
                raise ValueError('Ambiguous UI resource declaration.')
            if targets:
                path = (targets[0].text or '').strip()
            if not path:
                continue
            marker, separator, tail = path.replace('\\', '/').partition('/')
            root = package_root
            if marker.startswith('$('):
                if not separator or marker not in _STOCK_UI_ROOTS:
                    raise ValueError(f'Unsupported UI resource path {path!r}.')
                root = (game / _STOCK_UI_ROOTS[marker]).resolve()
                root.relative_to(game)
                path = tail
            yield _resolve_relative_file(root, path, 'UI resource').absolute_path


def binding_conflict(game, manifests=()):
    """Conservative one-shot check; no per-frame parsing or unit/order reads.

    Check all language slots, including inactive resource variants. A possible
    conflict frees the cursor instead of replacing a game's authored shortcut.
    OS registration additionally detects conflicting registered hotkeys.
    """
    from ..cam import MAGIC, HEADER_SIZE, read_cam
    game = Path(game).resolve()
    files = {game / 'Data/textdata.cam', game / 'DataMX/mx_textdata.cam'}
    for manifest in sorted(set(map(Path, manifests))):
        try:
            files.update(_ui_resources(game, manifest))
        except (LookupError, OSError, ValueError, ET.ParseError) as exc:
            raise ValueError(f'Cannot check the cursor shortcut in {manifest.name}: {exc}') from exc
    packed = struct.pack('<I', 0x000CE01A)
    text_binding = re.compile(rb'\bKEY(?:_[A-Z0-9]+)?\b[^\r\n]{0,256}', re.I)
    for file in sorted(files):
        if not file.is_file():
            # Expansion text is optional only in a non-expansion installation.
            if file == game / 'DataMX/mx_textdata.cam':
                continue
            raise ValueError('Cannot check the cursor shortcut: missing ' + str(file))
        if file.suffix.casefold() == '.cam':
            # Art/sound-only CAMs need no body read or parse. Reuse the CAM's
            # literal section directory, then the existing parser for UI CAMs.
            with file.open('rb') as stream:
                header = stream.read(HEADER_SIZE)
                if len(header) != HEADER_SIZE or header[:len(MAGIC)] != MAGIC:
                    raise ValueError('Cannot check the cursor shortcut: invalid CAM header in ' + file.name)
                count = struct.unpack_from('<I', header, len(MAGIC))[0]
                if count > (file.stat().st_size - HEADER_SIZE) // 8:
                    raise ValueError('Cannot check the cursor shortcut: invalid CAM directory in ' + file.name)
                directory = stream.read(count * 8)
                if not any(directory[n:n + 4] in (b'SMNU', b'DATA') for n in range(0, len(directory), 8)):
                    continue
            raw = file.read_bytes()
            blocks = [entry.data for section in read_cam(raw).sections
                      if section.extension in (b'SMNU', b'DATA') for entry in section.entries]
        else:
            blocks = [file.read_bytes()]
        for block in blocks:
            if packed in block:
                return file
            for match in text_binding.finditer(block):
                words = set(re.findall(rb'[A-Z0-9]+', match.group().upper()))
                if b'F11' in words and b'SHIFT' in words and words & {b'CTRL', b'CONTROL', b'CTL', b'CNTRL'}:
                    return file
    return None


def configure(environment, paths, branch, manifests=()):
    for variable in ENVIRONMENT.values():
        environment.pop(variable, None)  # No inherited opt-in or stale flag.
    selected = options(paths.game_executable, paths.profile_path.parent / 'window-qol.json')
    warnings = []
    if any(selected.values()):
        verify(paths.game_executable, paths.repo_root, branch.key if branch else None)
        if ABI_MARKER not in paths.runtime_dll.read_bytes():
            raise ValueError('The window options require the matching updated Manager runtime.')
        if selected['cursor-confinement']:
            try:
                conflict = binding_conflict(paths.game_path, manifests)
                if conflict:
                    raise ValueError(f'{SHORTCUT} may already be bound in {conflict.name}.')
            except (OSError, ValueError, ET.ParseError) as exc:
                selected['cursor-confinement'] = False
                warnings.append(f'Cursor confinement is off for this launch: {exc}')
    for key, enabled in selected.items():
        environment[ENVIRONMENT[key]] = '1' if enabled else '0'
    return tuple(warnings)
