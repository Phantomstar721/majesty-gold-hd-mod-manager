"""PyInstaller entry point for the windowed Majesty Mod Manager."""

from majesty_cam.manager.app import main


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--check-qol-startup':
        from majesty_cam.manager.alpha_startup_check import run
        raise SystemExit(run(sys.argv[2]))
    raise SystemExit(main())
