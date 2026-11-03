from dataclasses import replace
import copy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import struct
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.private_recruitment import PrivateRecruitmentError, validate_descriptions, validate_resolved_descriptions, validate_panel, validate_secondary_panel, records, control_record
from majesty_cam.stock_controller_features import StockAp52PrivateRecruitment, StockAp52RecruitmentPanel, StockMx22BuildingOpenToggle, parse_controller_feature
from majesty_cam.stock_controller_registry import (
    ControllerRegistryError, resolve_stock_controller_registry,
    encode_stock_controller_registry, decode_stock_controller_registry,
)


def buildings():
    result = []
    for stage in range(1, 4):
        item = ET.fromstring(f'''<Description type="Unit" subType="Building" ID="ZZZ{stage}" Name="Example{stage}">
          <Game><DialogID value="ZZPN"/><Flags value="IsGuild"/><MaxGuildMembers value="4"/>
          <Produces><Unit ID="HeroA"/><Unit ID="HeroB"/><Unit ID="HeroC"/></Produces></Game></Description>''')
        game = item.find("Game")
        if stage != 1: ET.SubElement(game, "UpgradeFrom", value=f"Example{stage-1}")
        if stage != 3: ET.SubElement(game, "UpgradeTo", value=f"Example{stage+1}")
        result.append(item)
    return result


class PrivateRecruitmentTests(unittest.TestCase):
    def setUp(self):
        self.feature = StockAp52PrivateRecruitment("recruitment", "Example1", 0x7301)
        self.parent = int.from_bytes(b"ZZPN", "little")

    def test_typed_feature_and_v17_roundtrip(self):
        self.assertEqual(parse_controller_feature({"type": self.feature.type, "panel_key": "recruitment",
                                                  "parent_building": "Example1", "third_price_control_id": 0x7301}), self.feature)
        registry = resolve_stock_controller_registry((self.feature,), {}, recruitment_parents={"recruitment": self.parent})
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from("<I", payload, 4)[0], 17)
        self.assertEqual(decode_stock_controller_registry(payload), registry)
        for end in range(len(payload)):
            with self.assertRaises(ControllerRegistryError): decode_stock_controller_registry(payload[:end])
        with self.assertRaises(ControllerRegistryError): decode_stock_controller_registry(payload+b'\0')
        legacy = encode_stock_controller_registry(resolve_stock_controller_registry((), {}))
        self.assertEqual(struct.unpack_from("<I", legacy, 4)[0], 2)

    def test_same_parent_toggle_supported_but_control_collision_rejected(self):
        toggle = StockMx22BuildingOpenToggle("open", "Example1", 0x7201, 0x7202)
        registry = resolve_stock_controller_registry((self.feature, toggle), {},
            recruitment_parents={"recruitment": self.parent}, toggle_parents={"open": (self.parent, "AP52")})
        self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(registry)), registry)
        for control in (0x7301, 0x1F48, 0x1F47):
            with self.assertRaises(ControllerRegistryError):
                resolve_stock_controller_registry((self.feature, replace(toggle, open_command_id=control)), {},
                    recruitment_parents={"recruitment": self.parent}, toggle_parents={"open": (self.parent, "AP52")})
        with self.assertRaises(ControllerRegistryError):
            resolve_stock_controller_registry((self.feature, toggle), {},
                recruitment_parents={"recruitment": self.parent}, toggle_parents={"open": (self.parent, "AP08")})

    def test_secondary_recruitment_v18_and_cross_record_validation(self):
        feature = StockAp52RecruitmentPanel("a-child", "Example", 0x7301,
                    source_dialog_id="RCRT", open_command_id=0x7302)
        child = int.from_bytes(b"RCRT", "little")
        mapping = {feature.panel_key: (self.parent, child)}
        parents = {feature.panel_key: self.parent}
        self.assertEqual(parse_controller_feature(vars(feature)), feature)
        registry = resolve_stock_controller_registry((feature,), mapping, recruitment_parents=parents)
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from("<I", payload, 4)[0], 18)
        self.assertEqual(decode_stock_controller_registry(payload), registry)
        for end in range(len(payload)):
            with self.assertRaises(ControllerRegistryError): decode_stock_controller_registry(payload[:end])
        for field, value in (("child_dialog_id", self.parent), ("open_command_id", 0x1F49),
                             ("open_command_id", 0x7301), ("open_command_id", 0)):
            bad = replace(registry, private_recruitments=(replace(registry.private_recruitments[0], **{field:value}),))
            with self.assertRaises(ValueError): encode_stock_controller_registry(bad)
        with self.assertRaises(ControllerRegistryError):
            resolve_stock_controller_registry((feature,), mapping, recruitment_parents={feature.panel_key: child})
        toggle = StockMx22BuildingOpenToggle("toggle", "Example", 0x7302, 0x7303)
        with self.assertRaises(ControllerRegistryError):
            resolve_stock_controller_registry((feature, toggle), mapping, recruitment_parents=parents,
                                               toggle_parents={"toggle": (self.parent, "AP52")})
        # A shared section mixes inline and child recipes, sorted by key rather
        # than Python feature type; the native parser requires that ordering.
        inline = replace(self.feature, panel_key="z-inline", parent_building="Other")
        parents[inline.panel_key] = int.from_bytes(b"OTHR", "little")
        mixed = resolve_stock_controller_registry((inline, feature), mapping, recruitment_parents=parents)
        self.assertEqual([x.panel_key for x in mixed.private_recruitments], ["a-child", "z-inline"])
        self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(mixed)), mixed)

    def test_description_driven_three_stage_contract(self):
        source = buildings()
        self.assertEqual(len(validate_descriptions(source, "Example1")), 3)
        self.assertEqual(len(validate_descriptions(source, "Example")), 3)
        variants = []
        for field, value in (("Produces/Unit", "Other"), ("DialogID", "ZZXX"),
                             ("UpgradeFrom", "Example3"), ("MaxGuildMembers", "0"), ("Flags", "HasHPBar")):
            modified = copy.deepcopy(source)
            modified[1].find("./Game/"+field).set("ID" if field == "Produces/Unit" else "value", value)
            variants.append(modified)
        cycle = copy.deepcopy(source)
        cycle[1].find("./Game/UpgradeTo").set("value", "Example1")
        variants.append(cycle)
        variants.append(source[:2])
        variants.append(source+[copy.deepcopy(source[0])])
        for variant in variants:
            with self.assertRaises(PrivateRecruitmentError): validate_descriptions(variant, "Example1")

    def test_generated_owner_uses_relocated_dialog_not_sidecar_hash_name(self):
        source = buildings()
        for record in source: record.find('./Game/DialogID').set('value', 'CG07')
        self.assertEqual(validate_resolved_descriptions(source, 'CG07'), tuple(source))
        with self.assertRaises(PrivateRecruitmentError): validate_resolved_descriptions(source, 'ZZPN')
        unrelated = copy.deepcopy(source[0]); unrelated.set('Name', 'Other')
        with self.assertRaises(PrivateRecruitmentError): validate_resolved_descriptions(source + [unrelated], 'CG07')


class PrivateRecruitmentProfileTests(unittest.TestCase):
    def test_full_size_secondary_contract(self):
        beta = os.environ.get("MAJESTY_BETA2_EXE")
        if not beta: self.skipTest("stock CAM fixtures are not configured")
        from majesty_cam.compose import _require_cam_entry
        path = Path(beta).parent / "Data" / "textdata.cam"
        templates = {key: _require_cam_entry(path, b"SMNU", key).data for key in (b"AP52", b"AP53", b"AP10", b"AP69")}
        stock = records(templates[b"AP52"])
        def clone(source, control, old=None, position=None):
            row = list(control_record(source, old or control))
            if old is not None:
                at = next(i for i in range(6,len(row)-1) if row[i:i+2] == [6,old])
                row[at+1] = control
            if position is not None: row[2:4] = position
            return tuple(row)
        main = list(stock)
        sub = [row[:2]+(1500,1500)+row[4:] if len(row)>6 else row for row in stock]
        hidden = (0x22CE,0x1F49,0x1181,0x1F0E,0x1F11,0x1F12,0x1F13,0x1F14,
                  0x1F48,0x1389,0x1388,0x1752,0x1F51,0x1F56,0x1F57)
        for control in hidden:
            main[main.index(control_record(main,control))] = clone(stock,control,position=(1500,1500))
        for control in (0x1E28,0x1F47,0x1F4F): main.insert(-1,clone(records(templates[b"AP53"]),control))
        main.insert(-1,clone(stock,0x7301,0x1F51,(1500,1500)))
        main.insert(-1,clone(records(templates[b"AP10"]),0x7302,0x1F49))
        sub.insert(-1,clone(records(templates[b"AP69"]),0x1F4D))
        for row_index,(control,price) in enumerate(((0x1388,0x7301),(0x1389,0x1F51),(0x1F48,0x1752))):
            y = 64+40*row_index
            sub[sub.index(control_record(sub,control))] = clone(stock,control,0x1389,(7,y))
            row = clone(stock,price,0x1F51,(155,y+4))
            if price == 0x7301: sub.insert(-1,row)
            else: sub[sub.index(control_record(sub,price))] = row
        for control in (0x1F56,0x1F57): sub[sub.index(control_record(sub,control))] = clone(stock,control)
        pack = lambda items: b''.join(struct.pack(f'<{len(row)}I',*row) for row in items)
        validate_secondary_panel(pack(main),pack(sub),templates,0x7301,0x7302)
        # Only the three full-width recruit buttons may select AP52's small
        # recruit font; native caption geometry/art/flags stay unchanged.
        def set_font(items, control, font):
            changed = list(items)
            at = changed.index(control_record(changed, control))
            row = list(changed[at])
            font_at = next(i+1 for i in range(6, len(row)-1) if row[i] == 0x12)
            row[font_at] = font
            changed[at] = tuple(row)
            return changed
        for control, font in ((0x1389, 0x34746E66), (0x1388, 0x37746E66), (0x1F48, 0x37746E66)):
            row = control_record(stock, control)
            self.assertIn((0x12, font), tuple(zip(row, row[1:])))
        for control in (0x1F48, 0x1389, 0x1388):
            for font in (0, 0x31746E66, 0x38746E66, 0x41414141):
                with self.subTest(control=control, font=font), self.assertRaises(PrivateRecruitmentError):
                    validate_secondary_panel(pack(main), pack(set_font(sub, control, font)), templates, 0x7301, 0x7302)
            sub = set_font(sub, control, 0x37746E66)
            validate_secondary_panel(pack(main), pack(sub), templates, 0x7301, 0x7302)
        # Font flexibility does not extend to the price widgets or navigation.
        for control, font in ((0x1F51, 0x34746E66), (0x1F4D, 0x41414141)):
            with self.assertRaises(PrivateRecruitmentError):
                validate_secondary_panel(pack(main), pack(set_font(sub, control, font)), templates, 0x7301, 0x7302)
        for offset in (8, 30, 37, 41):  # caption top, button flag, font tag, text color
            bad = list(sub)
            at = bad.index(control_record(bad, 0x1389))
            row = list(bad[at]); row[offset] += 1; bad[at] = tuple(row)
            with self.assertRaises(PrivateRecruitmentError):
                validate_secondary_panel(pack(main), pack(bad), templates, 0x7301, 0x7302)
        # Exercise the Manager's generic child allocation/evidence path, not
        # just the binary encoder. This is an isolated source fixture; it does
        # not prepare or write a playable Manager profile.
        from majesty_cam.cam import CamEntry, pad_name
        from majesty_cam.compose import (PackageInventory, SelectedMod, CamResource, ResolvedBuildingDialog,
            resolve_controller_registry, _validate_authored_controller_panel_controls,
            _validate_authored_private_recruitment)
        from majesty_cam.package import ModDefinition, CustomBuildingDefinition
        with TemporaryDirectory() as directory:
            root = Path(directory)
            xml = ET.Element("Majesty")
            xml.extend(buildings())
            for name in ("HeroA", "HeroB", "HeroC"):
                ET.SubElement(xml, "Description", type="Unit", subType="Character", Name=name, ID=name[-1]+"001")
            description = root / "description.xml"
            ET.ElementTree(xml).write(description)
            feature = StockAp52RecruitmentPanel("recruitment", "Example", 0x7301,
                                               source_dialog_id="RCRT", open_command_id=0x7302)
            definition = ModDefinition(schema_version=3, mod_id="00000000-0000-0000-0000-000000000091",
                internal_name="Example", display_name="Example",
                custom_buildings=(CustomBuildingDefinition(local_name="Example", dialog_id=None, controller_base="AP52", panel_resource_template="AP52"),),
                runtime_features=(feature,), runtime_capabilities=())
            resources = tuple(CamResource("example", root/"panel.cam", 0, index, 0, section, CamEntry(pad_name(key), payload))
                for index,(section,key,payload) in enumerate(((b"SMNU",b"ZZPN",pack(main)),
                    (b"STRT",b"ZZPN",b"labels"),(b"SMNU",b"RCRT",pack(sub)),(b"STRT",b"RCRT",b"labels"))))
            inventory = PackageInventory(SelectedMod("example", SimpleNamespace(definition=definition, mod_id=definition.mod_id)),
                                         (), (description,), (), resources)
            resolved = resolve_controller_registry((inventory,), building_dialogs=(
                ResolvedBuildingDialog("example", "Example", b"ZZPN", b"CGAA"),))
            self.assertEqual(len(resolved.registry.child_panels), 1)
            self.assertEqual(resolved.registry.private_recruitments[0].child_dialog_id,
                             int.from_bytes(resolved.panels[0].resolved_child_dialog_id,"little"))
            _validate_authored_controller_panel_controls((inventory,), resolved.registry, resolved.panels)
            _validate_authored_private_recruitment(Path(beta).parent, (inventory,), resolved.registry, stock_descriptions={})
        for control in (0x1388,0x1389,0x1F48,0x7301,0x1F4D):
            bad = list(sub); index = bad.index(control_record(bad,control))
            row = list(bad[index]); row[4] += 1; bad[index] = tuple(row)
            with self.assertRaises(PrivateRecruitmentError):
                validate_secondary_panel(pack(main),pack(bad),templates,0x7301,0x7302)
        bad = list(main); at = bad.index(control_record(bad,0x1388))
        bad[at] = clone(stock,0x1388,position=(7,64))
        with self.assertRaises(PrivateRecruitmentError):
            validate_secondary_panel(pack(bad),pack(sub),templates,0x7301,0x7302)

    def test_literal_widget_contract(self):
        beta = os.environ.get("MAJESTY_BETA2_EXE")
        if not beta: self.skipTest("stock CAM fixtures are not configured")
        from majesty_cam.compose import _require_cam_entry
        stock_path = Path(beta).parent / "Data" / "textdata.cam"
        ap52 = _require_cam_entry(stock_path, b"SMNU", b"AP52").data
        ap53 = _require_cam_entry(stock_path, b"SMNU", b"AP53").data
        panel = list(records(ap52))
        wizard = records(ap53)
        def clone(template, old, new):
            row = list(template)
            index = next(i for i in range(6, len(row)-1) if row[i:i+2] == [6, old])
            row[index+1] = new
            return tuple(row)
        for command in (0x1F48, 0x1389, 0x1388):
            at = panel.index(control_record(panel, command))
            panel[at] = clone(control_record(panel, 0x1F49), 0x1F49, command)
        at = panel.index(control_record(panel, 0x1752))
        panel[at] = clone(control_record(panel, 0x1F51), 0x1F51, 0x1752)
        panel.insert(-1, clone(control_record(panel, 0x1F51), 0x1F51, 0x7301))
        for control in (0x1E28, 0x1F47, 0x1F4F): panel.insert(-1, control_record(wizard, control))
        for control in (0x22CE, 0x1F49, 0x1181, 0x1F0E, 0x1F11, 0x1F12, 0x1F13, 0x1F14):
            at = panel.index(control_record(panel, control))
            row = list(panel[at]); row[2:4] = [1500, 1500]; panel[at] = tuple(row)
        pack = lambda items: b''.join(struct.pack(f'<{len(row)}I', *row) for row in items)
        validate_panel(pack(panel), ap52, ap53, 0x7301)
        # The native Call-to-Arms text box leaves unused button width. Private
        # localized recruit names may use it, without changing font/art/type
        # or extending into the separate stock price control.
        wide = list(panel)
        for command in (0x1F48, 0x1389, 0x1388):
            at = wide.index(control_record(wide, command))
            row = list(wide[at]); row[7:11] = [2, 4, 135, 14]; wide[at] = tuple(row)
        validate_panel(pack(wide), ap52, ap53, 0x7301)
        at = wide.index(control_record(wide, 0x1389))
        for rectangle in ((2, 4, 138, 14), (2, 4, 135, 18), (2, 4, 0, 14),
                          (0xFFFFFFFF, 4, 135, 14), (2, 21, 135, 1)):
            bad = list(wide); row = list(bad[at]); row[7:11] = rectangle; bad[at] = tuple(row)
            with self.assertRaises(PrivateRecruitmentError): validate_panel(pack(bad), ap52, ap53, 0x7301)
        for offset, value in ((6, 0x2B), (4, 140),
                              (wide[at].index(int.from_bytes(b'fnt7', 'little')),
                               int.from_bytes(b'fnt4', 'little'))):
            bad = list(wide); row = list(bad[at]); row[offset] = value; bad[at] = tuple(row)
            with self.assertRaises(PrivateRecruitmentError): validate_panel(pack(bad), ap52, ap53, 0x7301)
        for kind in ('missing', 'duplicate', 'wrong-widget', 'visible-legacy'):
            bad = list(panel)
            at = bad.index(control_record(bad, 0x7301))
            if kind == 'missing': del bad[at]
            elif kind == 'duplicate': bad.insert(-1, bad[at])
            elif kind == 'wrong-widget': bad[at] = (0,) + bad[at][1:]
            else:
                at = bad.index(control_record(bad, 0x1F49))
                row = list(bad[at]); row[2:4] = [7, 219]; bad[at] = tuple(row)
            with self.assertRaises(PrivateRecruitmentError): validate_panel(pack(bad), ap52, ap53, 0x7301)

    def test_audited_profiles_match_supported_executables(self):
        public, beta = os.environ.get("MAJESTY_PUBLIC_EXE"), os.environ.get("MAJESTY_BETA2_EXE")
        if not public or not beta: self.skipTest("supported executable fixtures are not configured")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        try:
            from audit_private_recruitment import render
        except ImportError:
            self.skipTest("PE auditing dependencies are not installed in this Python runtime")
        header = Path(__file__).resolve().parents[1] / "runtime" / "PrivateRecruitmentProfiles.h"
        self.assertEqual(render(public, beta).strip(), header.read_text().strip())


if __name__ == "__main__": unittest.main()
