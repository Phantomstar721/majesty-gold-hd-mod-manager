"""Inspect unchanged native packages through catalog/source/CAM readers; no profile build."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from majesty_cam.cam import read_cam
from majesty_cam.engine_dependencies import from_verified_sources, aggregate
from majesty_cam.manager.catalog import scan_catalog, CatalogKind
from majesty_cam.manager.engine_patches import discover
from majesty_cam.panel_engine import find_panels, rewrite_table
from majesty_cam.standard_scripts import read, verify


def inspect(package, compiler):
    package = package.resolve()
    before = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(package.rglob('*')) if p.is_file()}
    entries = scan_catalog(workshop_roots=[package]).entries
    if len(entries) != 1:
        raise ValueError('Expected exactly one native component')
    entry, = entries
    if entry.kind != CatalogKind.STANDARD or not entry.selectable:
        raise ValueError('Native admission failed: '+repr(entry.issues))
    dependency = discover(entry,compiler=compiler)
    provider = read(entry)
    if not verify(provider, compiler):
        raise ValueError('Sources do not reproduce the loaded target')
    kinds = Counter(); evidence = list(dependency.evidence); panels = []
    for dataset in provider.package.datasets[:1]:
        resources = {}
        for load in dataset.loads:
            for cam in load.cams:
                for section in read_cam(cam.absolute_path).sections:
                    for record in section.entries:
                        resources[section.extension, record.name[:4]] = record.data
        discovered = find_panels(resources)
        for key, rows in discovered.items():
            data = resources[b'STRT', key]
            if rewrite_table(data) != data:
                raise ValueError('Identity relocation changed native protocol bytes')
            kinds.update(row.kind for row in rows)
            panels.append({'dataset':dataset.base, 'id':key.decode('latin1'), 'records':len(rows)})
        sources = [(p.relative_path, provider._parse_source(p.absolute_path).text)
                   for load, base in zip(provider.loads, provider.bases)
                   if base == dataset.base.casefold() for p in load.sources]
        evidence.extend(from_verified_sources(sources, owner_id=entry.content_id,
            owner_name=entry.display_name, dataset=dataset.base))
    after = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(package.rglob('*')) if p.is_file()}
    if after != before:
        raise ValueError('Native package changed during validation')
    return {'schema':1, 'package':str(package), 'contentId':entry.content_id,
        'kind':entry.kind.value, 'selectable':entry.selectable, 'inputs':before,
        'sourceProof':True, 'panels':panels, 'behaviorKinds':dict(sorted(kinds.items())),
        'requirements':[{'service':r.service,'minimumRevision':r.minimum_revision,'owners':owners}
                        for r, owners in aggregate(evidence)], 'profilePrepared':False,
        'limits':'Static production readers/compiler proof only; no native engine or gameplay acceptance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.package, args.compiler)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
