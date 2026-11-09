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

    def test_full_generic_runtime_is_in_production_sources(self):
        for path in ("runtime/AttackObservationRuntime.cpp", "runtime/CheckedPlacementRuntime.cpp",
                     "runtime/EffectSequence.cpp", "src/majesty_cam/paired_accuracy.py",
                     "runtime/SavedAttributeRuntime.inl"):
            self.assertTrue((ROOT / path).is_file(), "Missing supported source: " + path)
        from majesty_cam.manager.capabilities import DERIVED_RUNTIME_CAPABILITIES
        for feature in ("manager.projectile-interception.v1", "manager.checked-placement.v1"):
            self.assertIn(feature, DERIVED_RUNTIME_CAPABILITIES)
        script = (ROOT / 'scripts/Build-Runtime.ps1').read_text()
        source_list = script.split('$runtimeSources = @(', 1)[1].split('$runtimeLibraries', 1)[0]
        self.assertIn('"AttackObservationRuntime.cpp"', source_list)
        self.assertIn('"CheckedPlacementRuntime.cpp"', source_list)
        self.assertNotIn('"NativeImpactRuntime.cpp"', source_list)
        wrapper = (ROOT / 'scripts/Build-ModManagerExe.ps1').read_text()
        for flag in ('-AttackDiagnostic', '-EmploymentDiagnostic', '-SiegeCrashDiagnostic', '-PlacementDiagnostic'):
            self.assertNotIn(flag, wrapper)

    def test_unknown_builds_still_fail_runtime_profile_selection(self):
        text = (ROOT / "runtime/MapQueryRuntime.cpp").read_text()
        body = text.split("bool InstallMapQueryRuntime", 1)[1]
        for name in ("SteamPublic", "SteamBeta2", "Gog"):
            self.assertIn("case MajestyBuildId::" + name, body)
        self.assertIn("default: return false", body)
