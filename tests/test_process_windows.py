from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam._subprocess import no_console_window_options
from majesty_cam.compose import compile_gpl
from majesty_cam.gpl import GplProjectSourceSet
from majesty_cam.intent_text import (
    INTENT_REGISTRY_ENV_VAR,
    encode_intent_registry,
)
from majesty_cam.manager.launch import launch_majesty
from majesty_cam.manager.profile_lock import (
    PROFILE_LOCK_HANDLE_ENV_VAR,
    acquire_merged_profile_lock,
)
from majesty_cam.runtime_capabilities import (
    RUNTIME_CAPABILITY_MANIFEST_ENV_VAR,
    encode_runtime_capability_manifest,
)
from majesty_cam.runtime_features import (
    RUNTIME_FEATURE_REGISTRY_ENV_VAR,
    encode_runtime_feature_registry,
)
from majesty_cam.stock_controller_registry import (
    CONTROLLER_REGISTRY_ENVIRONMENT,
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
)
from majesty_cam.manager.paths import ManagerPaths


MOD_ID = "48CDD934-B338-4373-A4A4-A99A8E7F917F"


class WindowsProcessOptionsTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows process flags")
    def test_headless_options_suppress_console_and_window_show_state(self):
        options = no_console_window_options()

        self.assertEqual(options["creationflags"], subprocess.CREATE_NO_WINDOW)
        startupinfo = options["startupinfo"]
        self.assertTrue(startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(startupinfo.wShowWindow, subprocess.SW_HIDE)

    @unittest.skipUnless(os.name == "nt", "Windows process flags")
    def test_gui_child_keeps_its_window_while_suppressing_only_a_console(self):
        options = no_console_window_options(force_hidden=False)

        self.assertEqual(options, {"creationflags": subprocess.CREATE_NO_WINDOW})

    @unittest.skipIf(os.name == "nt", "Non-Windows subprocess behavior")
    def test_non_windows_callers_receive_no_windows_only_options(self):
        self.assertEqual(no_console_window_options(), {})


class ManagerProcessWiringTests(unittest.TestCase):
    def test_launch_fallback_uses_the_registry_driven_required_helper_service(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _manager_paths(root)
            for path in (
                paths.game_executable,
                paths.runtime_launcher,
                paths.runtime_dll,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            with patch(
                "majesty_cam.manager.launch.QolService"
            ) as service_type, patch(
                "majesty_cam.manager.launch.subprocess.Popen",
                return_value=SimpleNamespace(pid=4321),
            ):
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=True,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                )

            service_type.assert_called_once_with(
                repo_root=paths.repo_root,
                game_executable=paths.game_executable,
            )
            service_type.return_value.ensure_required.assert_called_once_with()

    def test_gpl_compiler_is_headless_without_changing_capture_contract(self):
        source_set = GplProjectSourceSet(
            project_text='source="Merged.gpl"\n',
            gpl_filename="Merged.gpl",
            gpl_text="Function Fixture()\nBegin\nEnd\n",
            dat_filename=None,
            dat_text="",
        )
        window_options = {"creationflags": 0x08000000, "startupinfo": object()}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            compiler = root / "Compiler.exe"
            compiler.write_bytes(b"fixture")
            output = root / "compiled"

            def run_compiler(command, **kwargs):
                (output / "Merged.bcd").write_bytes(b"compiled")
                return subprocess.CompletedProcess(command, 0, "compiler output", "")

            with patch(
                "majesty_cam.compose.no_console_window_options",
                return_value=window_options,
            ) as options, patch(
                "majesty_cam.compose.subprocess.run",
                side_effect=run_compiler,
            ) as run:
                result = compile_gpl(source_set, compiler, output)

        options.assert_called_once_with()
        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["encoding"], "cp1252")
        self.assertIs(kwargs["startupinfo"], window_options["startupinfo"])
        self.assertEqual(kwargs["creationflags"], window_options["creationflags"])
        self.assertEqual(result.stdout, "compiler output")

    def test_runtime_launcher_is_headless_but_game_command_is_unchanged(self):
        window_options = {"creationflags": 0x08000000, "startupinfo": object()}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _manager_paths(root)
            for path in (
                paths.game_executable,
                paths.runtime_launcher,
                paths.runtime_dll,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            with patch.dict(
                os.environ,
                {INTENT_REGISTRY_ENV_VAR: r"C:\stale\registry.bin"},
            ), patch(
                "majesty_cam.manager.launch.no_console_window_options",
                return_value=window_options,
            ) as options, patch(
                "majesty_cam.manager.launch.subprocess.Popen",
                return_value=SimpleNamespace(pid=4321),
            ) as popen:
                result = launch_majesty(
                    paths,
                    [MOD_ID],
                    game_arguments=("-debugout",),
                    ensure_qol=False,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                )

        options.assert_called_once_with()
        command = popen.call_args.args[0]
        self.assertEqual(
            command,
            [
                str(paths.runtime_launcher),
                str(paths.game_executable),
                str(paths.runtime_dll),
                "-debugout",
            ],
        )
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], paths.runtime_root)
        self.assertTrue(kwargs["close_fds"])
        self.assertNotIn(INTENT_REGISTRY_ENV_VAR, kwargs["env"])
        self.assertIn(RUNTIME_CAPABILITY_MANIFEST_ENV_VAR, kwargs["env"])
        self.assertIn(RUNTIME_FEATURE_REGISTRY_ENV_VAR, kwargs["env"])
        self.assertIn(CONTROLLER_REGISTRY_ENVIRONMENT, kwargs["env"])
        self.assertNotIn(PROFILE_LOCK_HANDLE_ENV_VAR, kwargs["env"])
        self.assertIs(kwargs["startupinfo"], window_options["startupinfo"])
        self.assertEqual(kwargs["creationflags"], window_options["creationflags"])
        self.assertEqual(result.launcher_pid, 4321)

    @unittest.skipUnless(os.name == "nt", "Windows inherited-handle launch wiring")
    def test_merge_launch_passes_only_the_profile_lock_handle_to_hidden_launcher(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _manager_paths(root)
            for path in (
                paths.game_executable,
                paths.runtime_launcher,
                paths.runtime_dll,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            startupinfo = SimpleNamespace(lpAttributeList=None)
            window_options = {
                "creationflags": subprocess.CREATE_NO_WINDOW,
                "startupinfo": startupinfo,
            }
            with patch(
                "majesty_cam.manager.launch.no_console_window_options",
                return_value=window_options,
            ), patch(
                "majesty_cam.manager.launch.subprocess.Popen",
                return_value=SimpleNamespace(pid=4321),
            ) as popen:
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                    merged_profile_root=paths.merged_output_root,
                )

            kwargs = popen.call_args.kwargs
            inherited = startupinfo.lpAttributeList["handle_list"]
            self.assertEqual(len(inherited), 1)
            self.assertEqual(
                kwargs["env"][PROFILE_LOCK_HANDLE_ENV_VAR],
                str(inherited[0]),
            )
            self.assertTrue(kwargs["close_fds"])
            # Mocking Popen means there is no child reference; the manager must
            # still release its own handle on the success path.
            reacquired = acquire_merged_profile_lock(paths.merged_output_root)
            reacquired.close()

    def test_runtime_launcher_receives_only_the_validated_selected_registry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _manager_paths(root)
            for path in (
                paths.game_executable,
                paths.runtime_launcher,
                paths.runtime_dll,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            registry = root / "prepared" / "Data" / "MMMIntentText.bin"
            registry.parent.mkdir(parents=True)
            registry.write_bytes(encode_intent_registry(()))

            with patch(
                "majesty_cam.manager.launch.subprocess.Popen",
                return_value=SimpleNamespace(pid=4321),
            ) as popen:
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    intent_registry=registry,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                )

            self.assertEqual(
                popen.call_args.kwargs["env"][INTENT_REGISTRY_ENV_VAR],
                str(registry.resolve()),
            )
            capability = _capability_manifest(root)
            self.assertEqual(
                popen.call_args.kwargs["env"][RUNTIME_CAPABILITY_MANIFEST_ENV_VAR],
                str(capability.resolve()),
            )
            registry.write_bytes(b"not a registry")
            with self.assertRaisesRegex(RuntimeError, "missing or invalid"):
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    intent_registry=registry,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                )
            capability.write_bytes(b"not an MMCP manifest")
            with self.assertRaisesRegex(RuntimeError, "capability manifest"):
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    intent_registry=None,
                    capability_manifest=capability,
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=_controller_registry(root),
                )
            feature = _feature_registry(root)
            feature.write_bytes(b"not an MMFR registry")
            with self.assertRaisesRegex(RuntimeError, "runtime feature registry"):
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    intent_registry=None,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=feature,
                    controller_registry=_controller_registry(root),
                )
            controller = _controller_registry(root)
            controller.write_bytes(b"not an MMCR registry")
            with self.assertRaisesRegex(RuntimeError, "controller registry"):
                launch_majesty(
                    paths,
                    [MOD_ID],
                    ensure_qol=False,
                    intent_registry=None,
                    capability_manifest=_capability_manifest(root),
                    runtime_feature_registry=_feature_registry(root),
                    controller_registry=controller,
                )

    def test_source_launcher_starts_powershell_hidden_and_keeps_gui_errors(self):
        batch = (REPO_ROOT / "Launch - Majesty Mod Manager.bat").read_text(
            encoding="utf-8"
        )
        script = (REPO_ROOT / "scripts" / "Launch-ModManager.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("-WindowStyle Hidden", batch)
        self.assertIn("-NonInteractive", batch)
        self.assertNotIn("pause", batch.casefold())
        self.assertIn("Start-Process -FilePath $pythonw", script)
        self.assertIn("-WindowStyle Hidden", script)
        self.assertNotIn("-Verb RunAs", script)
        self.assertIn("WScript.Shell", script)
        self.assertIn("Write-Error $detail", script)

        build_script = (
            REPO_ROOT / "scripts" / "Build-ModManagerExe.ps1"
        ).read_text(encoding="utf-8")
        self.assertNotIn("--uac-admin", build_script)


def _manager_paths(root: Path) -> ManagerPaths:
    game = root / "game"
    runtime = root / "runtime"
    return ManagerPaths(
        repo_root=root / "repo",
        game_path=game,
        local_mods_root=root / "Mods",
        local_quests_root=root / "Quests",
        workshop_roots=(),
        runtime_root=runtime,
        generic_visitor_installer=root / "Install-GenericVisitorLists.ps1",
        remember_mods_installer=root / "Install-ModPersistence.ps1",
        remembered_path=root / "state" / "MajestyModPersistence.txt",
        profile_path=root / "state" / "profile.json",
        merged_output_root=root / "Mods" / "Majesty Mod Manager - Merged",
    )


def _capability_manifest(root: Path) -> Path:
    path = root / "prepared" / "capabilities.mmcp"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_runtime_capability_manifest(()))
    return path


def _feature_registry(root: Path) -> Path:
    path = root / "prepared" / "features.mmfr"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_runtime_feature_registry(()))
    return path


def _controller_registry(root: Path) -> Path:
    path = root / "prepared" / "controllers.mmcr"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        encode_stock_controller_registry(resolve_stock_controller_registry((), {}))
    )
    return path


if __name__ == "__main__":
    unittest.main()
