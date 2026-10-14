"""Native observer dependency links; not whole-provider activation evidence."""
import os
import hashlib
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage
def fingerprint(data):
    result = 2166136261
    for byte in data:
        result = ((result ^ byte) * 16777619) & 0xffffffff
    return result


class ObservationNativeProfilesTests(unittest.TestCase):
    def test_native_identity_and_registration_links(self):
        root = Path(__file__).parents[1]
        text = (root / 'runtime/AttackObservationNativeProfiles.h').read_text()
        resolves = []
        for env, name, unit_table, register_impact, resolve_hash in (
            ('MAJESTY_PUBLIC_EXE', 'publicBuild', 0x73A924, 0x4EEECC, 0x9AE9E45E),
            ('MAJESTY_BETA2_EXE', 'betaBuild', 0x7539E4, 0x4EF48C, 0x480F562E),
            ('MAJESTY_GOG_EXE', 'gogBuild', 0x752A2C, 0x4EFC3C, 0x480F562E),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            def read(va, count): return image.read(va - image.base, count)
            def word(va): return struct.unpack('<I', read(va, 4))[0]
            def target(va): return image.target(va - image.base) + image.base
            bodies = (root / 'runtime/ObserverBodyProfiles.h').read_text()
            label = {'publicBuild': 'Public', 'betaBuild': 'Beta', 'gogBuild': 'Gog'}[name]
            block = re.search(r'ObserverBodies' + label + r'\(\).*?bodies\[\]=\{(.*?)\n    \};', bodies,re.S)
            self.assertIsNotNone(block,label)
            for address,size,digest in re.findall(r'\{(0x[0-9a-f]+),(0x[0-9a-f]+),\{([^}]+)\}\}',block[1]):
                self.assertEqual(hashlib.sha256(read(int(address,16),int(size,16))).digest(),
                    bytes(int(v,16) for v in digest.split(',')), address)
            values = re.search(r'ObservationNativeProfile ' + name + r'\{([^}]+)\}', text)[1]
            (find_name, callbacks, actions, units, release, impact, pending,
             missile, animation, retire, catalog, arguments, resolve,
             runtime, all_units, impact_global, impact_function, find_unit) = [
                int(v.strip(), 16) for v in values.split(',')]
            for table, typename in ((missile, 'GS_OrderMoveMissile'),
                                    (animation, 'OrderInitAction'),
                                    (all_units, 'GE_AllUnitsList')):
                descriptor = word(word(table-4)+12)
                expected = ('.?AV' + typename + '@@\0').encode()
                self.assertEqual(read(descriptor+8, len(expected)), expected)
            shared = (root / 'runtime/PairedOccupantLookupProfiles.h').read_text()
            rows = re.search(r'AllUnitsTables\[\] = \{([^}]+)\}', shared)[1]
            tables = [int(v.strip().rstrip('u'), 16)+image.base for v in rows.split(',')]
            stock = tables[('publicBuild','betaBuild','gogBuild').index(name)]
            locator = word(stock-4)
            self.assertEqual(word(locator+4), 0)  # primary receiver, no adjustment
            expected = b'.?AVAllUnitsList@@\0'
            self.assertEqual(read(word(locator+12)+8, len(expected)), expected)
            for slot in (0x28, 0x30):
                self.assertEqual(word(stock+slot), word(all_units+slot))
            self.assertEqual(word(unit_table+0x30), retire)
            self.assertEqual(read(release+0x16, 2), bytes.fromhex('8b0d'))
            self.assertEqual(word(release+0x18), actions)
            self.assertEqual(target(release+0x51), find_unit)
            self.assertEqual(read(catalog, 8), bytes.fromhex('8b898c00000085c9'))
            self.assertEqual(read(find_unit, 9), bytes.fromhex('568b74240885f67431'))
            # Registry singleton constructs the object that consumes this exact
            # ID/function table. Similar singleton bodies are not interchangeable.
            constructor = target(callbacks+0x46)
            self.assertEqual(read(constructor+0x44, 1), b'\x68')
            callback_table = word(constructor+0x45)
            self.assertEqual(word(callback_table), 0x1000)
            entries = dict(struct.unpack('<II', read(callback_table+8*i, 8)) for i in range(12))
            self.assertEqual(entries[0x1000], release)
            self.assertEqual(entries[0x100A], impact)
            self.assertEqual(entries[0x1008], pending)
            setter = target(register_impact)
            self.assertEqual(read(register_impact-5, 1), b'\x68')
            self.assertEqual(word(register_impact-4), impact_function)
            self.assertEqual(read(setter+4, 1), b'\xA1')
            self.assertEqual(word(setter+5), impact_global)
            self.assertEqual(read(setter+0x17, 2), bytes.fromhex('890d'))
            self.assertEqual(word(setter+0x19), impact_global)
            body = bytearray(read(resolve, 0x2B))
            self.assertEqual(fingerprint(body), resolve_hash)
            for offset in (8, 0xF, 0x24): body[offset:offset+4] = bytes(4)
            resolves.append(bytes(body))
            # Cross-check the existing independently profiled Manager helpers.
            movement = (root / 'runtime/MapQueryRuntime.cpp').read_text()
            suffix = {'publicBuild':'Public','betaBuild':'Beta','gogBuild':'Gog'}[name]
            hooks = (root / 'runtime/AttackObservationWindows.h').read_text()
            block = re.search(r'k' + suffix + r'HookWindows\[\] = \{(.*?)\n\};', hooks, re.S)[1]
            windows = re.findall(r'\{(0x[0-9A-F]+),(\d+),\{([^}]+)\}\}', block)
            self.assertEqual(len(windows),14)
            addresses = []
            for address, count, values in windows:
                address, count = int(address,16), int(count)
                expected = bytes(int(v,16) for v in values.split(','))
                self.assertEqual(len(expected),count)
                self.assertEqual(read(address,count),expected)
                addresses.append(address)
            self.assertEqual(addresses[2],retire)
            self.assertEqual(addresses[4],release)
            category_return={'publicBuild':0x4F141E,'betaBuild':0x4F19EE,'gogBuild':0x4F1EE0}[name]
            self.assertEqual(target(category_return-5),addresses[12])
            post_return={'publicBuild':0x4F1500,'betaBuild':0x4F1AD0,'gogBuild':0x4F1FC0}[name]
            self.assertEqual(target(post_return-5),addresses[13])
            self.assertEqual(read(addresses[12]+0x116,3),bytes.fromhex('c20400'))
            self.assertEqual(read(addresses[13]+0x10b,1),b'\xc3')
            route_text = (root / 'runtime/WorldAttachmentProfiles.h').read_text()
            route = re.search(r'WorldAttachmentProfile ' + name + r'\{([^}]+)\}',route_text)[1]
            saved, created = [int(v,16) for v in route.split(',')[:2]]
            self.assertEqual(target(saved-5),addresses[7])
            self.assertEqual(target(created-5),addresses[7])
            row = re.search(r'kMovement' + suffix + r' = \{([^}]+)\}', movement)[1]
            known = [int(v.strip(),16)+image.base for v in row.split(',')]
            self.assertEqual((resolve, find_name, units), tuple(known[1:4]))
            row = re.search(r'constexpr Profile k' + suffix + r' = \{([^}]+)\}', movement)[1]
            known = [int(v.strip(),16)+image.base for v in row.split(',')]
            self.assertEqual((arguments, runtime), tuple(known[6:8]))
        self.assertEqual(resolves[0], resolves[1])
        self.assertEqual(resolves[0], resolves[2])
