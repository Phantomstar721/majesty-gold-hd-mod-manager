"""Offline three-profile evidence, not live acceptance or a runtime feature."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from inspect_reward_flag_lifecycle import audit, inspect, PROFILES


class RewardFlagLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = audit()

    def test_requires_exact_executable(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported executable'):
            inspect(PROFILES[0][1], '0' * 64)

    def test_completion_removes_without_reward_ownership_test(self):
        # Complete body: event2 -> unit virtual74; no owner/value query.
        expected = '837c241402750b8b4c24088b018b5074ffd233c0c3'
        for name, profile in self.profiles.items():
            with self.subTest(profile=name):
                self.assertEqual(profile['methods']['completion_1005']['bytes'], expected)

    def test_secondary_draw_does_not_consume_fade_word(self):
        for name, profile in self.profiles.items():
            with self.subTest(profile=name):
                listing = '\n'.join(profile['methods']['secondary_draw_ac']['listing'])
                self.assertNotIn('[esi + 0x24]', listing)
                self.assertIn('cmp dword ptr [esi + 0x6c], 4', listing)
                self.assertIn('push 0x80ffffff', listing)

    def test_callback_guard_precedes_callback_and_flag_passes_self(self):
        for profile in self.profiles.values():
            listing = profile['methods']['death_callback_13c']['listing']
            text = '\n'.join(listing)
            self.assertIn('test eax, 0x800', text)
            self.assertIn('or eax, 0x800', text)
            self.assertIn('cmp dword ptr [esi + 0x6c], 4', text)
            self.assertLess(text.index('or eax, 0x800'), text.index('call '))


if __name__ == '__main__':
    unittest.main()
