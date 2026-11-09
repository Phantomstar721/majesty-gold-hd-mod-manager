"""Exact offline impact witnesses. Does not install/enable interception.

All three executable paths are required when running this gate explicitly.
Boolean publication uses the separately reviewed stock frame preparation.
These are offline byte/ABI checks, not live acceptance or exception recovery.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import struct
import unittest

from test_occupant_runtime_profiles import PeImage
from majesty_cam.native_impact import require_exact_profile, AUDITED_IMAGES


class NativeImpactProfiles(unittest.TestCase):
    def test_all_production_profiles(self):
        evidence = json.loads((Path(__file__).parent / 'fixtures' /
                               'native-impact-guards.json').read_text())
        returns = json.loads((Path(__file__).parent / 'fixtures' /
                              'boolean-return-guards.json').read_text())
        self.assertEqual({p['name'] for p in evidence['profiles']}, {'Public', 'Beta2', 'Gog'})
        self.assertEqual(AUDITED_IMAGES, {p['sha256'] for p in evidence['profiles']})
        variables = {'Public': 'MAJESTY_PUBLIC_EXE', 'Beta2': 'MAJESTY_BETA2_EXE',
                     'Gog': 'MAJESTY_GOG_EXE'}
        for profile in evidence['profiles']:
            with self.subTest(profile=profile['name']):
                variable = variables[profile['name']]
                self.assertIn(variable, os.environ, 'All three exact fixtures are required')
                image = PeImage(os.environ[variable])
                require_exact_profile(Path(os.environ[variable]))
                # require_exact_profile checks build identity and consumed bodies;
                # the full-image hash above records original evidence provenance.
                self.assertEqual(image.base, 0x400000)
                def read(va, size):
                    return image.read(va - image.base, size)
                for window in profile['windows']:
                    self.assertEqual(hashlib.sha256(read(window['va'], window['size'])).hexdigest(),
                                     window['sha256'], window['name'])
                    for call in window['calls']:
                        self.assertEqual(image.target(call['site'] - image.base) + image.base,
                                         call['target'], window['name'])
                result_profile = next(p for p in returns['profiles'] if p['name'] == profile['name'])
                self.assertEqual(result_profile['executableSHA256'], profile['sha256'])
                for window in result_profile['windows']:
                    self.assertEqual(hashlib.sha256(read(window['va'], window['size'])).hexdigest(),
                                     window['sha256'], window['name'])
                # Check the compiled adapter's own profile rows, not just a
                # detached evidence file. No skipped/missing branch fixtures.
                index = {'Public': 0, 'Beta2': 1, 'Gog': 2}[profile['name']]
                for filename in ('BooleanRuntimeProfiles.h', 'NativeImpactProfiles.h'):
                    header = (Path(__file__).parents[1] / 'runtime' / filename).read_text()
                    block = re.search(r'bodies'+str(index)+r'\[\]=\{(.*?)\n    \};', header, re.S).group(1)
                    rows = re.findall(r'\{(0x[0-9a-f]+),(\d+),\{([^}]+)\}\}', block)
                    self.assertTrue(rows, filename)
                    for address, size, digest in rows:
                        expected = bytes(int(x,16) for x in digest.split(','))
                        self.assertEqual(hashlib.sha256(read(int(address,16),int(size))).digest(), expected, filename)
                sites = {w['name']: w for w in profile['windows']}
                install = read(sites['InstallImpact']['va'], 10)
                self.assertEqual(install[0], 0x68)
                self.assertEqual(struct.unpack_from('<I', install, 1)[0], sites['InstalledImpact']['va'])
                self.assertEqual(image.target(sites['InstallImpact']['va'] + 5 - image.base)
                                 + image.base, sites['ImpactSetter']['va'])
                terminal = read(sites['Terminal100A']['va'] + 0x54, 6)
                self.assertEqual(terminal[:2], b'\xff\x15')
                self.assertEqual(struct.unpack_from('<I', terminal, 2)[0], profile['impact_global'])
                table = profile['final_callback_table']
                self.assertEqual(hashlib.sha256(read(table['va'], table['size'])).hexdigest(), table['sha256'])
                boolean = profile['boolean']
                self.assertEqual(boolean['type'], 6)
                slot = read(boolean['vtable'] + 0x64, 4)
                self.assertEqual(struct.unpack('<I', slot)[0], boolean['getter'])
                self.assertEqual(hashlib.sha256(slot).hexdigest(), boolean['slotSHA256'])
                # Native bool returns AL only. An integer-result helper is not interchangeable.
                self.assertEqual(sites['EvaluatorExecute']['size'],
                                 261 if profile['name'] == 'Public' else 260)


if __name__ == '__main__':
    unittest.main()
