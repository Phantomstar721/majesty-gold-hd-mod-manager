"""In-memory author evidence; never prepares or rewrites a Manager profile."""
from dataclasses import replace
import os
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from majesty_cam.cam import read_cam
from majesty_cam.gpl import parse_dat, parse_gpl
from majesty_cam.kingdom_research_compose import (bindings, validate_panels, validate_generated,
    validate_active_effector, _ACTIVE_EFFECTOR, _shape)
from majesty_cam.private_recruitment import records, control_record
from majesty_cam.stock_controller_features import StockAp52PrivateRecruitment
from test_kingdom_research import FEATURE, UUID


class KingdomResearchEvidenceTests(unittest.TestCase):
    def setUp(self):
        game = os.environ.get('MAJESTY_BETA2_EXE')
        if not game: self.skipTest('stock CAM fixture not supplied')
        archive = read_cam(Path(game).parent/'Data/textdata.cam')
        self.templates = {entry.name[:4]: entry.data for section in archive.sections
                          if section.extension == b'SMNU' for entry in section.entries
                          if entry.name[:4] in (b'AP99', b'AP24', b'AP52')}
        self.descriptions = []
        self.dat = []
        for level in (1, 2, 3):
            before = f'<UpgradeFrom value="Example_Guild{level-1}"/>' if level > 1 else ''
            after = f'<UpgradeTo value="Example_Guild{level+1}"/>' if level < 3 else ''
            self.descriptions.append(ET.fromstring(f'''<Description type="Unit" subType="Building"
                ID="EXG{level}" Name="Example_Guild{level}"><Game><DialogID value="CGEX"/>
                <Flags value="IsGuild"/><MaxGuildMembers value="4"/>{before}{after}
                <Produces><Unit ID="One"/><Unit ID="Two"/><Unit ID="Three"/></Produces>
                </Game></Description>'''))
            self.dat.append(f'[Example_Guild{level}]\n{{Guild (title Actual_Script_Title) (Level {level})}}\n[end]\n')
        self.inventory = NS(selected=NS(alias='example', package=NS(mod_id=UUID, definition=NS(
            runtime_features=(FEATURE, StockAp52PrivateRecruitment('example', 'Example_Guild', 0x7100)),
            custom_buildings=(NS(local_name='Example_Guild', controller_base='AP52', panel_resource_template='AP52'),)))),
            descriptions=(Path('fixture.xml'),), semantic_sources=(parse_dat('\n'.join(self.dat)),))
        self.parsed = NS(records=tuple(NS(to_element=lambda item=item: item) for item in self.descriptions))

    def panel(self, compact):
        source = {key: records(value) for key, value in self.templates.items()}
        group = ((FEATURE.action_control_id, b'AP24', 0x1F49),
                 (FEATURE.price_control_id, b'AP24', 0x1184),
                 (FEATURE.progress_control_id, b'AP24', 0x2009),
                 (FEATURE.active_display_control_id, b'AP24', 0x227A)) if compact else (
                 (FEATURE.action_control_id, b'AP99', 0x1388),
                 (FEATURE.price_control_id, b'AP99', 0x1770),
                 (FEATURE.progress_control_id, b'AP52', 0x1F56),
                 (FEATURE.active_display_control_id, b'AP52', 0x1F57))
        rows = []
        for control, template, original in (*group, (FEATURE.icon_control_id, b'AP99', 0x157C)):
            words = list(control_record(source[template], original))
            for i in range(6, len(words)-1):
                if words[i:i+2] == [6, original]: words[i+1] = control
            words[2], words[3] = 7, 223
            rows.append(struct.pack(f'<{len(words)}I', *words))
        payload = b''.join(rows) + b'\xff'*4
        self.inventory.resources = (NS(section=b'SMNU', key=b'CGEX', entry=NS(data=payload)),
                                    NS(section=b'STRT', key=b'CGEX', entry=NS(data=b'')))

    def test_both_stock_layouts_and_actual_dat_title(self):
        with patch('majesty_cam.compose._parse_description_file', return_value=self.parsed):
            for compact in (False, True):
                self.panel(compact)
                validate_panels((self.inventory,), self.templates)
                record, title = bindings((self.inventory,))[0]
                self.assertEqual(title, 'Actual_Script_Title')
                self.assertEqual(record.building_family, int.from_bytes(b'EXG', 'little'))

    def test_custom_prototype_requires_typed_title_and_level(self):
        self.panel(True)
        dat = parse_dat('\n'.join(self.dat).replace('{Guild', '{PrivateGuild'))
        with patch('majesty_cam.compose._parse_description_file', return_value=self.parsed):
            for declared in ('string title;', 'integer Level;', ''):
                proto = parse_gpl('prototype PrivateGuild()\ndeclare\n'+declared+'\nbegin\nend')
                self.inventory.semantic_sources = (dat, proto)
                with self.assertRaisesRegex(ValueError, 'must declare'): bindings((self.inventory,))
            self.inventory.semantic_sources = (dat, parse_gpl(
                'prototype PrivateGuild()\ndeclare\nstring title;\ninteger Level;\nbegin\nend'))
            self.assertEqual(len(bindings((self.inventory,))), 1)

    def test_geometry_and_controller_collisions_fail_closed(self):
        self.panel(True)
        with patch('majesty_cam.compose._parse_description_file', return_value=self.parsed):
            row = self.inventory.resources[0].entry
            bad = bytearray(row.data)
            struct.pack_into('<I', bad, 16, 500) # change literal action width
            original = row.data
            row.data = bytes(bad)
            with self.assertRaisesRegex(ValueError, 'coherent stock'): validate_panels((self.inventory,), self.templates)
            row.data = original
            definition = self.inventory.selected.package.definition
            definition.runtime_features = (FEATURE, replace(definition.runtime_features[1],
                third_price_control_id=FEATURE.progress_control_id))
            with self.assertRaisesRegex(ValueError, 'overlap'): bindings((self.inventory,))

    def test_no_selected_feature_needs_no_package_or_source_lookups(self):
        self.assertEqual(bindings((NS(selected=NS()),)), ())

    def test_optional_overlay_is_literal_stock_and_owned(self):
        game = Path(os.environ['MAJESTY_BETA2_EXE']).parent
        stock = ET.parse(game/'SDK/OriginalQuests/Data/M_Overlays.xml').find(
            ".//Description[@Name='super_charge_effector']")
        self.assertEqual(_shape(stock), _shape(ET.fromstring(_ACTIVE_EFFECTOR)))
        overlay = ET.fromstring(_ACTIVE_EFFECTOR)
        overlay.set('ID', 'EXO1'); overlay.set('Name', 'Example_Active')
        overlay.find('./Engine/ImageIDBase').set('value', 'EXOA')
        overlay.find('./Engine/DefaultSound').set('value', '0')
        self.inventory.resources = (NS(section=b'IMAG', key=b'EXOA', entry=NS(data=b'owned')),)
        validate_active_effector(self.inventory, [overlay], 'Example_Active')
        overlay.find('./Game/StackPriority').set('value', '1')
        with self.assertRaisesRegex(ValueError, 'stock Super Charge'):
            validate_active_effector(self.inventory, [overlay], 'Example_Active')
        overlay.find('./Game/StackPriority').set('value', '0')
        self.inventory.resources = ()
        with self.assertRaisesRegex(ValueError, 'owned IMAG'):
            validate_active_effector(self.inventory, [overlay], 'Example_Active')
        with self.assertRaisesRegex(ValueError, 'one owned Overlay'):
            validate_active_effector(self.inventory, [], 'Example_Active')
        # No declaration means no source/stock/resource reads at all.
        validate_active_effector(NS(), [], '')

    def test_generated_stage_missing_dialog_has_actionable_error(self):
        self.panel(True)
        with patch('majesty_cam.compose._parse_description_file', return_value=self.parsed):
            record = bindings((self.inventory,))[0][0]
            game = self.descriptions[0].find('Game')
            game.remove(game.find('DialogID'))
            with self.assertRaisesRegex(ValueError, 'missing its parent dialog'):
                validate_generated(self.inventory, record)
