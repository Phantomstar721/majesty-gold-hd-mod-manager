"""Separate alpha executable entry; never changes the normal Manager's edition."""
import os
os.environ["MAJESTY_MANAGER_EDITION"] = "panel-engine-alpha"
from majesty_cam.manager.app import main

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--check-qol-startup':
        from majesty_cam.manager.alpha_startup_check import run
        raise SystemExit(run(sys.argv[2]))
    raise SystemExit(main())
