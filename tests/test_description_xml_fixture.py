"""Optional authored-input smoke test; never creates a playable merged profile."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
import xml.etree.ElementTree as ET

from majesty_cam.compose import _load_effective_stock_descriptions
from majesty_cam.description_composition import prepare_description_views
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.script_review import ScriptReviewSession, group_conflicts


class AuthoredXmlFixtureTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MAJESTY_STANDARD_XML_FIXTURE'), 'optional authored XML fixture not selected')
    def test_three_existing_building_overrides(self):
        provider_path = Path(os.environ['MAJESTY_STANDARD_XML_FIXTURE'])
        game = Path(os.environ['MAJESTY_STOCK_ROOT'])
        payload = provider_path.read_bytes()
        stock = _load_effective_stock_descriptions(game)
        chosen = [r for r in parse_descriptions(payload).records
                  if r.to_element().get('subType') == 'Building' and
                  (r.key not in stock or r.to_element().get('Name') != stock[r.key][0].to_element().get('Name'))][:3]
        self.assertEqual(len(chosen), 3, 'fixture needs three changed building identities')
        root = ET.Element('Majesty')
        for record in chosen:
            element = record.to_element()
            element.set('Name', element.get('Name', '') + '_FixturePatch')
            root.append(element)
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'overrides.xml'
            path.write_bytes(ET.tostring(root))
            definition = NS(schema_version=3, custom_buildings=(), runtime_features=())
            inventory = NS(descriptions=(path,), selected=NS(alias='patch', package=NS(
                mod_id='patch-id', definition=definition, metadata=NS(display_name='Building patch'))))
            provider = NS(name='Building provider', package=NS(mod_id='provider-id'),
                          description_payloads=(('majestyexpansion', payload),))
            for winner in ('patch-id', 'provider-id'):
                review = ScriptReviewSession()
                def choose(conflicts):
                    return {pair.identity:winner for pair in group_conflicts(conflicts)}
                common, patches, _ = prepare_description_views(game, (inventory,), (provider,), review,
                                                               choose, dialog_resolutions=())
                records = dict(common.document.index)
                if 'majestyexpansion' in patches:
                    records.update(patches['majestyexpansion'].document.index)
                expected = parse_descriptions(ET.tostring(root)).index if winner == 'patch-id' else {r.key:r for r in chosen}
                for key, record in expected.items():
                    self.assertEqual(records[key]._fingerprint, record._fingerprint)
                self.assertEqual(len(review.applicable_decisions), 1)
