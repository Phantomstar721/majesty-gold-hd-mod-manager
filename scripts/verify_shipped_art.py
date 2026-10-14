"""Read-only real-package art regression gate. Never prepares a game profile."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from majesty_cam.stock_art import collapse_art_archives, load_stock_art_lineages
from majesty_cam.compose import _compose_art_domain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, default=ROOT.parent)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    roots = json.loads((ROOT / 'release/art-regression-packages.json').read_text())
    lineages = load_stock_art_lineages(args.game)
    results, combined = [], {}
    for item in roots:
        relative = item if isinstance(item, str) else item['path']
        development_only = isinstance(item, dict) and item.get('development_only', False)
        if development_only:
            continue  # Development packages must not affect the release gate.
        root = args.workspace / relative
        manifests = sorted(root.glob('*.mmxml'))
        if not manifests:
            results.append({'package': relative, 'developmentOnly': development_only,
                            'error': 'required package manifest missing'})
            continue
        for manifest in manifests:
            for mod in ET.parse(manifest).getroot().findall('Mod'):
                name = mod.findtext('Name') or mod.attrib['id']
                owner = name.casefold()
                row = {'package': relative, 'component': name, 'inputs': [],
                       'developmentOnly': development_only}
                try:
                    # Match the Manager's first native dataset/component load order.
                    load = mod.find('DataConfiguration/Dataset/Load')
                    paths = tuple(root / item.text.strip().replace('\\', '/')
                                  for item in load.findall('CAM'))
                    row['inputs'] = [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                                     for path in (manifest, *paths)]
                    parts = collapse_art_archives(args.game, paths, owner=owner, lineages=lineages)
                    row['lineages'] = []
                    for part in parts:
                        inv = SimpleNamespace(selected=SimpleNamespace(alias=owner))
                        provider = (inv, part.paths[-1], part.archive)
                        output = _compose_art_domain(part.lineage.lineage_id, part.lineage.domain,
                            part.lineage.effective, (provider,), (part.analysis,),
                            fallthrough_ancestors=part.lineage.ancestors)
                        row['lineages'].append({'id': part.lineage.lineage_id,
                            'outputSha256': hashlib.sha256(output.archive.to_bytes()).hexdigest()})
                        if not development_only:
                            combined.setdefault(part.lineage.lineage_id, {})[owner] = (provider, part)
                except Exception as exc:
                    row['error'] = str(exc)
                results.append(row)
    for lineage_id, by_owner in combined.items():
        rows = list(by_owner.values())
        lineage = rows[0][1].lineage
        row = {'combination': lineage_id, 'owners': list(by_owner)}
        try:
            output = _compose_art_domain(lineage_id, lineage.domain, lineage.effective,
                tuple(provider for provider, _ in rows), tuple(part.analysis for _, part in rows),
                fallthrough_ancestors=lineage.ancestors)
            row['outputSha256'] = hashlib.sha256(output.archive.to_bytes()).hexdigest()
        except Exception as exc:
            row['error'] = str(exc)
        results.append(row)
    args.report.write_text(json.dumps(results, indent=2) + '\n')
    failures = [row for row in results if 'error' in row]
    for row in failures:
        print(f"{row.get('package', row.get('combination'))}: {row['error']}", file=sys.stderr)
    return any(not row.get('developmentOnly', False) for row in failures)


if __name__ == '__main__':
    sys.exit(main())
