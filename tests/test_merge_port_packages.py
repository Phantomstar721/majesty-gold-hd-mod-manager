"""Read-only real-art and scoped-XML regression; never builds a merged profile."""
import os
import hashlib
import struct
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import xml.etree.ElementTree as ET

from majesty_cam.stock_art import collapse_art_archives, load_stock_art_lineages
from majesty_cam.cam import read_cam
from majesty_cam.compose import _compose_art_domain, inventory_package, resolve_building_dialogs
from majesty_cam.description_composition import prepare_description_views
from majesty_cam.manager.compatibility import load_compatibility_registry
from majesty_cam.manager.preflight import prepare_merge_package
from majesty_cam.script_review import ScriptReviewSession, group_conflicts
from majesty_cam.scoped_descriptions import inventory_view, inventory_records


class MergePortPackageTests(unittest.TestCase):
    def test_installed_art_and_development_description_views(self):
        repo = Path(__file__).resolve().parents[1]
        game = Path(os.environ['MAJESTY_STOCK_ROOT'])
        workshop = game.parents[1] / 'workshop/content/73230'
        witch = Path(os.environ.get('MAJESTY_DEVELOPMENT_PACKAGE', str(
            Path(os.environ['USERPROFILE']) / 'Documents/My Games/MajestyHD/Mods/WitchHunterFourSkills')))
        roots = [workshop / name for name in ('3813128205', '3793509198', '3769947406')]
        # The author's published package replaced the temporary test item.
        # Keep the actual art regression payload pinned, not its old download ID.
        patch = Path(os.environ.get('MAJESTY_CAM_PATCH_FIXTURE', str(workshop / '3771164995')))
        art_path = patch / 'Data/MKART_hi.CAM'
        self.assertIn(hashlib.sha256(art_path.read_bytes()).hexdigest(), (
            '409d871b1e108dc000be4e79b43f677e2c7b53f47974ee0b77cdf23a30d704b3',
            '8f776b1329c550ec613679e83708535948149961bb3786679047dcc4f211f6cf',
            '24eb9ef469d353c3db810d29cf8d073206732c6713e4d56f509a6748346692b5'))
        # Independent original regression witness, retained in the updated
        # subscribed fixture. These offsets come from the author's byte-level
        # report, not the parser being tested.
        bbt = next(e.data for s in read_cam(art_path).sections if s.extension == b'IMAG'
                   for e in s.entries if e.name[:4] == b'BBT1')
        self.assertEqual([struct.unpack_from('<I', bbt, n)[0] for n in range(2344,2505,8)],
                         [20269]*10 + [20270]*11)
        self.assertEqual([struct.unpack_from('<I', bbt, n-4)[0] for n in range(2344,2505,8)], [0]*21)
        self.assertEqual(bbt[2508:2544].hex(),
                         '010000000500000000000000010000003200000000000000585234374000000000000000')
        roots.append(patch)
        roots += [repo.parent/'majesty-gold-hd-adventurers-guild/dist/workshop/AdventurerGuild',
                  repo.parent/'majesty-gold-hd-restore-abandoned-zoo/dist/workshop-upload/content', witch]
        lineages = load_stock_art_lineages(game)
        all_parts = {}
        registry = load_compatibility_registry(repo_root=repo)
        for root in roots:
            manifests = tuple(root.glob('*.mmxml'))
            self.assertEqual(len(manifests), 1, str(root))
            for mod in ET.parse(manifests[0]).getroot().findall('Mod'):
                owner = mod.attrib['id']
                paths = tuple(root / x.text.strip().replace('\\', '/')
                              for x in mod.findall('./DataConfiguration/Dataset/Load/CAM'))
                parts = collapse_art_archives(game, paths, owner=owner, lineages=lineages)
                for part in parts:
                    inv = NS(selected=NS(alias=owner))
                    provider = (inv, part.paths[-1], part.archive)
                    composed = _compose_art_domain(part.lineage.lineage_id, part.lineage.domain, part.lineage.effective,
                        (provider,), (part.analysis,), fallthrough_ancestors=part.lineage.ancestors)
                    if root == patch:
                        actual = [e.data for s in composed.archive.sections if s.extension == b'IMAG'
                                  for e in s.entries if e.name[:4] == b'BBT1']
                        if actual:
                            self.assertEqual(actual, [bbt])
                    all_parts.setdefault(part.lineage.lineage_id, {})[owner] = (provider, part)
                if root != witch:
                    continue
                prepared = prepare_merge_package(content_id=owner, display_name='Development',
                                                 source_root=root, registry=registry)
                self.assertFalse(prepared.issues, str(prepared.issues))
                inv = prepared.inventory or inventory_package(prepared.selected_mod)
                review = ScriptReviewSession()
                common, patches, _ = prepare_description_views(game, (inv,), (), review,
                    lambda conflicts: {p.identity: p.left.owner for p in group_conflicts(conflicts)},
                    dialog_resolutions=resolve_building_dialogs((inv,)))
                for scope in ('Majesty', 'MajestyExpansion'):
                    effective = dict(common.document.index)
                    if scope.casefold() in patches:
                        effective.update(patches[scope.casefold()].document.index)
                    # Preserve authored spell lists and private art in quest-scoped hero overrides.
                    for key, authored in inventory_records(inventory_view(inv, scope)).items():
                        if authored.to_element().get('subType') != 'Character':
                            continue
                        self.assertIn(key, effective)
                        for field in ('Engine/ImageIDBase', 'Game/Spell'):
                            self.assertEqual([x.attrib for x in authored.to_element().findall(field)],
                                             [x.attrib for x in effective[key].to_element().findall(field)])
        for by_owner in all_parts.values():
            for rows in (tuple(by_owner.values()), tuple(reversed(tuple(by_owner.values())))):
                lineage = rows[0][1].lineage
                _compose_art_domain(lineage.lineage_id, lineage.domain, lineage.effective,
                    tuple(p for p, _ in rows), tuple(part.analysis for _, part in rows),
                    fallthrough_ancestors=lineage.ancestors)
