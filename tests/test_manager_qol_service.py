from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.qol_service import (
    BETA2_BRANCH,
    PUBLIC_BRANCH,
    QOL_PATCHES,
    QolPatchSpec,
    QolService,
    QolServiceError,
    QolUtilityState,
    detect_majesty_branch,
    resolve_qol_patch,
)


class QolCatalogTests(unittest.TestCase):
    def test_catalog_matches_the_ten_independently_reversible_bundle_utilities(self):
        self.assertEqual(
            [item.key for item in QOL_PATCHES],
            [
                "skip-intro",
                "quests-shortcut",
                "map-drag",
                "unlock-quests",
                "suppress-flags",
                "remember-mods",
                "remember-speed",
                "remember-zoom",
                "generic-visitors",
                "lower-tracking",
            ],
        )
        self.assertTrue(all(item.license_identifier == "MIT" for item in QOL_PATCHES))
        self.assertEqual(
            {item.key for item in QOL_PATCHES if item.required_by_manager},
            {"remember-mods", "generic-visitors"},
        )
        self.assertNotIn("speedrun-timer", {item.key for item in QOL_PATCHES})
        self.assertNotIn("remove-earthquake", {item.key for item in QOL_PATCHES})

    def test_complete_payload_wins_and_partial_payload_does_not_mix_revisions(self):
        spec = _test_spec()
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            merger = workspace / "merger"
            payload = merger / "payload" / "qol" / spec.payload_slug
            standalone = workspace / spec.repository
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / "LICENSE.txt").write_text("MIT License", encoding="utf-8")
            scripts = standalone / "scripts"
            scripts.mkdir(parents=True)
            (scripts / spec.install_script_name).write_text("", encoding="utf-8")
            (scripts / spec.remove_script_name).write_text("", encoding="utf-8")
            (standalone / "LICENSE").write_text("MIT License", encoding="utf-8")

            complete = resolve_qol_patch(merger, spec)
            self.assertEqual(complete.source_kind, "standalone-repository")
            self.assertTrue(complete.apply_available)
            self.assertTrue(complete.remove_available)
            self.assertTrue(complete.license_available)

            suite = (
                merger
                / "payload"
                / "qol"
                / "utilities"
                / spec.bundle_directory
                / "scripts"
            )
            suite.mkdir(parents=True)
            (suite / spec.install_script_name).write_text("", encoding="utf-8")
            (suite / spec.remove_script_name).write_text("", encoding="utf-8")
            (suite.parent / "LICENSE").write_text("MIT License", encoding="utf-8")
            bundled = resolve_qol_patch(merger, spec)
            self.assertEqual(bundled.source_kind, "manager-payload-qol-suite")
            self.assertEqual(bundled.install_script.parent, suite)
            self.assertEqual(bundled.remove_script.parent, suite)


class MajestyBranchDetectionTests(unittest.TestCase):
    def test_public_and_beta2_evidence_survives_appended_qol_sections(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for branch in (PUBLIC_BRANCH, BETA2_BRANCH):
                path = root / f"{branch.key}-MajestyHD.exe"
                _write_synthetic_exe(path, branch, appended_section=True)
                self.assertEqual(detect_majesty_branch(path), branch)

    def test_unknown_timestamp_or_changed_stock_section_is_unsupported(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            unknown = root / "unknown.exe"
            _write_synthetic_exe(unknown, PUBLIC_BRANCH, timestamp=0x12345678)
            self.assertIsNone(detect_majesty_branch(unknown))

            changed = root / "changed.exe"
            _write_synthetic_exe(changed, PUBLIC_BRANCH, alter_first_section=True)
            self.assertIsNone(detect_majesty_branch(changed))


class QolServiceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows process flags")
    def test_default_powershell_runner_hides_its_console_window(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = QolService(
                repo_root=root,
                game_executable=root / "MajestyHD.exe",
                specs=(),
            )
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            with patch(
                "majesty_cam.manager.qol_service.subprocess.run",
                return_value=completed,
            ) as run:
                self.assertEqual(service._run_command(["powershell.exe"]), completed)

            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
            self.assertTrue(
                kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
            )
            self.assertEqual(kwargs["startupinfo"].wShowWindow, subprocess.SW_HIDE)

    def test_apply_and_remove_are_idempotent_and_use_one_canonical_script_pair(self):
        spec = _test_spec()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            game = root / "game"
            game.mkdir()
            executable = game / "MajestyHD.exe"
            _write_synthetic_exe(executable, PUBLIC_BRANCH)
            payload = merger / "payload" / "qol" / spec.payload_slug
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / spec.remove_script_name).write_text("", encoding="utf-8")
            (payload / "LICENSE.txt").write_text("MIT License", encoding="utf-8")
            runner = _StatefulRunner(spec)
            service = QolService(
                repo_root=merger,
                game_executable=executable,
                prefs_path=root / "MajXPrefs",
                specs=(spec,),
                runner=runner,
            )

            before = service.inspect().get(spec.key)
            self.assertEqual(before.state, QolUtilityState.AVAILABLE)
            self.assertTrue(before.supported)
            self.assertTrue(before.applicable)
            self.assertFalse(before.installed)
            self.assertEqual(before.name, spec.name)
            self.assertEqual(before.description, spec.description)
            self.assertFalse(before.required_for_manager)
            self.assertTrue(before.can_install)
            self.assertFalse(before.can_remove)
            self.assertEqual(before.status, "available")

            installed = service.apply(spec.key)
            self.assertEqual(installed.state, QolUtilityState.INSTALLED)
            self.assertFalse(installed.can_install)
            self.assertTrue(installed.can_remove)
            self.assertEqual(installed.status, "installed")
            service.apply(spec.key)
            removed = service.remove(spec.key)
            self.assertEqual(removed.state, QolUtilityState.AVAILABLE)
            service.remove(spec.key)

            mutations = [command for command in runner.commands if "-DryRun" not in command]
            self.assertEqual(len(mutations), 2)
            self.assertEqual(Path(mutations[0][5]), payload / spec.install_script_name)
            self.assertEqual(Path(mutations[1][5]), payload / spec.remove_script_name)
            self.assertTrue(all("-GamePath" in command for command in runner.commands))
            self.assertTrue(
                all(str(payload) in command[5] for command in runner.commands)
            )

    def test_cached_status_skips_duplicate_pre_action_dry_run(self):
        spec = _test_spec()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            executable = root / "game" / "MajestyHD.exe"
            executable.parent.mkdir()
            _write_synthetic_exe(executable, PUBLIC_BRANCH)
            payload = merger / "payload" / "qol" / spec.payload_slug
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / spec.remove_script_name).write_text("", encoding="utf-8")
            runner = _StatefulRunner(spec)
            service = QolService(
                repo_root=merger,
                game_executable=executable,
                specs=(spec,),
                runner=runner,
            )

            cached = service.inspect_patch(spec.key)
            runner.commands.clear()
            installed = service.apply(spec.key, current=cached)

            self.assertTrue(installed.installed)
            self.assertEqual(installed.state, QolUtilityState.INSTALLED)
            self.assertEqual(len(runner.commands), 1)
            self.assertNotIn("-DryRun", runner.commands[0])

    def test_protected_game_mutation_elevates_only_the_exact_action(self):
        spec = _test_spec()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            executable = root / "game" / "MajestyHD.exe"
            executable.parent.mkdir()
            _write_synthetic_exe(executable, PUBLIC_BRANCH)
            payload = merger / "payload" / "qol" / spec.payload_slug
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / spec.remove_script_name).write_text("", encoding="utf-8")
            normal = _StatefulRunner(spec)
            elevated = _StatefulRunner(spec)
            service = QolService(
                repo_root=merger,
                game_executable=executable,
                specs=(spec,),
                runner=normal,
                elevated_runner=elevated,
                elevation_probe=lambda _path: True,
            )

            current = service.inspect_patch(spec.key)
            service.apply(spec.key, current=current)

            self.assertEqual(len(normal.commands), 1)
            self.assertIn("-DryRun", normal.commands[0])
            self.assertEqual(len(elevated.commands), 1)
            self.assertNotIn("-DryRun", elevated.commands[0])
            self.assertIn("-GamePath", elevated.commands[0])

    def test_profile_preference_mutation_never_elevates(self):
        spec = QolPatchSpec(
            key="skip",
            name="Skip Intro",
            description="test",
            repository="skip-repo",
            bundle_directory="Skip",
            payload_slug="skip",
            install_script_name="Install.ps1",
            remove_script_name="Remove.ps1",
            preference_only=True,
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            payload = merger / "payload" / "qol" / "skip"
            payload.mkdir(parents=True)
            (payload / "Install.ps1").write_text("", encoding="utf-8")
            (payload / "Remove.ps1").write_text("", encoding="utf-8")
            prefs = root / "MajXPrefs"
            normal_commands = []

            def normal(command):
                normal_commands.append(list(command))
                return subprocess.CompletedProcess(command, 0, "installed", "")

            def must_not_elevate(_command):
                raise AssertionError("a per-user preference requested elevation")

            service = QolService(
                repo_root=merger,
                game_executable=root / "missing" / "MajestyHD.exe",
                prefs_path=prefs,
                specs=(spec,),
                runner=normal,
                elevated_runner=must_not_elevate,
                elevation_probe=lambda _path: True,
            )

            service.apply("skip")

            self.assertEqual(len(normal_commands), 1)
            self.assertIn("-PrefsPath", normal_commands[0])

    def test_executable_patch_is_not_run_for_an_unsupported_branch(self):
        spec = _test_spec()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            executable = root / "game" / "MajestyHD.exe"
            executable.parent.mkdir()
            _write_synthetic_exe(executable, PUBLIC_BRANCH, timestamp=0x12345678)
            payload = merger / "payload" / "qol" / spec.payload_slug
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / spec.remove_script_name).write_text("", encoding="utf-8")

            def should_not_run(_command):
                raise AssertionError("unsupported executable invoked a patch script")

            service = QolService(
                repo_root=merger,
                game_executable=executable,
                specs=(spec,),
                runner=should_not_run,
            )
            status = service.inspect().get(spec.key)

            self.assertEqual(status.state, QolUtilityState.UNSUPPORTED)
            self.assertFalse(status.supported)
            self.assertFalse(status.applicable)
            self.assertIsNone(status.installed)

    def test_manager_required_patch_cannot_be_removed(self):
        spec = replace(_test_spec(), required_by_manager=True)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            executable = root / "game" / "MajestyHD.exe"
            executable.parent.mkdir()
            _write_synthetic_exe(executable, PUBLIC_BRANCH)
            payload = merger / "payload" / "qol" / spec.payload_slug
            payload.mkdir(parents=True)
            (payload / spec.install_script_name).write_text("", encoding="utf-8")
            (payload / spec.remove_script_name).write_text("", encoding="utf-8")
            runner = _StatefulRunner(spec)
            runner.installed = True
            service = QolService(
                repo_root=merger,
                game_executable=executable,
                specs=(spec,),
                runner=runner,
            )

            status = service.inspect_patch(spec.key)
            self.assertTrue(status.required_for_manager)
            self.assertFalse(status.can_remove)
            with self.assertRaisesRegex(QolServiceError, "required"):
                service.remove(spec.key)
            self.assertFalse(
                any("-DryRun" not in command for command in runner.commands)
            )

    def test_skip_intro_is_branch_independent_and_reads_stock_preference(self):
        spec = QolPatchSpec(
            key="skip",
            name="Skip Intro",
            description="test",
            repository="skip-repo",
            bundle_directory="Skip",
            payload_slug="skip",
            install_script_name="Install.ps1",
            remove_script_name="Remove.ps1",
            preference_only=True,
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            merger = root / "merger"
            payload = merger / "payload" / "qol" / "skip"
            payload.mkdir(parents=True)
            (payload / "Install.ps1").write_text("", encoding="utf-8")
            (payload / "Remove.ps1").write_text("", encoding="utf-8")
            prefs = root / "MajXPrefs"
            prefs.write_text(
                "<DataGroups><IntroVideo>0</IntroVideo></DataGroups>",
                encoding="ascii",
            )
            service = QolService(
                repo_root=merger,
                game_executable=root / "missing" / "MajestyHD.exe",
                prefs_path=prefs,
                specs=(spec,),
            )

            status = service.inspect().get("skip")
            self.assertEqual(status.state, QolUtilityState.INSTALLED)
            self.assertTrue(status.supported)
            self.assertTrue(status.applicable)


class _StatefulRunner:
    def __init__(self, spec: QolPatchSpec):
        self.spec = spec
        self.installed = False
        self.commands = []

    def __call__(self, command):
        command = list(command)
        self.commands.append(command)
        if "-DryRun" in command:
            output = self.spec.installed_phrase if self.installed else "WouldPatch"
        elif Path(command[5]).name == self.spec.install_script_name:
            self.installed = True
            output = "installed"
        else:
            self.installed = False
            output = "restored"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")


def _test_spec() -> QolPatchSpec:
    return QolPatchSpec(
        key="test-patch",
        name="Test Patch",
        description="test",
        repository="standalone-test-patch",
        bundle_directory="Test Patch",
        payload_slug="test-patch",
        install_script_name="Install-Test.ps1",
        remove_script_name="Restore-Test.ps1",
        installed_phrase="already installed",
    )


def _write_synthetic_exe(
    path: Path,
    branch,
    *,
    timestamp: int | None = None,
    appended_section: bool = False,
    alter_first_section: bool = False,
) -> None:
    pe_offset = 0x80
    optional_offset = pe_offset + 24
    section_table = optional_offset + 0xE0
    section_count = 5 if appended_section else 4
    size = max(
        section.raw_offset + section.raw_size for section in branch.stock_sections
    )
    data = bytearray(size)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset : pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<HH", data, pe_offset + 4, 0x014C, section_count)
    struct.pack_into(
        "<I", data, pe_offset + 8, branch.coff_timestamp if timestamp is None else timestamp
    )
    struct.pack_into("<H", data, pe_offset + 20, 0xE0)
    struct.pack_into("<H", data, optional_offset, 0x010B)
    struct.pack_into("<I", data, optional_offset + 28, 0x00400000)
    struct.pack_into("<II", data, optional_offset + 32, 0x1000, 0x0200)
    struct.pack_into("<I", data, optional_offset + 60, 0x0400)
    for index, section in enumerate(branch.stock_sections):
        offset = section_table + (index * 40)
        name = section.name.encode("ascii")
        data[offset : offset + len(name)] = name
        virtual_size = section.virtual_size + (
            1 if alter_first_section and index == 0 else 0
        )
        struct.pack_into(
            "<IIII",
            data,
            offset + 8,
            virtual_size,
            section.rva,
            section.raw_size,
            section.raw_offset,
        )
        struct.pack_into("<I", data, offset + 36, section.characteristics)
    if appended_section:
        offset = section_table + (4 * 40)
        data[offset : offset + 5] = b".mpst"
        struct.pack_into("<IIII", data, offset + 8, 0x200, 0x500000, 0, 0)
        struct.pack_into("<I", data, offset + 36, 0xE0000020)
    path.write_bytes(data)


if __name__ == "__main__":
    unittest.main()
