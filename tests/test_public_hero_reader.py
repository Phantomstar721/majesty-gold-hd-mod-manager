"""Offline fixtures for the explicitly partial, read-only public diagnostic."""
import importlib.util
from pathlib import Path
import struct

import unittest

check = unittest.TestCase()

SOURCE = Path(__file__).parents[1] / 'scripts' / 'read_public_hero.py'
spec = importlib.util.spec_from_file_location('public_reader', SOURCE)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def fixture():
    memory = {}
    actor, description = 0x100000, 0x200000

    def put(address, value):
        memory.update({address + i: b for i, b in enumerate(struct.pack('<I', value))})

    for offset in range(0, 0xA4, 4):
        put(actor + offset, 0)
    for offset, value in {0: reader.UNIT_VTABLE, 0x70: 42, 0x7C: int.from_bytes(b'WHP1', 'little'),
                          0x90: description, 0x94: 0x300000, 0x58: 100 << 11, 0x5C: 200 << 11}.items():
        put(actor + offset, value)
    put(description + 4, int.from_bytes(b'WHP1', 'little'))
    put(description + 8, 1)
    put(reader.CLOCK, 123)
    for slot, value in ((0x30, 0x4474F0), (0xC0, 0x441FE0), (0x124, 0x448A40)):
        put(reader.UNIT_VTABLE + slot, value)

    def read(address, size):
        return bytes(memory[address + i] for i in range(size))

    return actor, put, read


def test_partial_snapshot():
    actor, _, read = fixture()
    result = reader.capture(read, actor)
    assert result['native_id'] == 42
    assert result['outside_pixel_position'] == [100, 200]
    assert result['orders'] == []
    assert not result['current_selection_verified']
    assert not result['atomic_snapshot']


def test_selected_other_hero_retains_description_identity_checks():
    actor, put, read = fixture()
    solarus = int.from_bytes(b'AVK1', 'little')
    put(actor + 0x7C, solarus)
    put(0x200004, solarus)
    with check.assertRaisesRegex(ValueError, 'WHP1'):
        reader.capture(read, actor)
    assert reader.capture(read, actor, expected_description=None)['description'] == 'AVK1'
    put(0x200004, 0)
    with check.assertRaisesRegex(ValueError, 'description'):
        reader.capture(read, actor, expected_description=None)


def test_invalid_actor():
    for offset, value in [(0, 0), (0x74, 4), (0x70, 0), (0x80, 8), (0x94, 0), (0x7C, 0)]:
        actor, put, read = fixture()
        put(actor + offset, value)
        with check.assertRaises(ValueError):
            reader.capture(read, actor)


def test_stale_actor():
    actor, put, read = fixture()
    count = 0

    def changing(address, size):
        nonlocal count
        if address == actor and size == 0x98:
            count += 1
            if count == 2:
                put(actor + 0x70, 43)
        return read(address, size)

    with check.assertRaisesRegex(ValueError, 'identity changed'):
        reader.capture(changing, actor)


def test_supported_vehicle_and_bad_method():
    actor, put, read = fixture()
    table = 0x73B08C
    put(actor, table)
    for slot, value in ((0x30, 0x4474F0), (0xC0, 0x441FE0), (0x124, 0x448A40)):
        put(table + slot, value)
    assert reader.capture(read, actor)['native_id'] == 42
    put(table + 0x124, 0)
    with check.assertRaisesRegex(ValueError, 'method table'):
        reader.capture(read, actor)


def test_description_mismatch():
    actor, put, read = fixture()
    put(0x200004, 0)
    with check.assertRaisesRegex(ValueError, 'description'):
        reader.capture(read, actor)


def test_rejects_bad_actor_address():
    actor, put, read = fixture()
    with check.assertRaisesRegex(ValueError, 'bounded'):
        reader.capture(read, 1)


def test_order_and_cycle():
    actor, put, read = fixture()
    stack, head, link, order = 0x400000, 0x400100, 0x400200, 0x400300
    for address, value in ((actor + 0x9C, stack), (stack + 4, actor), (stack + 0x1C, head),
                           (head, link), (link, head), (link + 8, order), (order + 0x10, 10),
                           (order + 0x34, 0x500000), (order + 0x3C, 73)):
        put(address, value)
    assert reader.capture(read, actor)['orders'][0]['target_id'] == 73
    put(link, link)
    with check.assertRaisesRegex(ValueError, 'Cyclic'):
        reader.capture(read, actor)
    put(stack + 4, actor + 4)
    with check.assertRaisesRegex(ValueError, 'owner'):
        reader.capture(read, actor)


def test_read_failure_and_short_read():
    with check.assertRaisesRegex(ValueError, 'Short'):
        reader.capture(lambda address, size: b'', 0x100000)
    def failed(address, size):
        raise OSError('access denied')
    with check.assertRaisesRegex(OSError, 'access denied'):
        reader.capture(failed, 0x100000)


def test_image_and_context_gates():
    with check.assertRaisesRegex(ValueError, 'Unsupported executable'):
        reader.verify_image(b'wrong build')
    with check.assertRaisesRegex(ValueError, 'No AP20'):
        reader.logged_actor('')
    assert reader.logged_actor('today Dialog creation entry: id=0x30325041 context=0x100000') == ('today', 0x100000)


def test_no_write_access_or_mutating_apis():
    source = SOURCE.read_text()
    assert 'OpenProcess(0x1010, False, pid)' in source
    for forbidden in ('WriteProcessMemory', 'VirtualAllocEx', 'VirtualProtectEx', 'CreateRemoteThread', 'SuspendThread'):
        assert forbidden not in source


def test_series_bounds_and_identity_change():
    actor, put, read = fixture()
    for samples, interval in ((0, 0.1), (101, 0.1), (2, 0), (2, 1)):
        with check.assertRaises(ValueError):
            reader.capture_series(read, actor, samples, interval)
    def change(_):
        put(actor + 0x70, 43)
    result = reader.capture_series(read, actor, 3, sleep=change)
    assert len(result['samples']) == 1
    assert 'identity changed' in result['stopped_on_error']
    assert not result['current_selection_verified']


def test_series_clock_progress_and_read_failure():
    actor, put, read = fixture()
    def advance(_):
        put(reader.CLOCK, 124)
    result = reader.capture_series(read, actor, 2, sleep=advance)
    assert [row['clock_begin'] for row in result['samples']] == [123, 124]
    assert not result['atomic_snapshot']
    result = reader.capture_series(lambda address, size: b'', actor, 2)
    assert result['samples'] == []
    assert 'Short' in result['stopped_on_error']


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(value) for name, value in globals().items()
                              if name.startswith('test_') and callable(value))


if __name__ == '__main__':
    unittest.main()
