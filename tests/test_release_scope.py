"""The production release must not absorb unfinished development features."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseScopeTests(unittest.TestCase):
    def test_shared_bridge_has_no_build_specific_research_or_movement_rejection(self):
        text = (ROOT / "runtime/MapQueryRuntime.cpp").read_text()
        for flag in ("researchOrder", "movementDistance"):
            self.assertNotRegex(text, r"if\s*\([^\n]*" + flag + r"[^\n]*buildId")
        self.assertIn("ValidateMovementQuery()", text)
        self.assertIn("ValidateNativeTiming()", text)

    def test_development_features_are_not_in_production_sources(self):
        for path in ("runtime/AttackObservationRuntime.cpp", "runtime/CheckedPlacementRuntime.cpp",
                     "runtime/EffectSequence.cpp", "src/majesty_cam/paired_accuracy.py",
                     "runtime/PaidSourceTargetRuntime.inl", "runtime/SavedAttributeRuntime.inl"):
            self.assertFalse((ROOT / path).exists(), "Development source entered release: " + path)
        from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES
        self.assertNotIn("manager.attack-projectile-observation.v1", DERIVED_RUNTIME_CAPABILITIES)
        self.assertNotIn("manager.checked-placement.v1", DERIVED_RUNTIME_CAPABILITIES)

    def test_unknown_builds_still_fail_runtime_profile_selection(self):
        text = (ROOT / "runtime/MapQueryRuntime.cpp").read_text()
        body = text.split("bool InstallMapQueryRuntime", 1)[1]
        for name in ("SteamPublic", "SteamBeta2", "Gog"):
            self.assertIn("case MajestyBuildId::" + name, body)
        self.assertIn("default: return false", body)
