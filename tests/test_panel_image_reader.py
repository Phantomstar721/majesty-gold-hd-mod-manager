import hashlib
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import read_panel_image as panel


class PanelImageReaderTests(unittest.TestCase):
    def setUp(self):
        self.item, self.table = 0x20000, 0x30000
        self.memory = {
            0x400000: b'abcd', 0x400010: b'efgh',
            self.item: struct.pack('<I', self.table),
            self.table+0x154: struct.pack('<2I', 0x400000, 0x400010),
            self.item+0xCC: struct.pack('<I', 1),
            self.item+0xDC: b'WBic'+struct.pack('<I', 1015),
        }
        self.guards = {'guards': {name: dict(VA=hex(address), bytes=4,
                        SHA256=hashlib.sha256(self.memory[address]).hexdigest())
                        for name,address in [('item-key-setter',0x400000),('item-set-setter',0x400010)]}}
        self.member = self.item
    def read(self, address, size):
        value = self.memory[address]
        self.assertEqual(len(value), size)
        return value
    def capture(self):
        return panel.capture_item(self.read, self.item, self.guards, lambda:self.member)
    def test_binding_and_explicit_partial_coverage(self):
        result = self.capture()
        self.assertEqual((result['kind'],result['image_key'],result['image_set']), (1,'WBic',1015))
        self.assertFalse(result['atomic_snapshot'])
        self.assertIn('tile_identity',result['unavailable'])
    def test_unmapped_handler_and_stale_membership(self):
        self.member = 0
        with self.assertRaisesRegex(ValueError,'current displayed'):self.capture()
        self.member = self.item
        self.memory[self.table+0x154] = struct.pack('<2I',0x77777,0x400010)
        with self.assertRaisesRegex(ValueError,'unmapped'):self.capture()
    def test_mid_capture_change(self):
        calls = iter([self.item, 0])
        with self.assertRaisesRegex(ValueError,'changed during'):
            panel.capture_item(self.read,self.item,self.guards,lambda:next(calls))
    def test_live_guard_changed(self):
        self.memory[0x400000] = b'nope'
        with self.assertRaisesRegex(ValueError,'code differs'):self.capture()
    def test_short_read_process_end_and_invalid_range(self):
        with self.assertRaisesRegex(ValueError,'Short'):panel.exact(lambda *_:b'',self.item,4)
        with self.assertRaisesRegex(ValueError,'Invalid'):panel.exact(self.read,0,4)
        def ended(*_):raise OSError('process ended')
        with self.assertRaises(OSError):panel.capture_item(ended,self.item,self.guards,lambda:self.item)
    def test_unknown_build_rejected_before_evidence_or_offsets(self):
        with self.assertRaisesRegex(ValueError,'Unsupported'):panel.profile(b'unknown')
    def test_no_game_write_or_execution_api(self):
        source=Path(panel.__file__).read_text()
        for forbidden in ('WriteProcessMemory','VirtualAllocEx','CreateRemoteThread','SendMessage','sleep('):
            self.assertNotIn(forbidden,source)

