from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_research_pages_candidate import validate_completion_storage
from majesty_cam.stock_controller_features import StockAp99ResearchRow, StockAp10Ap69SecondaryPanel, parse_controller_feature, controller_feature_mapping
from majesty_cam.stock_controller_registry import resolve_stock_controller_registry, encode_stock_controller_registry, decode_stock_controller_registry
from majesty_cam.queued_building_action import source, symbol
from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.compose import compile_gpl


def row():
    return StockAp99ResearchRow('plague','purge',31900,5000,5000,3,0,32900,31901,31902,0,'Purge',
        charge_ms=30000,readiness_callback_symbol='Ready',completion_callback_symbol='Complete')


class QueuedBuildingActionTests(unittest.TestCase):
    def test_passive_cooldown_panel_roundtrip(self):
        panel=StockAp10Ap69SecondaryPanel('plague','Forge','PG01','FRG',31720,
            cooldown_remaining_callback_symbol='Remaining',cooldown_duration_ms=300000,
            cooldown_progress_control_id=31920,cooldown_text_control_id=31921)
        self.assertEqual(parse_controller_feature(controller_feature_mapping(panel)),panel)
        registry=resolve_stock_controller_registry((panel,row()),{'plague':(int.from_bytes(b'FRG1','little'),int.from_bytes(b'PG01','little'))})
        data=encode_stock_controller_registry(registry)
        self.assertEqual(int.from_bytes(data[4:8],'little'),30)
        self.assertEqual(decode_stock_controller_registry(data),registry)
        for bad in (replace(panel,cooldown_duration_ms=-1),replace(panel,cooldown_text_control_id=31920),replace(panel,cooldown_remaining_callback_symbol='')):
            with self.assertRaises(ValueError): controller_feature_mapping(bad)

    def test_prepaid_contract_separates_quote_start_and_restored_completion(self):
        item=replace(row(),quote_callback_symbol='CanPay',start_callback_symbol='Pay')
        self.assertNotEqual(symbol(item),symbol(row())) # unpaid v28 saves cannot cure for free
        self.assertEqual(parse_controller_feature(controller_feature_mapping(item)),item)
        panel=StockAp10Ap69SecondaryPanel('plague','Forge','PG01','FRG',31720)
        registry=resolve_stock_controller_registry((panel,item),{'plague':(int.from_bytes(b'FRG1','little'),int.from_bytes(b'PG01','little'))})
        data=encode_stock_controller_registry(registry)
        self.assertEqual(int.from_bytes(data[4:8],'little'),29)
        self.assertEqual(decode_stock_controller_registry(data),registry)
        for n in range(len(data)):
            with self.assertRaises(ValueError): decode_stock_controller_registry(data[:n])
        text=source(item)
        completed=text.split('if (Operation == 2)',1)[1].split('if (Pending) return 2;',1)[0]
        self.assertNotIn('$Pay(',completed)
        self.assertNotIn('$CanPay(',completed)
        self.assertIn('$Complete(Building)',completed)
        self.assertLess(text.index('if (Pending) return 2;'),text.index('$CanPay('))
        self.assertLess(text.index('if (Operation == 1)'),text.index('$Pay('))
        self.assertLess(text.index('_pending" = 1;'),text.index('$Pay('))
        self.assertIn('_pending" = 0;',text.split('$Pay(',1)[1])
        with self.assertRaises(ValueError): controller_feature_mapping(replace(item,quote_callback_symbol=''))

    def test_permanent_completion_storage_only(self):
        charged=row()
        permanent=replace(charged,charge_ms=0,readiness_callback_symbol='',completion_callback_symbol='')
        mapping={'plague':(123,456)}
        validate_completion_storage((charged,permanent),mapping)
        with self.assertRaisesRegex(ValueError,'share completion storage'):
            validate_completion_storage((permanent,permanent),mapping)

    def test_schema_wire_and_generated_source(self):
        item=row()
        self.assertEqual(parse_controller_feature(controller_feature_mapping(item)),item)
        panel=StockAp10Ap69SecondaryPanel('plague','Forge','PG01','FRG',31720)
        registry=resolve_stock_controller_registry((panel,item),{'plague':(int.from_bytes(b'FRG1','little'),int.from_bytes(b'PG01','little'))})
        data=encode_stock_controller_registry(registry)
        self.assertEqual(int.from_bytes(data[4:8],'little'),28)
        self.assertEqual(decode_stock_controller_registry(data),registry)
        with self.assertRaises(ValueError):decode_stock_controller_registry(data[:-1])
        text=source(item)
        self.assertLess(text.index('Building\'s "'+symbol(item)+'_pending" = 0;',text.index('if (Operation == 2)')), text.index('$Complete(Building)'))
        self.assertIn('if (Player != Initiator) return 3;',text)
        self.assertNotIn('RunThread',text)
        self.assertNotIn('ListObjects',text)
        for bad in (replace(item,price=1),replace(item,charge_ms=-1),replace(item,readiness_callback_symbol='')):
            with self.assertRaises(ValueError):controller_feature_mapping(bad)

    def test_stock_compiler_accepts_saved_owner_adapter(self):
        compiler=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe')
        self.assertTrue(compiler.is_file())
        paid=replace(row(),quote_callback_symbol='CanPay',start_callback_symbol='Pay')
        text='function Ready(agent Building) is boolean declare begin return True; end\nfunction Complete(agent Building) declare begin end\nfunction CanPay(agent Building) is boolean declare begin return True; end\nfunction Pay(agent Building) is boolean declare begin return True; end\n'+source(row())+source(paid)
        result=SemanticMergeResult(parse_gpl(text).items,())
        with TemporaryDirectory(prefix='queued-action-') as tmp:
            compile_gpl(result.emit_project_source_set(),compiler,Path(tmp)/'compile')


if __name__=='__main__':unittest.main()
