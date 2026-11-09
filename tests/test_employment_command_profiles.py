"""Exact-image parity evidence for the two researched paired-call sites."""
import hashlib
import os
import json
import re
from pathlib import Path
import unittest
from test_occupant_runtime_profiles import PeImage

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT.parent/'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
IMAGES = {
    'Public': Path(os.environ.get('MAJESTY_PUBLIC_EXE','C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/MajestyHD.exe')),
    'Beta2': Path(os.environ.get('MAJESTY_BETA2_EXE',str(FIXTURES/'beta2/MajestyHD.exe'))),
    'Gog': Path(os.environ.get('MAJESTY_GOG_EXE',str(FIXTURES/'gog-pristine/MajestyHD.exe'))),
}


class EmploymentCommandProfileTests(unittest.TestCase):
    def test_allunits_class_uses_same_guarded_lookup(self):
        # Verified primary tables from handle-service-correction-20261006.
        for name, table, ge in [('Public', 0x73A4FC, 0x748D4C),
                               ('Beta2', 0x7535BC, 0x762E1C),
                               ('Gog', 0x752604, 0x761CDC)]:
            image = PeImage(IMAGES[name])
            self.assertEqual(image.read(table-image.base+0x28,4),
                             image.read(ge-image.base+0x28,4))

    def test_missing_handle_lookup_guard_covers_all_three_stock_services(self):
        header = (ROOT/'runtime/PairedOccupantLookupProfiles.h').read_text()
        actual = [(int(a,16), int(b), int(c,16)) for a,b,c in
                  re.findall(r'\{0x([0-9A-F]+)u, (\d+)u, 0x([0-9A-F]+)u\}', header)]
        evidence = json.loads((ROOT/'tests/fixtures/employment-lookup-profiles.json').read_text())
        bindings = [(int(a,16), int(b,16)) for a,b in
                    re.findall(r'\{0x([0-9A-F]+)u, 0x([0-9A-F]+)u\}', header)]
        self.assertEqual(bindings, [(p['categoryGetter']-0x400000, p['serviceVtable']-0x400000)
                                    for p in evidence['profiles']])
        expected = []
        self.assertEqual({p['name'] for p in evidence['profiles']}, set(IMAGES))
        for p in evidence['profiles']:
            image = PeImage(IMAGES[p['name']])
            self.assertEqual(hashlib.sha256(image.data).hexdigest(), p['executableSHA256'])
            for w in (*p['windows'], *p['metadata']):
                data = image.read(w['va']-image.base, w['size'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), w['sha256'])
                h = 2166136261
                for byte in data:
                    h = ((h ^ byte) * 16777619) & 0xffffffff
                expected.append((w['va']-image.base, w['size'], h))
        self.assertEqual(actual, expected)

    def test_installer_windows_match_exact_image_evidence(self):
        header = (ROOT/'runtime/PairedOccupantProfiles.h').read_text()
        encoded = re.findall(r'\{0x([0-9A-F]+)u, (\d+)u, 0x([0-9A-F]+)u\}', header)
        evidence = json.loads((ROOT/'tests/fixtures/employment-command-profiles.json').read_text())
        bindings = [tuple(int(v,16) for v in row) for row in
                    re.findall(r'\{0x([0-9A-F]+)u, 0x([0-9A-F]+)u, 0x([0-9A-F]+)u, 0x([0-9A-F]+)u\}', header)]
        self.assertEqual(bindings, [tuple(v-0x400000 for v in
                         (p['sites']['addSubject'], p['sites']['execute'], p['stock']['addAgent'], p['stock']['execute']))
                         for p in evidence['profiles']])
        expected = []
        for profile in evidence['profiles']:
            image = PeImage(IMAGES[profile['name']])
            self.assertEqual(hashlib.sha256(image.data).hexdigest(), profile['executableSHA256'])
            for w in [profile['commandTable'], *profile['windows']]:
                data = image.read(w['va']-image.base, w['size'])
                self.assertEqual(hashlib.sha256(data).hexdigest(), w['sha256'])
                h = 2166136261
                for byte in data:
                    h = ((h ^ byte) * 16777619) & 0xffffffff
                expected.append((w['va']-image.base, w['size'], h))
        self.assertEqual([(int(a,16), int(b), int(c,16)) for a,b,c in encoded], expected)

    def test_all_three_exact_images_and_call_abis(self):
        evidence = json.loads((ROOT/'tests/fixtures/employment-command-profiles.json').read_text())
        self.assertEqual({p['name'] for p in evidence['profiles']}, set(IMAGES))
        for profile in evidence['profiles']:
            with self.subTest(profile=profile['name']):
                image = PeImage(IMAGES[profile['name']])
                self.assertEqual(hashlib.sha256(image.data).hexdigest(), profile['executableSHA256'])
                self.assertEqual(image.base, evidence['imageBase'])
                for window in [profile['commandTable'], *profile['windows']]:
                    actual = image.read(window['va']-image.base, window['size'])
                    self.assertEqual(hashlib.sha256(actual).hexdigest(), window['sha256'])
                for site, target in [('addSubject','addAgent'), ('execute','execute'), ('destroy','destroy')]:
                    self.assertEqual(image.target(profile['sites'][site]-image.base),
                                     profile['stock'][target]-image.base)
                self.assertEqual(image.read(profile['sites']['addSubject']-image.base-5,5),
                                 bytes.fromhex('53 8d 4c 24 74'))
                self.assertEqual(image.read(profile['sites']['execute']-image.base-4,4),
                                 bytes.fromhex('8d 4c 24 70'))


if __name__ == '__main__':
    unittest.main()
