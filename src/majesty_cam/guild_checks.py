"""Small offline checks over declared outputs, never a visual/gameplay verdict."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import re
import struct

from .art import parse_stock_imag_tile_references, parse_tile_palette_reference
from .cam import read_cam


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def image_fingerprint(archive, image):
    """Retain frame offsets/flags/timing and pixels; normalize relocation only."""
    def section(kinds):
        found = [s for s in archive.sections if s.extension in kinds]
        if len(found) != 1:
            raise ValueError(f"IMAG/{image.name[:4]!r}: expected one {kinds} table")
        return found[0].entries
    tiles = section((b'TILE',))
    parsed = parse_stock_imag_tile_references(image.data, tile_count=len(tiles), entry_name=image.name)
    normalized = bytearray(image.data)
    frames = []
    for ref in parsed.references:
        tile = bytearray(tiles[ref.tile_index].data)
        if not tile:
            raise ValueError(f"IMAG/{image.name[:4]!r}: empty TILE {ref.tile_index}")
        palette = parse_tile_palette_reference(tile, tile_index=ref.tile_index)
        palette_hash = None
        if palette is not None:
            palettes = section((b'SPLT', b'PALT'))
            if palette.palette_index >= len(palettes) or not palettes[palette.palette_index].data:
                raise ValueError(f"IMAG/{image.name[:4]!r}: missing palette {palette.palette_index}")
            palette_hash = _sha(palettes[palette.palette_index].data)
            struct.pack_into('<I', tile, palette.offset, 0)
        struct.pack_into('<H', normalized, ref.offset, 0)
        frames.append({'set': ref.set_id, 'direction': ref.direction, 'frame': ref.frame,
                       'tile_sha256': _sha(tile), 'palette_sha256': palette_hash})
    return {'metadata_sha256': _sha(normalized), 'frames': frames}


def presentation_snapshot(root: Path, image_ids=(), panel_keys=None):
    """Explicit baseline of registered panels and requested profile/sprite images.

    Snapshotting records expectations; it does not approve the source artwork.
    Additional unrelated panels/images in a later composition are permitted.
    """
    from .scoped_output import load_generated_bundle
    from .stock_controller_registry import CONTROLLER_REGISTRY_RELATIVE_PATH, decode_stock_controller_registry
    package = load_generated_bundle(root)[0]
    archives = [read_cam(c.absolute_path) for c in package.datasets[0].loads[0].cams]
    registry = decode_stock_controller_registry((root / CONTROLLER_REGISTRY_RELATIVE_PATH).read_bytes())
    def one(kind, key):
        matches = [(c, e) for c in archives for s in c.sections if s.extension == kind
                   for e in s.entries if e.name[:4] == key and e.data]
        if len(matches) != 1:
            raise ValueError(f"presentation requires one {kind.decode()}/{key!r}; found {len(matches)}")
        return matches[0]
    panels = {}
    selected = set(panel_keys) if panel_keys is not None else {p.panel_key for p in registry.panels}
    for panel in registry.panels:
        if panel.panel_key not in selected:
            continue
        if panel.panel_key in panels:
            raise ValueError(f"duplicate presentation panel {panel.panel_key}")
        record = {'building_family': panel.building_family_id, 'open_command': panel.open_command_id}
        for role, number in [('primary', panel.parent_dialog_id), ('subpanel', panel.child_dialog_id)]:
            record[role] = {kind.decode(): _sha(one(kind, number.to_bytes(4, 'little'))[1].data)
                            for kind in (b'SMNU', b'STRT')}
        record['research_rows'] = sorted((asdict(r) for r in registry.research_rows
                                          if r.panel_key == panel.panel_key), key=lambda r: r['recipe_key'])
        panels[panel.panel_key] = record
    if selected != set(panels):
        raise ValueError('required presentation panel missing: ' + ', '.join(sorted(selected - set(panels))))
    images = {}
    for key in sorted(set(image_ids)):
        if not isinstance(key, str) or not re.fullmatch(r'[\x21-\x7e]{4}', key):
            raise ValueError('presentation image IDs must be four printable ASCII characters')
        archive, image = one(b'IMAG', key.encode('ascii'))
        images[key] = image_fingerprint(archive, image)
    if not panels and not images:
        raise ValueError('presentation snapshot must select at least one panel or image')
    return {'schema_version': 1, 'panels': panels, 'images': images}


def compare_presentation(expected, actual):
    """Fail only an explicit baseline contract, not an inferred art preference."""
    if not isinstance(expected, dict) or set(expected) != {'schema_version', 'panels', 'images'}:
        raise ValueError('invalid presentation contract fields')
    if expected['schema_version'] != 1 or not all(isinstance(expected[k], dict) for k in ('panels', 'images')):
        raise ValueError('unsupported presentation contract schema')
    if not expected['panels'] and not expected['images']:
        raise ValueError('empty presentation contract')
    for group in ('panels', 'images'):
        for key, value in expected[group].items():
            if key not in actual[group]:
                raise ValueError(f'presentation contract: required {group}/{key} missing')
            if value != actual[group][key]:
                fields = sorted(k for k in value.keys() | actual[group][key].keys()
                                if value.get(k) != actual[group][key].get(k)) if isinstance(value, dict) else ['record']
                raise ValueError(f'presentation contract: {group}/{key} changed ({", ".join(fields)})')


# Preserve string tokens so a quoted slash or && cannot become an operator.
_LEX = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
                  r"[A-Za-z_][A-Za-z0-9_]*|\d+|&&|\|\||[^\s]", re.MULTILINE)


def gpl_guard_warnings(text: str, source: str):
    """Bounded syntactic advisory, no dataflow/type/null-safety assertion."""
    tokens = [m for m in _LEX.finditer(text) if not m.group().startswith(('//', '/*'))]
    findings = []
    for i, token in enumerate(tokens[:-1]):
        if token.group().casefold() not in ('if', 'while') or tokens[i+1].group() != '(':
            continue
        depth, end = 1, i+2
        while end < len(tokens) and depth:
            depth += (tokens[end].group() == '(') - (tokens[end].group() == ')')
            end += 1
        if depth:
            continue  # Existing GPL parser owns malformed source errors.
        condition = [t.group() for t in tokens[i+2:end-1]]
        logical = next((j for j, t in enumerate(condition) if t in ('&&', '||')), None)
        if logical is None:
            continue
        rhs = condition[logical+1:]
        left = condition[:logical]
        def canonical(items):
            return [t if t.startswith('"') else t.casefold() for t in items]
        left, rhs = canonical(left), canonical(rhs)
        def contains(items, part):
            return any(items[n:n+len(part)] == part for n in range(len(items)-len(part)+1))
        hazards = []
        divisors = [rhs[j+1] for j,t in enumerate(rhs[:-1]) if t in ('/', '%')
                    and re.fullmatch(r'[a-z_][a-z0-9_]*', rhs[j+1])]
        if any(contains(left, [name]+op+['0']) for name in divisors
               for op in (['!','='], ['=','='], ['<'], ['>'], ['<','='], ['>','='])):
            hazards.append('division/remainder')
        access_guard = False
        for j in range(len(left)-4):
            if left[j:j+3] == ['$', 'notvalid', '('] and left[j+4] == ')':
                receiver=left[j+3]
                access_guard |= contains(rhs,[receiver,"'",'s']) or contains(rhs,['$','getattribute','(',receiver,','])
            if (left[j:j+3] == ['$','hasattribute','('] and j+6<len(left)
                    and left[j+4]==',' and left[j+6]==')' and left[j+5].startswith('"')):
                receiver,name=left[j+3],left[j+5]
                access_guard |= contains(rhs,[receiver,"'",'s',name]) or contains(rhs,['$','getattribute','(',receiver,',',name,')'])
        if access_guard:
            hazards.append('property/attribute access')
        if hazards:
            findings.append({'severity': 'warning', 'code': 'GPL-EAGER-GUARD', 'source': source,
                             'line': text.count('\n', 0, token.start()) + 1,
                             'message': 'Logical RHS contains ' + ' and '.join(hazards) +
                             '; tested GPL evaluates both operands. Use nested if statements when '
                             'the left side is intended to guard it. This is not proof of an unsafe value.',
                             'evidence': 'research/docs/gpl-numeric-guidance.md#guard-expressions-and-condition-types',
                             'profile': 'documented modified-beta2/compiler pair; advisory on other profiles'})
    return findings
