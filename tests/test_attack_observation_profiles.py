"""Actual preflight and capability parity; machine bodies checked separately."""
import os
from pathlib import Path
import unittest
from majesty_cam.attack_observation import require_exact_profile, CAPABILITY
from majesty_cam.checked_placement import CAPABILITY as PLACEMENT
from majesty_cam.manager.qol_service import detect_majesty_branch
from majesty_cam.manager.runtime_profiles import unsupported_runtime_capabilities

class AttackProfileTests(unittest.TestCase):
    def test_production_preflight_accepts_all_three_profiles(self):
        for env in ('MAJESTY_PUBLIC_EXE', 'MAJESTY_BETA2_EXE', 'MAJESTY_GOG_EXE'):
            self.assertTrue(os.environ.get(env), env + ' is required')
            path = Path(os.environ[env])
            with self.subTest(profile=env):
                require_exact_profile(path)
                branch = detect_majesty_branch(path)
                self.assertIsNotNone(branch)
                self.assertEqual(unsupported_runtime_capabilities(branch, (CAPABILITY, PLACEMENT)), ())
