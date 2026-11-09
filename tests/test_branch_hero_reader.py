import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import read_hero_diagnostic as reader
from test_public_hero_reader import fixture


def registry_fixture(profile):
    actor, put, read = fixture()
    for slot, value in zip((0x30, 0xC0, 0x124), profile['methods']):
        put(profile['tables'][0] + slot, value)
    put(actor, profile['tables'][0])
    put(profile['clock'], 100)
    root, owner, registry = 0x600000, 0x601000, 0x602000
    head, node, agent = 0x603000, 0x604000, 0x605000
    for address, value in ((profile['root'], root), (root + 32, owner),
        (owner + 4, registry), (registry + 0x58 + 24, head), (head + 4, node),
        (node, head), (node + 8, head), (node + 12, 7), (node + 16, agent),
        (node + 20, 0), (agent + 0x30, 42), (agent + 0x34, actor), (agent + 0x38, 0)):
        put(address, value)
    if profile['selection']:
        put(profile['selection'], 0x606000)
        put(0x606048, actor)
    put(agent, 0x607000)
    put(0x607018, 0x607100)
    put(0x607104, 0x607100)
    return actor, agent, put, read


class BranchReaderTests(unittest.TestCase):
    def test_public_registry_with_selected_candidate(self):
        actor, _, _, read = registry_fixture(reader.PUBLIC)
        row = reader.Snapshot(read, reader.PUBLIC).capture(actor)
        self.assertTrue(row['registry_membership_observed'])
        self.assertTrue(row['current_selection_verified'])
        self.assertFalse(row['lifetime_epoch_verified'])
        self.assertEqual(row['capabilities']['properties_and_dispatch'], 'supported')

    def test_public_no_selection_is_explicit(self):
        _, _, put, read = registry_fixture(reader.PUBLIC)
        put(reader.PUBLIC['selection'], 0)
        with self.assertRaisesRegex(ValueError, 'mapping unavailable'):
            reader.Snapshot(read, reader.PUBLIC).capture()

    def test_beta_selection_uses_its_profile(self):
        profile = dict(reader.BETA, properties=False)
        _, _, _, read = registry_fixture(profile)
        row = reader.Snapshot(read, profile).capture()
        self.assertTrue(row['current_selection_verified'])
        self.assertEqual(row['native']['clock_begin'], 100)

    def test_deleted_and_identity_mismatch(self):
        for offset, value in ((0x38, 1), (0x30, 99), (0x34, 0)):
            actor, agent, put, read = registry_fixture(reader.PUBLIC)
            put(agent + offset, value)
            with self.assertRaises(ValueError):
                reader.Snapshot(read, reader.PUBLIC).capture(actor)

    def test_selection_changes(self):
        profile = dict(reader.BETA, properties=False)
        _, _, put, read = registry_fixture(profile)
        count = 0
        def changing(address, size):
            nonlocal count
            if address == profile['selection']:
                count += 1
                if count == 2:
                    put(address, 0)
            return read(address, size)
        with self.assertRaisesRegex(ValueError, 'Selection changed'):
            reader.Snapshot(changing, profile).capture()

    def test_read_failure_and_process_exit(self):
        for error in (OSError('access denied'), OSError('process ended')):
            def failed(address, size):
                raise error
            with self.assertRaises(OSError):
                reader.Snapshot(failed, reader.PUBLIC).capture(0x100000)
        with self.assertRaisesRegex(ValueError, 'Short'):
            reader.Snapshot(lambda a, n: b'', reader.PUBLIC).capture(0x100000)

    def test_unsupported_profile_and_no_writes(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported executable'):
            reader.identify(b'unknown executable')
        source = Path(reader.__file__).read_text()
        for name in ('WriteProcessMemory', 'CreateRemoteThread', 'VirtualAllocEx', 'VirtualProtectEx'):
            self.assertNotIn(name, source)

    def test_string_length_not_capacity_and_wide_strings(self):
        for profile in (reader.PUBLIC, reader.BETA):
            _, _, put, read = registry_fixture(profile)
            put(0x610000, 0x611000)
            put(0x610004, 64)  # spare capacity is not the text length
            put(0x610008, 3)
            put(0x611000, int.from_bytes(b'abc\0', 'little'))
            self.assertEqual(reader.Snapshot(read, profile).string(0x610000), 'abc')
            put(0x610004, 0x01000004)
            put(0x610008, 1)
            put(0x611000, int.from_bytes('X\0'.encode('utf-16-le'), 'little'))
            self.assertEqual(reader.Snapshot(read, profile).string(0x610000), 'X')

    def test_function_schedule_fields(self):
        for profile in (reader.PUBLIC, reader.BETA):
            _, _, put, read = registry_fixture(profile)
            for offset, value in ((4, 8), (8, 0x610000), (0x44, 200), (0x48, 123), (0x4C, 128)):
                put(0x612000 + offset, value)
            for offset, value in ((0, 0x611000), (4, 64), (8, 3)):
                put(0x610000 + offset, value)
            put(0x611000, int.from_bytes(b'abc\0', 'little'))
            value = reader.Snapshot(read, profile).value(0x612000)
            self.assertEqual(value, dict(function='abc', interval=200, last_dispatch=123, flags=128))

    def test_property_map_and_target_reference_on_both_branches(self):
        for profile in (reader.PUBLIC, reader.BETA):
            _, _, put, read = registry_fixture(profile)
            node, text, value = 0x608000, 0x609000, 0x60A000
            for address, word in ((0x607104, node), (node, 0x607100),
                (node + 8, 0x607100), (node + 12, text),
                (node + 16, 32), (node + 20, 6), (node + 24, value),
                (node + 28, 0), (text, int.from_bytes(b'Targ', 'little')),
                (text + 4, int.from_bytes(b'et\0\0', 'little')),
                (value + 4, 5), (value + 8, 99)):
                put(address, word)
            result = reader.Snapshot(read, profile).capture()
            self.assertEqual(result['properties']['target'], {'agent_id': 99})
            self.assertEqual(result['target'], {'gpl_id': 99, 'registry_present': False})
            put(node, node)
            with self.assertRaisesRegex(ValueError, 'Cyclic'):
                reader.Snapshot(read, profile).capture()

    def test_admitted_identities_are_explicit(self):
        self.assertEqual(len(reader.PROFILES), 3)
        self.assertNotEqual(reader.PUBLIC['selection'], reader.BETA['selection'])
        self.assertNotEqual(reader.PUBLIC['root'], reader.BETA['root'])
        self.assertNotEqual(reader.PUBLIC['clock'], reader.BETA['clock'])


if __name__ == '__main__':
    unittest.main()
