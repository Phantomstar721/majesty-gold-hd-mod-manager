"""Explicit opt-in isolation for the panel-engine alpha application."""
import os

ENVIRONMENT = "MAJESTY_MANAGER_EDITION"
ALPHA = "panel-engine-alpha"


def panel_alpha():
    return os.environ.get(ENVIRONMENT) == ALPHA


def state_folder():
    return "MajestyModManagerPanelEngineAlpha" if panel_alpha() else "MajestyModManager"


def output_directory_name():
    return "Majesty Mod Manager - Panel Engine Alpha" if panel_alpha() else "Majesty Mod Manager - Merged"


def alpha_launch_blocker():
    # Native readiness is checked per selected executable/module at launch;
    # optional patches are never installed merely by selecting a mod.
    return None
