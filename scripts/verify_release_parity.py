"""Mandatory, read-only release profile checks; missing fixtures are errors."""
import io
import os
from pathlib import Path
import sys
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

MODULES = (
    "test_sound_review",
    "test_feature_parity_profiles", "test_map_query_runtime_profiles",
    "test_movement_query_profiles", "test_native_timing_profiles",
    "test_exploration_profiles", "test_occupant_runtime_profiles",
    "test_panel_lifecycle_profiles", "test_building_toggle_runtime_profiles",
    "test_quest_board_runtime_profiles", "test_release_scope",
    "test_timed_imag", "test_release_merge_literals",
    "test_description_review",
    "test_sparse_art_ids",
    "test_damage_contributions", "test_native_impact",
    "test_native_impact_profiles", "test_observation_native_profiles",
    "test_impact_compatible_image", "test_standard_project_recovery", "test_event_review",
)

def main():
    os.environ['MAJESTY_REQUIRE_DAMAGE_FIXTURES'] = '1'
    for name in ("PUBLIC", "BETA2", "GOG"):
        key = "MAJESTY_" + name + "_EXE"
        path = os.environ.get(key)
        if not path or not Path(path).is_file():
            raise SystemExit("Release blocked: set " + key + " to its verified executable fixture")
        os.environ["MAJESTY_EXPLORATION_" + name + "_EXE"] = path
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
    if not result.wasSuccessful() or result.skipped:
        sys.stderr.write(output.getvalue())
        for test, reason in result.skipped:
            sys.stderr.write("Release blocked by skipped check: {}: {}\n".format(test, reason))
        return 1
    stock_root = os.environ.get("MAJESTY_STOCK_ROOT")
    if not stock_root:
        raise SystemExit("Release blocked: MAJESTY_STOCK_ROOT is required for the shipped-art audit")
    audit = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_shipped_art.py'),
                            '--game', stock_root, '--report',
                            str(ROOT / 'local/shipped-art-regression.json')],
                           capture_output=True, text=True)
    if audit.returncode:
        sys.stderr.write(audit.stderr)
        return 1
    packages = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_release_packages.py'),
        '--game', stock_root, '--report', str(ROOT / 'local/release-package-regression.json')],
        capture_output=True, text=True)
    if packages.returncode:
        sys.stderr.write(packages.stderr)
        return 1
    mix = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_reported_standard_mix.py'), stock_root],
                         capture_output=True, text=True)
    if mix.returncode:
        sys.stderr.write(mix.stdout + mix.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
