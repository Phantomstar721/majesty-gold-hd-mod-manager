from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Sequence

from .._subprocess import no_console_window_options
from ..intent_text import INTENT_REGISTRY_ENV_VAR, decode_intent_registry
from ..runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    RUNTIME_CAPABILITY_MANIFEST_ENV_VAR,
    decode_runtime_capability_manifest,
)
from ..runtime_features import (
    ENCHANTMENT_ROW_RUNTIME_CAPABILITY,
    NAME_GENERATOR_RUNTIME_CAPABILITY,
    RUNTIME_FEATURE_REGISTRY_ENV_VAR,
    decode_runtime_feature_registry,
    legacy_runtime_features,
)
from ..stock_controller_features import LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY
from ..stock_controller_registry import (
    CONTROLLER_REGISTRY_ENVIRONMENT,
    STOCK_CONTROLLER_RUNTIME_CAPABILITY,
    ControllerRegistryError,
    decode_stock_controller_registry,
)
from .paths import ManagerPaths
from .profile_lock import (
    ExclusiveProfileLock,
    PROFILE_LOCK_HANDLE_ENV_VAR,
    ProfileLockError,
    acquire_merged_profile_lock,
)
from .profile import normalize_guid, write_remembered_mods
from .qol import ensure_required_qol


CURRENT_PERSISTENCE_LIMIT = 26


class ManagerLaunchError(RuntimeError):
    """Raised when the guarded DLL launch cannot start safely."""


@dataclass(frozen=True)
class LaunchResult:
    launcher_pid: int
    active_mod_ids: tuple[str, ...]
    executable: Path
    runtime_dll: Path


def launch_majesty(
    paths: ManagerPaths,
    active_mod_ids: Sequence[str],
    *,
    game_arguments: Sequence[str] = (),
    ensure_qol: bool = True,
    intent_registry: Path | None = None,
    capability_manifest: Path,
    runtime_feature_registry: Path,
    controller_registry: Path,
    merged_profile_root: Path | None = None,
    acquired_profile_lock: ExclusiveProfileLock | None = None,
) -> LaunchResult:
    """Project the manager profile, then invoke the suspended DLL launcher.

    A Merge launch either acquires ``merged_profile_root`` here or consumes an
    already-held ``acquired_profile_lock`` from the controller.  Only that
    handle is made inheritable, and the hidden launcher owns it until Majesty
    exits.  Standard-only launches pass neither argument and do not lock the
    unused generated profile.
    """

    if merged_profile_root is not None and acquired_profile_lock is not None:
        raise ManagerLaunchError(
            "The generated Merge profile lock was supplied twice."
        )

    required = (
        paths.game_executable,
        paths.runtime_launcher,
        paths.runtime_dll,
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise ManagerLaunchError(
            "Required launch files are missing: " + ", ".join(str(path) for path in missing)
        )
    ordered: list[str] = []
    seen: set[str] = set()
    for value in active_mod_ids:
        mod_id = normalize_guid(value)
        if mod_id in seen:
            continue
        seen.add(mod_id)
        ordered.append(mod_id)
    if len(ordered) > CURRENT_PERSISTENCE_LIMIT:
        raise ManagerLaunchError(
            f"The current guarded persistence bridge can restore at most "
            f"{CURRENT_PERSISTENCE_LIMIT} active IDs; this profile has {len(ordered)}. "
            "The manager-owned arbitrary-length runtime restore hook is not yet bundled."
        )
    environment = os.environ.copy()
    environment.pop(INTENT_REGISTRY_ENV_VAR, None)
    environment.pop(RUNTIME_CAPABILITY_MANIFEST_ENV_VAR, None)
    environment.pop(RUNTIME_FEATURE_REGISTRY_ENV_VAR, None)
    environment.pop(CONTROLLER_REGISTRY_ENVIRONMENT, None)
    environment.pop(PROFILE_LOCK_HANDLE_ENV_VAR, None)
    try:
        capability_path = capability_manifest.resolve(strict=True)
        if not capability_path.is_file():
            raise OSError("capability manifest path is not a file")
        prepared_capabilities = decode_runtime_capability_manifest(
            capability_path.read_bytes()
        )
    except (OSError, ValueError) as exc:
        raise ManagerLaunchError(
            f"The prepared runtime capability manifest is missing or invalid: {exc}"
        ) from exc
    environment[RUNTIME_CAPABILITY_MANIFEST_ENV_VAR] = str(capability_path)
    try:
        feature_path = runtime_feature_registry.resolve(strict=True)
        if not feature_path.is_file():
            raise OSError("runtime feature registry path is not a file")
        prepared_features = decode_runtime_feature_registry(feature_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ManagerLaunchError(
            f"The prepared runtime feature registry is missing or invalid: {exc}"
        ) from exc
    environment[RUNTIME_FEATURE_REGISTRY_ENV_VAR] = str(feature_path)
    try:
        controller_path = controller_registry.resolve(strict=True)
        if not controller_path.is_file():
            raise OSError("controller registry path is not a file")
        prepared_controllers = decode_stock_controller_registry(
            controller_path.read_bytes()
        )
    except (OSError, ControllerRegistryError) as exc:
        raise ManagerLaunchError(
            f"The prepared controller registry is missing or invalid: {exc}"
        ) from exc
    environment[CONTROLLER_REGISTRY_ENVIRONMENT] = str(controller_path)
    controller_count = sum(
        len(section)
        for section in (
            prepared_controllers.panels,
            prepared_controllers.meters,
            prepared_controllers.research_rows,
            prepared_controllers.upgrade_gates,
            prepared_controllers.timed_rage_actions,
            prepared_controllers.rage_command_actions,
            prepared_controllers.sovereign_target_actions,
            prepared_controllers.reward_panels,
            prepared_controllers.occupant_action_panels,
            prepared_controllers.hostile_monster_flags,
            prepared_controllers.building_open_toggles,
            prepared_controllers.quest_boards,
        )
    )
    if legacy_runtime_features(prepared_capabilities) or (
        LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY in prepared_capabilities
    ):
        raise ManagerLaunchError(
            "The prepared runtime manifests contain legacy package aliases; "
            "rebuild the managed profile."
        )
    feature_agreement = (
        bool(prepared_features.name_generators)
        == (NAME_GENERATOR_RUNTIME_CAPABILITY in prepared_capabilities)
        and bool(prepared_features.enchantment_rows)
        == (ENCHANTMENT_ROW_RUNTIME_CAPABILITY in prepared_capabilities)
        and bool(controller_count)
        == (STOCK_CONTROLLER_RUNTIME_CAPABILITY in prepared_capabilities)
    )
    if not feature_agreement:
        raise ManagerLaunchError(
            "The prepared runtime capability, feature, and controller "
            "registries do not agree; rebuild the managed profile."
        )
    intent_records = ()
    if intent_registry is not None:
        try:
            registry_path = intent_registry.resolve(strict=True)
            if not registry_path.is_file():
                raise OSError("registry path is not a file")
            intent_records = decode_intent_registry(registry_path.read_bytes())
        except (OSError, ValueError) as exc:
            raise ManagerLaunchError(
                f"The prepared activity-text registry is missing or invalid: {exc}"
            ) from exc
        environment[INTENT_REGISTRY_ENV_VAR] = str(registry_path)
    if bool(intent_records) != (
        PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY in prepared_capabilities
    ):
        raise ManagerLaunchError(
            "The prepared activity-text registry and runtime capability "
            "manifest do not agree; rebuild the managed profile."
        )

    profile_lock = acquired_profile_lock
    try:
        if profile_lock is None and merged_profile_root is not None:
            profile_lock = acquire_merged_profile_lock(merged_profile_root)
    except ProfileLockError as exc:
        raise ManagerLaunchError(str(exc)) from exc

    try:
        if ensure_qol:
            try:
                ensure_required_qol(paths)
            except Exception as exc:
                raise ManagerLaunchError(str(exc)) from exc
        write_remembered_mods(paths.remembered_path, ordered)

        command = [
            str(paths.runtime_launcher),
            str(paths.game_executable),
            str(paths.runtime_dll),
            *game_arguments,
        ]
        process_options = no_console_window_options()
        if profile_lock is not None:
            if os.name != "nt":
                raise ManagerLaunchError(
                    "The generated Merge profile lock can only be inherited on Windows."
                )
            try:
                profile_lock.set_inheritable(True)
            except ProfileLockError as exc:
                raise ManagerLaunchError(str(exc)) from exc
            startupinfo = process_options.get("startupinfo")
            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
                process_options["startupinfo"] = startupinfo
            startupinfo.lpAttributeList = {"handle_list": [profile_lock.handle]}
            environment[PROFILE_LOCK_HANDLE_ENV_VAR] = str(profile_lock.handle)
        try:
            process = subprocess.Popen(
                command,
                cwd=paths.runtime_root,
                close_fds=True,
                env=environment,
                **process_options,
            )
        except OSError as exc:
            raise ManagerLaunchError(
                f"Could not start the Majesty runtime launcher: {exc}"
            ) from exc
    finally:
        # On success the launcher owns an inherited reference to the same file
        # object. On every failure this closes the only reference immediately.
        if profile_lock is not None:
            profile_lock.close()
    return LaunchResult(
        launcher_pid=process.pid,
        active_mod_ids=tuple(ordered),
        executable=paths.game_executable,
        runtime_dll=paths.runtime_dll,
    )


__all__ = [
    "CURRENT_PERSISTENCE_LIMIT",
    "LaunchResult",
    "ManagerLaunchError",
    "launch_majesty",
]
