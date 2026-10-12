"""Mandatory, read-only release profile checks; missing fixtures are errors."""
import io
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

MODULES = (
    "test_feature_parity_profiles", "test_map_query_runtime_profiles",
    "test_movement_query_profiles", "test_native_timing_profiles",
    "test_exploration_profiles", "test_occupant_runtime_profiles",
    "test_panel_lifecycle_profiles", "test_building_toggle_runtime_profiles",
    "test_quest_board_runtime_profiles", "test_release_scope",
    "test_timed_imag", "test_release_merge_literals",
)

def main():
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
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
