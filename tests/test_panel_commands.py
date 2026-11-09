from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from majesty_cam.panel_commands import PanelCommand, parse_commands, adapter_source, adapter_symbol
from majesty_cam.stock_controller_features import StockAp10Ap69SecondaryPanel, parse_controller_feature, controller_feature_mapping
from majesty_cam.stock_controller_registry import resolve_stock_controller_registry, encode_stock_controller_registry, decode_stock_controller_registry
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.compose import compile_gpl


class PanelCommandsTests(unittest.TestCase):
    def test_schema_and_wire(self):
        p = StockAp10Ap69SecondaryPanel('page','Forge','PG01','FRG',31720,
                required_level=3,commands=(PanelCommand(31904,'TryAction'),))
        self.assertEqual(parse_controller_feature(controller_feature_mapping(p)), p)
        r = resolve_stock_controller_registry((p,), {'page':(int.from_bytes(b'FRG1','little'),int.from_bytes(b'PG01','little'))})
        data = encode_stock_controller_registry(r)
        self.assertEqual(int.from_bytes(data[4:8], 'little'),27)
        self.assertEqual(decode_stock_controller_registry(data),r)
        with self.assertRaises(ValueError): decode_stock_controller_registry(data[:-1])
        for raw in ([{'control_id':1,'callback_symbol':'TryAction'}],
                    [{'control_id':31904,'callback_symbol':'MM_Reserved'}],
                    [PanelCommand(31904,'TryAction')]*2):
            with self.assertRaises(ValueError): parse_commands(raw)

    def test_static_boolean_quote_commit_and_numeric_owner(self):
        quote, commit, owner = (adapter_source('TryAction',v) for v in (False,True,None))
        self.assertIn('$TryAction(Building, False)',quote)
        self.assertIn('$TryAction(Building, True)',commit)
        self.assertNotIn('$TryAction(',owner)
        self.assertIn('$GetUnitPlayerNumber(Building)',owner)
        compiler=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe')
        if compiler.is_file():
            body='function TryAction(agent Building, boolean Commit) is boolean declare begin return True; end\n'
            source=SemanticMergeResult(parse_gpl(body+quote+commit+owner).items,())
            with TemporaryDirectory(prefix='panel-command-') as tmp:
                compile_gpl(source.emit_project_source_set(),compiler,Path(tmp)/'compile')


if __name__ == '__main__': unittest.main()
