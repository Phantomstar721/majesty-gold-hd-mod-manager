"""Pin the distinct stock save-loader routes; not whole-world load acceptance."""
import os
import struct
import unittest
from pathlib import Path
import re
from test_occupant_runtime_profiles import PeImage
from test_fade_persistence_profiles import fingerprint


class DawnfallLoadProfilesTests(unittest.TestCase):
    def test_menu_saved_world_handoff(self):
        text = (Path(__file__).parents[1] / 'runtime/WorldAttachmentProfiles.h').read_text()
        for env, name in (('MAJESTY_PUBLIC_EXE','publicBuild'),
                          ('MAJESTY_BETA2_EXE','betaBuild'),('MAJESTY_GOG_EXE','gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            values = [int(v,16) for v in re.search(r'WorldAttachmentProfile '+name+r'\{([^}]+)\}',text)[1].split(',')]
            returned, digest = values[12:14]
            image = PeImage(os.environ[env])
            window = image.read(returned-19-image.base,19)
            self.assertEqual(fingerprint(window),digest)
            # Nonnull output, literal mode0, returned world and owning controller.
            self.assertEqual(window[5:14],bytes.fromhex('85c0741a6a00508bcb'))
            self.assertEqual(image.target(returned-5-image.base)+image.base,values[5])
            if name=='publicBuild':
                self.assertEqual(image.target(returned-19-image.base)+image.base,0x475530)
            else:
                self.assertEqual(window[:5],bytes.fromhex('ffd28b45ec'))
        runtime=(Path(__file__).parents[1]/'runtime/AttackObservationRuntime.cpp').read_text()
        self.assertIn('guardedBody(attachmentProfile->savedMenuReturn-19,19,attachmentProfile->savedMenuHash)',runtime)

    def test_completed_world_builder_profiles(self):
        text = (Path(__file__).parents[1] / 'runtime/WorldAttachmentProfiles.h').read_text()
        bodies = []
        for env, name in (('MAJESTY_PUBLIC_EXE', 'publicBuild'),
                          ('MAJESTY_BETA2_EXE', 'betaBuild'),
                          ('MAJESTY_GOG_EXE', 'gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            values = re.search(r'WorldAttachmentProfile ' + name + r'\{([^}]+)\}', text)[1]
            saved, created, builder, digest, caller_digest, *_ = [int(v, 16) for v in values.split(',')]
            image = PeImage(os.environ[env])
            body = bytearray(image.read(builder - image.base, 0x575))
            self.assertEqual(fingerprint(body), digest)
            caller = image.read(created - 0x3F - image.base, 0x4D)
            self.assertEqual(fingerprint(caller), caller_digest)
            self.assertEqual(image.target(created - 0x3D - image.base) + image.base, builder)
            self.assertEqual(image.target(saved - 5 - image.base), image.target(created - 5 - image.base))
            # Failure returns zero. Success takes the retained world at+C4,
            # completes temporary-owner cleanup, then returns that same world.
            self.assertEqual(body[0x74:0x76], bytes.fromhex('33c0'))
            self.assertEqual(body[0x52B:0x531], bytes.fromhex('8bb6c4000000'))
            self.assertEqual(body[0x559:0x55B], bytes.fromhex('8bc6'))
            self.assertEqual(body[-7:], bytes.fromhex('81c4a0000000c3'))
            # Only external code/data operands are normalized. Branches,
            # virtual slots, ownership fields and cleanup order remain exact.
            for offset in (0x3,0x19,0x34,0x4B,0x59,0x70,0x7C,0x8A,0x8F,
                           0xA0,0xBF,0xCB,0xE6,0xFC,0x106,0x11C,0x145,
                           0x16A,0x19E,0x1C6,0x1E9,0x20B,0x232,0x239,
                           0x26D,0x294,0x29B,0x2CE,0x2F5,0x2FC,0x330,
                           0x357,0x35E,0x39D,0x3B2,0x3B8,0x3D5,0x3FD,
                           0x404,0x455,0x46D,0x477,0x520,0x526,0x541,0x555):
                body[offset:offset+4] = bytes(4)
            bodies.append(bytes(body))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0], bodies[2])

    def test_attach_mode_dispatch_and_service_slot(self):
        root = Path(__file__).parents[1]
        text = (root / 'runtime/WorldAttachmentProfiles.h').read_text()
        observer = (root / 'runtime/AttackObservationNativeProfiles.h').read_text()
        bodies = []
        for env, name in (('MAJESTY_PUBLIC_EXE', 'publicBuild'),
                          ('MAJESTY_BETA2_EXE', 'betaBuild'),
                          ('MAJESTY_GOG_EXE', 'gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            values = re.search(r'WorldAttachmentProfile ' + name + r'\{([^}]+)\}', text)[1]
            saved, created, _, _, _, attach, digest, slot, *_ = [int(v,16) for v in values.split(',')]
            native = re.search(r'ObservationNativeProfile ' + name + r'\{([^}]+)\}', observer)[1]
            runtime_global = [int(v,16) for v in native.split(',')][13]
            image = PeImage(os.environ[env])
            body = bytearray(image.read(attach-image.base, 0x108))
            self.assertEqual(fingerprint(body), digest)
            self.assertEqual(image.target(saved-5-image.base)+image.base, attach)
            self.assertEqual(image.target(created-5-image.base)+image.base, attach)
            # Public has a different service virtual slot. This call stays in
            # the original stock body, not a manually replayed beta2 call.
            self.assertEqual(body[0x68:0x6D], bytes((0x8B,0x42,slot,0x56,0xFF)))
            self.assertEqual(body[0x6D], 0xD0)
            self.assertEqual(body[0xF4:0xF7], bytes.fromhex('c20800'))
            # Modes 0/3 publish + select; 1 selects then deletes; 2 only publishes.
            table = struct.unpack_from('<4I', body, 0xF8)
            self.assertEqual(tuple(x-attach for x in table), (0x7E,0x9A,0xB4,0x7E))
            for offset in (0x80,0x8E,0x9C,0xB6):
                self.assertEqual(struct.unpack_from('<I', body, offset)[0], runtime_global)
            self.assertEqual(body[0xA6:0xC2], bytes.fromhex(
                '85f674188b168b026a018bceeb0c8b0d') + struct.pack('<I',runtime_global) +
                bytes.fromhex('8b118b420456ffd0'))
            for offset in (3,18,40,66,84,92,122,128,142,148,156,162,182):
                body[offset:offset+4] = bytes(4)
            body[0x6A] = 0
            for offset, value in zip(range(0xF8,0x108,4), table):
                struct.pack_into('<I', body, offset, value-attach)
            bodies.append(bytes(body))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0], bodies[2])

    def test_additional_direct_builder_callers(self):
        text = (Path(__file__).parents[1] / 'runtime/WorldAttachmentProfiles.h').read_text()
        bodies = [[], []]
        for env, name in (('MAJESTY_PUBLIC_EXE', 'publicBuild'),
                          ('MAJESTY_BETA2_EXE', 'betaBuild'),
                          ('MAJESTY_GOG_EXE', 'gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            values = re.search(r'WorldAttachmentProfile ' + name + r'\{([^}]+)\}', text)[1]
            profile = [int(v,16) for v in values.split(',')]
            image = PeImage(os.environ[env])
            for index, length in enumerate((0x22, 0x21)):
                returned, digest = profile[8+index*2:10+index*2]
                start = returned-length
                body = bytearray(image.read(start-image.base, length))
                self.assertEqual(fingerprint(body), digest)
                self.assertEqual(image.target(start+4-image.base)+image.base, profile[2])
                self.assertEqual(image.target(returned-5-image.base)+image.base, profile[5])
                # Builder EAX is passed directly as the world. Its +A4 field
                # receives an existing caller value, not a substitute world.
                argument = bytes.fromhex('6a0050') if index==0 else bytes.fromhex('5350')
                self.assertEqual(body[13:13+len(argument)], argument)
                self.assertEqual(body[13+len(argument):19+len(argument)], bytes.fromhex('8988a4000000'))
                # GOG's first caller uses stack20 instead of stack1C. Preserve
                # that difference explicitly; the two operands must agree.
                expected_stack = 0x20 if name=='gogBuild' and index==0 else (0x1C if index==0 else 0x68)
                self.assertEqual(body[3], expected_stack)
                self.assertEqual(body[12], expected_stack)
                body[3] = body[12] = 0
                for offset in (5, length-11, length-4): body[offset:offset+4] = bytes(4)
                bodies[index].append(bytes(body))
        for group in bodies:
            self.assertEqual(group[0], group[1])
            self.assertEqual(group[0], group[2])

    def test_separate_nonnull_world_construction_route(self):
        # Bounded caller evidence only. The builder and later startup service
        # still require lifecycle certification before admitting this route.
        bodies = []
        for env, start, builder, attach, digest, field_a, field_b in (
            ('MAJESTY_PUBLIC_EXE', 0x4946C0, 0x4E96D0, 0x424CC0, 0xC4C47D10, 0x70, 0x258),
            ('MAJESTY_BETA2_EXE', 0x494E70, 0x4E9C90, 0x425C90, 0x23E2DADB, 0x68, 0x238),
            ('MAJESTY_GOG_EXE', 0x495420, 0x4EA3D0, 0x424F20, 0x751F5191, 0x68, 0x238),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            body = bytearray(image.read(start - image.base, 0x4D))
            self.assertEqual(fingerprint(body), digest)
            self.assertEqual(image.target(start + 2 - image.base) + image.base, builder)
            self.assertEqual(image.target(start + 0x3A - image.base) + image.base, attach)
            # EDI receives the builder result; null jumps past the attach call.
            self.assertEqual(body[7:13], bytes.fromhex('8bf885ff7432'))
            self.assertEqual(13 + body[12], 0x3F)
            self.assertEqual(body[0x26:0x29], bytes.fromhex('6a0057'))
            self.assertEqual(body[0x3F], 0xE8)
            self.assertEqual(body[0x44:], bytes.fromhex('8b108bc88b4240ffd0'))
            self.assertEqual(body[0x1C], field_a)
            self.assertEqual(struct.unpack_from('<I', body, 0x2B)[0], field_b)
            for offset in (3, 0x16, 0x22, 0x34, 0x3B, 0x40):
                body[offset:offset + 4] = bytes(4)
            body[0x1C] = 0
            body[0x2B:0x2F] = bytes(4)
            bodies.append(bytes(body))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0], bodies[2])

    def test_stock_loader_routes(self):
        bodies = []
        for env, table, load_slot, load, digest, path_slot, body_slot, attach_call, attach in (
            ('MAJESTY_PUBLIC_EXE', 0x73B36C, 0x40, 0x44DBC0, 0x845DFEE1, 0x48, 0x0C, 0x4252BC, 0x424CC0),
            ('MAJESTY_BETA2_EXE', 0x75442C, 0x48, 0x44EAD0, 0x9E77264C, 0x50, 0x10, 0x42628C, 0x425C90),
            ('MAJESTY_GOG_EXE', 0x753474, 0x48, 0x44E9F0, 0x4FF97C8E, 0x50, 0x10, 0x42551C, 0x424F20),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            def read(va, count):
                return image.read(va - image.base, count)
            def word(va):
                return struct.unpack('<I', read(va, 4))[0]
            locator = word(table - 4)
            descriptor = word(locator + 12)
            name = b'.?AVGS_MapIOManager@@\0'
            self.assertEqual(read(descriptor + 8, len(name)), name)
            self.assertEqual(word(table + load_slot), load)
            body = bytearray(read(load, 0x90))
            self.assertEqual(fingerprint(body), digest)
            self.assertEqual(body[0x43:0x46], bytes((0x8B, 0x40, path_slot)))
            self.assertEqual(body[0x5A:0x5D], bytes((0x8B, 0x52, body_slot)))
            self.assertEqual(body[-3:], bytes.fromhex('c20800'))
            # Permit only independently understood image references and the
            # two explicitly identified virtual-slot differences.
            for start in (3, 0x14, 0x31, 0x76):
                body[start:start + 4] = bytes(4)
            body[0x45] = body[0x5C] = 0
            bodies.append(bytes(body))
            self.assertEqual(image.target(attach_call - image.base) + image.base, attach)
            # The post-attach continuation calls service +40 on each build.
            self.assertEqual(read(attach_call + 10, 9), bytes.fromhex('8b108bc88b4240ffd0'))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0], bodies[2])
