from dataclasses import replace
from pathlib import Path
import sys
import struct
import unittest
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.compact_sovereign_toolbar import FEATURE_TYPE, parse, bind
from majesty_cam.stock_controller_features import (
    StockAp10Ap69SecondaryPanel, StockAp69PaidSourceTargetAction,
    parse_controller_feature, ControllerFeatureError,
)


class ToolbarContractTests(unittest.TestCase):
    def setUp(self):
        self.value = dict(type=FEATURE_TYPE, panel_key="example.spells",
                          action_key="example-action", required_level=3,
                          icon_id="Exic", icon_set=1015, hover_text="Example — 500 gold.")
        self.panel = StockAp10Ap69SecondaryPanel("example.spells", "ExampleGuild", "Exsp", "EXG", 8001)
        self.action = StockAp69PaidSourceTargetAction(
            panel_key="example.spells", action_key="example-action",
            visual_control_id=4403, private_control_id=31248,
            visual_template_control_id=4403, target_template_control_id=4408,
            stock_target_mode="Sp29", stock_executor_mode="Sp14",
            private_mode="ExB1", private_unit_id="EXBS", cursor_ordinal=45,
            required_level=2, icon_control_id=5403, price_control_id=3403,
            callback_symbol="ExamplePaid", sovereign_gold_cost=500)

    def test_binding_preserves_action_and_distinct_origin(self):
        result = bind(parse(self.value), (self.panel, self.action))
        self.assertIs(result.action, self.action)
        self.assertEqual((result.required_level, result.action.required_level), (3, 2))
        self.assertEqual(result.building_family_id, "EXG")
        self.assertEqual((result.action.sovereign_gold_cost, result.action.callback_symbol), (500, "ExamplePaid"))

    def test_missing_ambiguous_or_other_owner_inputs_rejected(self):
        for features in ((), (self.panel,), (self.action,),
                         (self.panel, self.action, self.action),
                         (self.panel, self.panel, self.action),
                         (self.panel, replace(self.action, panel_key="other.spells"))):
            with self.subTest(features=features), self.assertRaises(ValueError):
                bind(parse(self.value), features)

    def test_no_duplicate_gameplay_definition(self):
        for field in ("sovereign_gold_cost", "callback_symbol", "private_mode", "building_family_id", "private_control_id"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse(dict(self.value, **{field: 500}))

    def test_gate_and_hover_boundaries(self):
        for field, value in (("required_level", True), ("required_level", 0),
                             ("required_level", 4), ("icon_id", "toolong"),
                             ("icon_set", -1), ("icon_set", True),
                             ("hover_text", "a\x00b"), ("hover_text", ""),
                             ("hover_text", "x" * 1025), ("hover_text", "\u2603")):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                parse(dict(self.value, **{field: value}))
        with self.assertRaises(ValueError):
            bind(parse(dict(self.value, required_level=1)), (self.panel, self.action))

    def test_typed_parser_and_registry_roundtrip(self):
        from majesty_cam.stock_controller_registry import resolve_stock_controller_registry, encode_stock_controller_registry, decode_stock_controller_registry
        feature = parse_controller_feature(self.value)
        registry = resolve_stock_controller_registry((self.panel, self.action, feature),
            {self.panel.panel_key: (int.from_bytes(b"EXG1", "little"), int.from_bytes(b"Exsp", "little"))})
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(int.from_bytes(payload[4:8], "little"), 25)
        self.assertEqual(decode_stock_controller_registry(payload), registry)

    def test_bounds_preserve_negative_centering_and_stock_margin(self):
        from majesty_cam.compact_toolbar_resources import extend_stock_bounds
        from majesty_cam.private_recruitment import records, control_record
        words = [1000, 2, 0xFFFFFFFF, 0xFFFFFFFF, 590, 34, 0xFFFFFFFF]
        words += [0, 2, 0, 0, 590, 34, 6, 1, 0xFFFFFFFF]
        for index, control in enumerate(range(4401, 4423)):
            x = 562 if index == 21 else 4 + index * 25
            words += [0, 2, x, 4, 25, 25, 6, control, 0xFFFFFFFF]
        words += [0xFFFFFFFF]
        stock = struct.pack(f"<{len(words)}I", *words)
        for right, width in ((612, 615), (637, 640)):
            with self.subTest(right=right):
                output = extend_stock_bounds(stock, stock, right)
                self.assertEqual(struct.unpack_from("<6I", output),
                                 (1000, 2, 0xFFFFFFFF, 0xFFFFFFFF, width, 34))
                self.assertEqual(control_record(records(output), 1)[2:6], (0, 0, width, 34))
                for control in range(4401, 4423):
                    self.assertEqual(control_record(records(output), control),
                                     control_record(records(stock), control))

    def test_chrome_retains_endcaps_palette_and_centered_anchor(self):
        from majesty_cam.compact_toolbar_resources import extend_chrome_tile
        header = bytearray(26)
        struct.pack_into('<4H',header,0,1,34,590,590)
        struct.pack_into('<hh',header,10,295,17)
        struct.pack_into('<HI',header,20,1,26+590*34)
        rows = [bytes((x+y)%256 for x in range(590)) for y in range(34)]
        palette = bytes(i%256 for i in range(1032))
        source = bytes(header)+b''.join(rows)+palette
        for width in (590,615,618,640,643):
            output = extend_chrome_tile(source,width)
            self.assertEqual(struct.unpack_from('<4H',output),(1,34,width,width))
            self.assertEqual(struct.unpack_from('<hh',output,10),(width//2,17))
            self.assertEqual(output[26+width*34:],palette)
            for y,row in enumerate(rows):
                expanded=output[26+y*width:26+(y+1)*width]
                self.assertEqual(expanded[:295],row[:295])
                self.assertEqual(expanded[295+width-590:],row[295:])
        for offset,value in ((0,3),(4,589),(20,0),(10,0)):
            bad=bytearray(source);struct.pack_into('<H',bad,offset,value)
            with self.assertRaises(ValueError):extend_chrome_tile(bytes(bad),615)

    @unittest.skipUnless(os.environ.get('MAJESTY_STOCK_ROOT'), 'stock art fixture not configured')
    def test_composition_preserves_expansion_spells_overlays_and_help(self):
        from majesty_cam.compose import merge_text_resources
        from majesty_cam.cam import read_cam
        from majesty_cam.private_recruitment import records, control_record
        from majesty_cam.strt import parse_strt
        from majesty_cam.stock_controller_registry import resolve_stock_controller_registry
        game = Path(os.environ['MAJESTY_STOCK_ROOT'])
        registry = resolve_stock_controller_registry((self.panel, self.action, parse(self.value)),
            {self.panel.panel_key: (int.from_bytes(b'EXG1','little'),int.from_bytes(b'Exsp','little'))})
        result = merge_text_resources(game, (), controller_registry=registry)
        self.assertEqual(tuple(s for s, _ in result.scoped_text_archives), ('MajestyExpansion',))
        views = (('Data/textdata.cam', result.text_archive, range(4401,4423)),
                 ('DataMX/mx_textdata.cam', result.scoped_text_archives[0][1],
                  (*range(4401,4429),9500,9600)))
        def resource(archive, section):
            return next(e.data for s in archive.sections if s.extension == section
                        for e in s.entries if e.name[:4] == b'AP92')
        for path, view, controls in views:
            with self.subTest(dataset=path):
                stock = read_cam(game / path)
                before, after = records(resource(stock,b'SMNU')), records(resource(view,b'SMNU'))
                for control in controls:
                    self.assertEqual(control_record(before,control), control_record(after,control))
                old_help = parse_strt(resource(stock,b'STRT')).records
                new_help = parse_strt(resource(view,b'STRT')).records
                self.assertEqual(new_help[:-1], old_help)
                self.assertEqual(control_record(after,31248)[2:6], (590,4,25,25))
                self.assertEqual(struct.unpack_from('<I',resource(view,b'SMNU'),16)[0],618)

    @unittest.skipUnless(os.environ.get('MAJESTY_STOCK_ROOT'), 'stock art fixture not configured')
    def test_real_stock_chrome_is_reconciled_without_changing_other_art(self):
        from majesty_cam.compose import merge_art_resource_domains
        from majesty_cam.cam import CamArchive
        from majesty_cam.compact_toolbar_resources import append_toolbar, bind_toolbar_chrome
        from majesty_cam.stock_controller_registry import resolve_stock_controller_registry
        from majesty_cam.art import parse_stock_imag_tile_references
        game=Path(os.environ['MAJESTY_STOCK_ROOT'])
        toolbar=parse(self.value)
        registry=resolve_stock_controller_registry((self.panel,self.action,toolbar),
            {self.panel.panel_key:(int.from_bytes(b'EXG1','little'),int.from_bytes(b'Exsp','little'))})
        text=append_toolbar(CamArchive(()),game,registry)
        from majesty_cam.private_recruitment import records, control_record
        smnu=next(e.data for s in text.sections if s.extension==b'SMNU'
                  for e in s.entries if e.name[:4]==b'AP92')
        self.assertEqual(control_record(records(smnu),31248)[2:6],(590,4,25,25))
        self.assertEqual(struct.unpack_from('<I',smnu,16)[0],618)
        old=merge_art_resource_domains(game,(),required_stock_imag_ids=(b'INDz',))
        new=bind_toolbar_chrome(old,text,registry)
        changed=0
        for before,after in zip(old,new):
            if before is after:continue
            changed+=1
            sections={s.extension:s for s in after.archive.sections}
            old_sections={s.extension:s for s in before.archive.sections}
            tiles=sections[b'TILE'].entries
            self.assertEqual(tiles[:-1],old_sections[b'TILE'].entries)
            self.assertEqual(struct.unpack_from('<4H',tiles[-1].data),(1,34,618,618))
            for prior,current in zip(old_sections[b'IMAG'].entries,sections[b'IMAG'].entries):
                if prior.name[:4]!=b'INDz':self.assertEqual(prior,current);continue
                refs=[r for r in parse_stock_imag_tile_references(prior.data,
                    tile_count=len(tiles)-1).references if r.set_id==1012]
                self.assertEqual(len(refs),1)
                expected=bytearray(prior.data)
                struct.pack_into('<I',expected,refs[0].offset,refs[0].flag_bits|len(tiles)-1)
                self.assertEqual(current.data,bytes(expected))
        self.assertEqual(changed,1)


if __name__ == "__main__":
    unittest.main()
