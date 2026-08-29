from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.profile_lock import (
    ProfileLockBusyError,
    acquire_merged_profile_lock,
    merged_profile_lock_path,
)


@unittest.skipUnless(os.name == "nt", "Windows inherited-handle profile lock")
class ProfileLockTests(unittest.TestCase):
    def test_same_generated_target_cannot_be_locked_twice(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "Mods" / "Majesty Mod Manager - Merged"
            first = acquire_merged_profile_lock(target)
            try:
                with self.assertRaisesRegex(ProfileLockBusyError, "in use"):
                    acquire_merged_profile_lock(target)
            finally:
                first.close()

            second = acquire_merged_profile_lock(target)
            second.close()
            self.assertEqual(
                merged_profile_lock_path(target),
                target.parent / ".Majesty Mod Manager - Merged.lock",
            )
            self.assertTrue(merged_profile_lock_path(target).is_file())

    def test_explicitly_inherited_handle_holds_lock_after_parent_closes(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "Mods" / "Majesty Mod Manager - Merged"
            profile_lock = acquire_merged_profile_lock(target)
            profile_lock.set_inheritable(True)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.lpAttributeList = {
                "handle_list": [profile_lock.handle]
            }
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import time; time.sleep(0.4)",
                ],
                close_fds=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            profile_lock.close()
            try:
                with self.assertRaises(ProfileLockBusyError):
                    acquire_merged_profile_lock(target)
            finally:
                child.wait(timeout=5)

            reacquired = acquire_merged_profile_lock(target)
            reacquired.close()


if __name__ == "__main__":
    unittest.main()
