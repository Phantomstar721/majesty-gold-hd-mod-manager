"""Full unnormalized observer bodies, mandatory three-version fixtures."""
import hashlib
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage

ROOT = Path(__file__).resolve().parents[1]


class ObserverBodyTests(unittest.TestCase):
    def test_research_companion_ids_in_all_three_native_presenters(self):
        for env, entry in (('MAJESTY_PUBLIC_EXE',0xa8870),
                           ('MAJESTY_BETA2_EXE',0xa9160),
                           ('MAJESTY_GOG_EXE',0xa9710)):
            self.assertTrue(os.environ.get(env),env+' is required')
            image = PeImage(os.environ[env])
            # Independently pinned single-row presenter instructions: EBX is
            # the action ID; EBP gets price ID, ECX gets icon ID.
            self.assertEqual(image.read(entry+0xb7,6),bytes.fromhex('8dabe8030000'))
            self.assertEqual(image.read(entry+0xc8,6),bytes.fromhex('8d8bf4010000'))

    def test_custom_guild_factory_selector_bypasses_all_unknown_returns(self):
        source = (ROOT/'runtime/MajestyModManagerRuntime.cpp').read_text()
        resolver = source.split('extern "C" void __stdcall ResolveDialogFactoryRequest(',1)[1].split('__declspec(naked)',1)[0]
        route = resolver.split('if ((requested & 0xFFFFu) == 0x4743u) {',1)[1].split('\n    }',1)[0]
        self.assertIn('*idAddress = kAp10DialogId;', route)
        self.assertIn('return;', route)
        self.assertNotIn('idAddress[', route)  # preserve layout and context arguments
        self.assertLess(resolver.index('FindPanelByChildDialog'), resolver.index('requested & 0xFFFFu'))
        self.assertLess(resolver.index('requested & 0xFFFFu'), resolver.index('requested == kAp10DialogId'))
        # Execute only the stock switch's compare/jump decision instructions.
        # Stop before allocation/constructors; no game code is executed.
        def destination(image, start, selector):
            pc, lhs, rhs = start + 0x26, selector, 0
            for _ in range(100):
                code = image.read(pc, 18)
                if code[:2] == b'\x81\xf9':
                    rhs = struct.unpack_from('<I',code,2)[0]; pc += 6
                elif code[:2] in (b'\x0f\x87', b'\x0f\x84', b'\x0f\x85'):
                    take = {0x87: lhs > rhs, 0x84: lhs == rhs, 0x85: lhs != rhs}[code[1]]
                    pc += 6 + (struct.unpack_from('<i',code,2)[0] if take else 0)
                elif code[0] in (0x77,0x74,0x75):
                    take = {0x77: lhs > rhs, 0x74: lhs == rhs, 0x75: lhs != rhs}[code[0]]
                    pc += 2 + (struct.unpack_from('<b',code,1)[0] if take else 0)
                elif code[:2] == b'\x6a\x34' or code[:4] == b'\x8b\x4c\x24\x04':
                    return pc
                else:
                    self.fail('Unexpected stock switch instruction at %#x: %s' % (pc,code.hex()))
            self.fail('Stock switch did not terminate')
        for env, start, common, constructor in (
            ('MAJESTY_PUBLIC_EXE',0x10ac00,0x10c03f,0x10be9c),
            ('MAJESTY_BETA2_EXE',0x11b150,0x11c58f,0x11c3ec),
            ('MAJESTY_GOG_EXE',0x10d060,0x10e49f,0x10e2fc)):
            self.assertTrue(os.environ.get(env),env+' is required')
            image = PeImage(os.environ[env])
            self.assertEqual(destination(image,start,0x30315041),constructor)
            self.assertNotEqual(destination(image,start,0x34304743),common)
            for number in range(100):
                requested = int.from_bytes(('CG%02d'%number).encode(),'little')
                effective = 0x30315041 if requested & 0xffff == 0x4743 else requested
                self.assertEqual(destination(image,start,effective),constructor)

    def test_repeated_registration_rebinds_without_reinstalling_process_hooks(self):
        text=(ROOT/'runtime/AttackObservationRuntime.cpp').read_text()
        install=text.split('bool MajestyAttackObservation::InstallRuntime(',1)[1].split('const MajestyAttackObservation::Memory&',1)[0]
        repeated=install.split('if (installed) {',1)[1].split('// Require the complete stock creator',1)[0]
        self.assertIn('RegisterBindings(base,registration)',repeated)
        self.assertIn('return ok?diagnostic.Accept("reregistered"):false;',repeated)
        self.assertIn('fault || GetCurrentThreadId()!=ownerThread',repeated)
        self.assertNotIn('Patch(',repeated)
        self.assertLess(install.index('if (installed)'),install.index('guardedBody('))
        self.assertLess(install.index('if (installed)'),install.index('AuditedStartup('))
        placement=(ROOT/'runtime/CheckedPlacementRuntime.cpp').read_text().split('bool MajestyCheckedPlacement::InstallPreparedRuntime(',1)[1]
        once,aliases=placement.split('    const char* suffixes[]=',1)
        self.assertIn('if(!installed) {',once)
        self.assertIn('InstallCastObservers(preparedBuild)',once)
        self.assertIn('installed=true;\n    }',once)
        self.assertIn('registration(',aliases)
        self.assertNotIn('InstallCastObservers',aliases)

    def test_startup_selects_profile_before_proof_preparation_and_hooks(self):
        text = (ROOT / 'runtime/MajestyModManagerRuntime.cpp').read_text()
        loader = text.split('CapabilityManifestState LoadRuntimeCapabilityManifest() {',1)[1].split('g_runtimeCapabilities = std::move(manifest);',1)[0]
        self.assertLess(loader.index('ParseManifest('),loader.index('SelectMajestyBuildProfile()'))
        self.assertLess(loader.index('SelectMajestyBuildProfile()'),loader.index('MajestyAttackObservation::PrepareRuntime('))
        self.assertLess(loader.index('MajestyAttackObservation::PrepareRuntime('),loader.index('MajestyCheckedPlacement::PrepareRuntime('))
        self.assertIn('if (!SelectMajestyBuildProfile())',loader)
        self.assertIn('return CapabilityManifestState::Invalid;',loader.split('if (!SelectMajestyBuildProfile())',1)[1].split('if (manifest.Has',1)[0])
        startup=text.split('DWORD WINAPI InitializeRuntime(void*) {',1)[1]
        self.assertLess(startup.index('LoadRuntimeCapabilityManifest()'),startup.index('ValidateMajestyBuildProfile()'))
        self.assertLess(startup.index('ValidateMajestyBuildProfile()'),startup.index('InstallGogStandardMods()'))
        self.assertNotIn('SelectMajestyBuildProfile()',startup)

    def test_private_image_windows_for_every_supported_version(self):
        text = (ROOT / 'runtime/ImageBodyProfiles.h').read_text()
        for profile, env in (('Public','MAJESTY_PUBLIC_EXE'),('Beta2','MAJESTY_BETA2_EXE'),('Gog','MAJESTY_GOG_EXE')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            block = text.split('ImageBodies'+profile+'() {',1)[1].split('return bodies;',1)[0]
            rows = re.findall(r'\{(0x[0-9a-f]+),(0x[0-9a-f]+),\{([^}]+)\}\}, // (\w+)',block)
            self.assertEqual(len(rows),15)
            for address,size,digest,name in rows:
                with self.subTest(profile=profile,window=name):
                    self.assertEqual(hashlib.sha256(image.read(int(address,16)-image.base,int(size,16))).digest(),
                                     bytes(int(x,16) for x in digest.split(',')))

    def test_cast_bodies_for_every_supported_version(self):
        text = (ROOT / 'runtime/CastBodyProfiles.h').read_text()
        for profile, env in (('Public', 'MAJESTY_PUBLIC_EXE'), ('Beta2', 'MAJESTY_BETA2_EXE'), ('Gog', 'MAJESTY_GOG_EXE')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            block = text.split('CastBodies' + profile + '() {', 1)[1].split('return bodies;', 1)[0]
            rows = re.findall(r'\{(0x[0-9a-f]+),(0x[0-9a-f]+),\{([^}]+)\}\}, // (\w+)', block)
            self.assertEqual(len(rows), 19)
            for address, size, digest, name in rows:
                with self.subTest(profile=profile, body=name):
                    actual = image.read(int(address, 16) - image.base, int(size, 16))
                    self.assertEqual(hashlib.sha256(actual).digest(), bytes(int(x, 16) for x in digest.split(',')))

    def test_action_guards_match_reviewed_profile_tests(self):
        from test_dawnfall_action_profiles import PROFILES, LENGTHS
        text = (ROOT / 'runtime/ActionBodyProfiles.h').read_text()
        for name, profile in zip(('SteamPublic', 'SteamBeta2', 'Gog'), PROFILES):
            block = text.split('ActionBody ' + name + '[]={', 1)[1].split('};', 1)[0]
            rows = [tuple(int(x, 16) for x in r) for r in re.findall(r'\{(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+)\}', block)]
            self.assertEqual(rows[:11], list(zip(profile[4], LENGTHS, profile[5])))
            self.assertEqual(len(rows), 14)
            from test_fade_persistence_profiles import fingerprint
            self.assertTrue(os.environ.get(profile[0]), profile[0] + ' is required')
            image = PeImage(os.environ[profile[0]])
            for address, size, digest in rows:
                self.assertEqual(fingerprint(image.read(address-image.base, size)), digest)

    def test_complete_bodies_for_every_supported_version(self):
        text = (ROOT / 'runtime/ObserverBodyProfiles.h').read_text()
        for profile, env in (('Public', 'MAJESTY_PUBLIC_EXE'),
                             ('Beta', 'MAJESTY_BETA2_EXE'),
                             ('Gog', 'MAJESTY_GOG_EXE')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            block = text.split('ObserverBodies' + profile + '() {', 1)[1].split('return bodies;', 1)[0]
            rows = re.findall(r'\{(0x[0-9a-f]+),(0x[0-9a-f]+),\{([^}]+)\}\}, // (\w+)', block)
            self.assertEqual(len(rows), 18)
            for address, size, digest, name in rows:
                with self.subTest(profile=profile, body=name):
                    actual = image.read(int(address, 16) - image.base, int(size, 16))
                    expected = bytes(int(x, 16) for x in digest.split(','))
                    self.assertEqual(hashlib.sha256(actual).digest(), expected)

    def test_submission_never_reads_retired_storage(self):
        text = (ROOT / 'runtime/AttackObservationRuntime.cpp').read_text()
        submit = text.split('Word __fastcall Submit(', 1)[1].split('void __fastcall WorldDestroy', 1)[0]
        before, after = submit.split('const Word result=', 1)
        self.assertIn('releaseContext.projectile=id', before)
        self.assertIn('life.ContextAllowed(', before)
        self.assertNotIn('Read(order,', after)
        self.assertNotIn('Read(unit,', after)
        text = (ROOT / 'runtime/CheckedCastWindows.cpp').read_text()
        submit = text.split('void MajestyCheckedPlacement::ObserveCastSubmit', 1)[1].split('bool MajestyCheckedPlacement::BeginObservedCast', 1)[0]
        self.assertLess(submit.index('Capture(unit,actor)'), submit.index('ContainsOrder(unit,channel,order)'))
