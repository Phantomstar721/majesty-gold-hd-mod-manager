from pathlib import Path
import struct
from unittest import TestCase

from majesty_cam.bcd import definition_keys, BcdIndexError
from majesty_cam.gpl import DefinitionKind


def block(body=b'', version=1):
    return struct.pack('<II', len(body) + 16, version) + body + struct.pack('<II', 0, 0xffffffff)


def compiled(*keys):
    """Framed declaration-only fixture; never executed as bytecode."""
    tables = []
    for kind in DefinitionKind.PROTOTYPE, DefinitionKind.FUNCTION, DefinitionKind.EXPRESSION, DefinitionKind.DAT_BLOCK:
        names = [name for k, name in keys if k is kind]
        tables.append(struct.pack('<I', len(names)) + b''.join(name.encode() + b'\0' + block() for name in names))
    body = struct.pack('<I', 0) + block(struct.pack('<I', 0), 0) + block(b''.join(tables[:3])) + block(tables[3])
    root = block(body, 0xffffffff)
    return struct.pack('<I', len(root)) + root


class BcdTests(TestCase):
    def test_stock_compiler_fixture_indexes_all_definition_kinds_not_references(self):
        fixture = Path(__file__).parent / 'fixtures/bcd-ownership/Fixture.bcd.hex'
        data = bytes.fromhex(fixture.read_text())
        self.assertIn(b'Imported\0', data)  # A call, not an owned function.
        self.assertEqual(definition_keys(data), frozenset((
            (DefinitionKind.PROTOTYPE, 'agenttemplate'),
            (DefinitionKind.FUNCTION, 'owned'),
            (DefinitionKind.EXPRESSION, '#usedconstant'),
            (DefinitionKind.EXPRESSION, '#unusedconstant'),
            (DefinitionKind.DAT_BLOCK, 'ownedagent'),
        )))

    def test_empty_tables_and_separate_case_insensitive_namespaces(self):
        self.assertEqual(definition_keys(compiled()), frozenset())
        self.assertEqual(definition_keys(compiled((DefinitionKind.FUNCTION, 'Same'),
            (DefinitionKind.PROTOTYPE, 'same'))), frozenset((
                (DefinitionKind.FUNCTION, 'same'), (DefinitionKind.PROTOTYPE, 'same'))))

    def test_every_truncation_and_trailing_bytes_fail_closed(self):
        data = compiled((DefinitionKind.FUNCTION, 'Example'))
        for end in range(len(data)):
            with self.subTest(end=end), self.assertRaises(BcdIndexError):
                definition_keys(data[:end])
        with self.assertRaises(BcdIndexError):
            definition_keys(data + b'junk')

    def test_unknown_versions_errors_sizes_counts_and_names_fail_closed(self):
        data = compiled((DefinitionKind.FUNCTION, 'Example'))
        for offset, value in ((0, 0), (4, 8), (8, 0), (12, 1), (16, 0xffffffff),
                              (20, 1), (40, 2), (44, 0xffffffff)):
            damaged = bytearray(data)
            struct.pack_into('<I', damaged, offset, value)
            with self.subTest(offset=offset), self.assertRaises(BcdIndexError):
                definition_keys(bytes(damaged))
        for name in ('', 'bad name', 'x#y'):
            with self.subTest(name=name), self.assertRaises(BcdIndexError):
                definition_keys(compiled((DefinitionKind.FUNCTION, name)))
        with self.assertRaisesRegex(BcdIndexError, 'duplicate'):
            definition_keys(compiled((DefinitionKind.FUNCTION, 'One'), (DefinitionKind.FUNCTION, 'one')))
        damaged = bytearray(data)
        damaged[-1] = 0
        with self.assertRaisesRegex(BcdIndexError, 'terminator'):
            definition_keys(bytes(damaged))
