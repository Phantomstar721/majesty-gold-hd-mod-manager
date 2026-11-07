"""Global expansion-content preference for Manager launches."""

from .profile import _atomic_write

ENVIRONMENT = "MAJESTY_MANAGER_EXPANSION_QUESTS"


def enabled(paths):
    return (paths.profile_path.parent / "expansion-quests.enabled").is_file()


def set_enabled(paths, checked):
    marker = paths.profile_path.parent / "expansion-quests.enabled"
    if checked:
        marker.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(marker, b"1\n")
    else:
        marker.unlink(missing_ok=True)


def configure_launch(paths, environment):
    if enabled(paths):
        environment[ENVIRONMENT] = "1"
    else:
        environment.pop(ENVIRONMENT, None)
