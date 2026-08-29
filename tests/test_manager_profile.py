from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.profile import (
    ManagerProfile,
    initial_selection,
    load_profile,
    normalize_guid,
    read_remembered_mods,
    save_profile,
    write_remembered_mods,
)


ONE = "320E5EC3-C033-4131-9859-4F37DC377BDF"
TWO = "A80596DA-60D7-5DF1-9D01-4D69F40D5D95"


class ManagerProfileTests(unittest.TestCase):
    def test_remembered_mods_round_trip_in_canonical_crlf_format(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "MajestyHD" / "MajestyModPersistence.txt"
            result = write_remembered_mods(path, ("{" + ONE.lower() + "}", ONE, TWO))

            self.assertEqual(result, (ONE, TWO))
            self.assertEqual(path.read_bytes(), (ONE + "\r\n" + TWO + "\r\n").encode("ascii"))
            self.assertEqual(read_remembered_mods(path), (ONE, TWO))

    def test_bad_rows_and_duplicates_do_not_poison_remembered_import(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "preset.txt"
            path.write_text(f"bad\n{ONE}\n{ONE.lower()}\n", encoding="ascii")
            self.assertEqual(read_remembered_mods(path), (ONE,))

    def test_first_run_imports_existing_qol_choices(self):
        selected, order, source = initial_selection(
            (ONE, TWO), saved_profile=None, remembered_ids=(TWO,)
        )
        self.assertEqual(selected, {ONE: False, TWO: True})
        self.assertEqual(order, (TWO, ONE))
        self.assertEqual(source, "remembered")

    def test_without_prior_state_every_detected_mod_defaults_on(self):
        selected, order, source = initial_selection(
            (ONE, TWO), saved_profile=None, remembered_ids=()
        )
        self.assertEqual(selected, {ONE: True, TWO: True})
        self.assertEqual(order, (ONE, TWO))
        self.assertEqual(source, "defaults")

    def test_manager_state_wins_and_new_mods_default_on(self):
        profile = ManagerProfile(selections={ONE: False}, order=(ONE,))
        selected, order, source = initial_selection(
            (ONE, TWO), saved_profile=profile, remembered_ids=(ONE,)
        )
        self.assertEqual(selected, {ONE: False, TWO: True})
        self.assertEqual(order, (ONE, TWO))
        self.assertEqual(source, "manager")

    def test_manager_profile_round_trip_keeps_build_gate(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            profile = ManagerProfile(selections={ONE: True}, order=(ONE,)).with_successful_build(
                fingerprint="abc123", mod_id=TWO, path=Path(tmp) / "Merged"
            )
            save_profile(path, profile)
            loaded = load_profile(path)

            self.assertEqual(loaded.selections, {ONE: True})
            self.assertEqual(loaded.order, (ONE,))
            self.assertEqual(loaded.last_build_fingerprint, "abc123")
            self.assertEqual(loaded.last_build_mod_id, TWO)
            self.assertEqual(normalize_guid("{" + ONE.lower() + "}"), ONE)


if __name__ == "__main__":
    unittest.main()
