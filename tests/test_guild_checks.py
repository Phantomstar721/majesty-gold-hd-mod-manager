from dataclasses import replace
import copy
from pathlib import Path
import struct
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
import io
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from majesty_cam.guild_checks import image_fingerprint, compare_presentation, gpl_guard_warnings
from majesty_cam.art import parse_stock_imag_tile_references
from test_stock_art import _archive, _image, _tile


class PresentationContractTests(unittest.TestCase):
    def setUp(self):
        self.image = _image(b'PRF1', 1000, 0)
        self.archive = _archive((self.image,), (_tile(0, marker=31), _tile(1, marker=73)), palette=b'SPLT')

    def fingerprint(self, archive=None, image=None):
        return image_fingerprint(archive or self.archive, image or self.image)

    def test_relocation_does_not_change_contract(self):
        data = bytearray(self.image.data)
        ref = parse_stock_imag_tile_references(data, tile_count=2).references[0]
        struct.pack_into('<H', data, ref.offset, 1)
        moved = replace(self.image, data=bytes(data))
        oldtiles = next(s for s in self.archive.sections if s.extension == b'TILE')
        tile = bytearray(oldtiles.entries[0].data); struct.pack_into('<I', tile, 22, 1)
        archive = replace(self.archive, sections=tuple(
            replace(s, entries=(s.entries[1], replace(s.entries[0], data=bytes(tile)))) if s.extension == b'TILE'
            else replace(s, entries=tuple(reversed(s.entries))) if s.extension == b'SPLT' else s
            for s in self.archive.sections))
        self.assertEqual(self.fingerprint(), self.fingerprint(archive, moved))

    def test_signed_frame_offset_and_tile_anchor_changes_are_detected(self):
        ref = parse_stock_imag_tile_references(self.image.data, tile_count=2).references[0]
        data = bytearray(self.image.data);struct.pack_into('<h', data, ref.offset-4, -12)
        self.assertNotEqual(self.fingerprint(), self.fingerprint(image=replace(self.image, data=bytes(data))))
        archive = replace(self.archive, sections=tuple(replace(s, entries=(
            replace(s.entries[0], data=s.entries[0].data[:8]+b'\x01\x00'+s.entries[0].data[10:]), s.entries[1]))
            if s.extension==b'TILE' else s for s in self.archive.sections))
        self.assertNotEqual(self.fingerprint(), self.fingerprint(archive))

    def test_palette_change_and_frame_flags_are_detected(self):
        archive = replace(self.archive, sections=tuple(replace(s, entries=(replace(s.entries[0], data=b'changed'),s.entries[1]))
                          if s.extension==b'SPLT' else s for s in self.archive.sections))
        self.assertNotEqual(self.fingerprint(), self.fingerprint(archive))
        ref = parse_stock_imag_tile_references(self.image.data, tile_count=2).references[0]
        data = bytearray(self.image.data);struct.pack_into('<I', data, ref.offset, 0x40000000)
        self.assertNotEqual(self.fingerprint(), self.fingerprint(image=replace(self.image,data=bytes(data))))

    def test_missing_palette_rejected(self):
        archive=replace(self.archive,sections=tuple(replace(s,entries=()) if s.extension==b'SPLT' else s for s in self.archive.sections))
        with self.assertRaisesRegex(ValueError,'missing palette'):self.fingerprint(archive)

    def test_required_image_semantic_row_and_panel_changes_are_detected(self):
        expected={'schema_version':1,'panels':{'guild.research':{'research_rows':[{'recipe_key':'silver','icon_control_id':20}],
                  'primary':{'SMNU':'a'},'subpanel':{'STRT':'b'}}},'images':{'PRF1':self.fingerprint()}}
        compare_presentation(expected,copy.deepcopy(expected))
        for group,key,field in [('images','PRF1',None),('panels','guild.research','research_rows'),('panels','guild.research','subpanel')]:
            broken=copy.deepcopy(expected)
            if field is None:del broken[group][key]
            else:broken[group][key][field]=[]
            with self.assertRaisesRegex(ValueError,'presentation contract'):compare_presentation(expected,broken)
        expanded=copy.deepcopy(expected);expanded['panels']['other.guild']={}
        compare_presentation(expected,expanded)

    def test_empty_or_unknown_contract_rejected(self):
        for value in ({}, {'schema_version':2,'panels':{},'images':{}}, {'schema_version':1,'panels':{},'images':{}}):
            with self.assertRaises(ValueError):compare_presentation(value,value)


class GplGuardTests(unittest.TestCase):
    def test_division_and_property_pseudo_guards_warn(self):
        for expression in ('n != 0 && (total/n > 1)', 'n == 0 || (total%n == 1)',
                           '$HasAttribute(a,"X") && (a\'s "X" > 0)',
                           '$notvalid(a) == false && $GetAttribute(a,#HP) > 0'):
            result=gpl_guard_warnings('if ('+expression+') return;', 'hero.gpl')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['severity'],'warning')
            self.assertEqual(result[0]['line'],1)

    def test_nested_if_and_comments_strings_and_unguarded_body_do_not_warn(self):
        for source in ('if (n != 0) if (total/n > 1) return;',
                       '// if (a && b/c)\nif (a && b) value = x/y;',
                       'if (a && name == "slash / && property\'") return;',
                       'if ((x/y > 1) && ready) return;',
                       '/* if (a && b/c) */ if (ready) return;'):
            self.assertEqual(gpl_guard_warnings(source,'source.gpl'),[])

    def test_quoted_fake_guard_and_unrelated_property_do_not_warn(self):
        for source in ('if (n != 0 && label == "x/n") return;',
                       'if (label == "n!=0" && total/n > 1) return;',
                       'if ($HasAttribute(a,"X") && b\'s "X" > 0) return;',
                       'if ($notvalid(a) == false && label == "$GetAttribute(a,#HP)") return;'):
            self.assertEqual(gpl_guard_warnings(source,'source.gpl'),[])


class GuildCliTests(unittest.TestCase):
    def test_snapshot_never_overwrites_and_validation_uses_existing_api(self):
        from majesty_cam.cli import main
        contract={'schema_version':1,'panels':{},'images':{'PRF1':{'metadata_sha256':'pinned','frames':[]}}}
        with TemporaryDirectory() as folder:
            target=Path(folder)/'contract.json'
            with patch('majesty_cam.compose.validate_composed_package',return_value={'guild_warnings':[]}) as validate, \
                    patch('majesty_cam.guild_checks.presentation_snapshot',return_value=contract), \
                    redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(main(['presentation-snapshot',folder,'--image','PRF1','--output',str(target)]),0)
                before=target.read_bytes()
                self.assertEqual(main(['presentation-snapshot',folder,'--image','PRF1','--output',str(target)]),1)
                self.assertEqual(target.read_bytes(),before)
                self.assertEqual(main(['validate-output',folder,'--presentation-contract',str(target)]),0)
                validate.assert_called_with(Path(folder),presentation_contract=contract)


if __name__=='__main__':unittest.main()
