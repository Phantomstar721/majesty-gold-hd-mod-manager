from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.workshop import (
    WorkshopOpenMethod,
    normalize_workshop_item_id,
    open_workshop_item,
    workshop_page_url,
    workshop_steam_uri,
)


class ManagerWorkshopTests(unittest.TestCase):
    def test_id_validation_rejects_non_ascii_injection_and_uint64_overflow(self):
        self.assertEqual(normalize_workshop_item_id(" 123456 "), "123456")
        invalid = (
            "",
            "0",
            "00123",
            "123&calc.exe",
            "123/../456",
            "１２３",
            "18446744073709551616",
            123,
            None,
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_workshop_item_id(value)

    def test_urls_are_built_only_from_validated_ids(self):
        self.assertEqual(
            workshop_page_url("123456"),
            "https://steamcommunity.com/sharedfiles/filedetails/?id=123456",
        )
        self.assertEqual(
            workshop_steam_uri("123456"),
            "steam://url/CommunityFilePage/123456",
        )

    @patch("majesty_cam.manager.workshop.webbrowser.open_new_tab")
    @patch("majesty_cam.manager.workshop.subprocess.Popen")
    @patch("majesty_cam.manager.workshop.find_steam_executable")
    def test_installed_steam_is_launched_with_argv_and_no_shell(
        self, find_steam, popen, open_browser
    ):
        find_steam.return_value = Path(r"C:\Program Files (x86)\Steam\steam.exe")

        with patch(
            "majesty_cam.manager.workshop.no_console_window_options",
            return_value={"creationflags": 0x08000000},
        ) as window_options:
            method = open_workshop_item("123456")

        self.assertEqual(method, WorkshopOpenMethod.STEAM)
        window_options.assert_called_once_with(force_hidden=False)
        args, kwargs = popen.call_args
        self.assertEqual(
            args[0],
            [
                r"C:\Program Files (x86)\Steam\steam.exe",
                "steam://url/CommunityFilePage/123456",
            ],
        )
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["creationflags"], 0x08000000)
        self.assertNotIn("startupinfo", kwargs)
        open_browser.assert_not_called()

    @patch("majesty_cam.manager.workshop.webbrowser.open_new_tab", return_value=True)
    @patch("majesty_cam.manager.workshop.find_steam_executable", return_value=None)
    def test_browser_is_used_when_steam_is_not_installed(self, find_steam, open_browser):
        method = open_workshop_item("123456")

        self.assertEqual(method, WorkshopOpenMethod.BROWSER)
        open_browser.assert_called_once_with(
            "https://steamcommunity.com/sharedfiles/filedetails/?id=123456"
        )

    @patch("majesty_cam.manager.workshop.webbrowser.open_new_tab", return_value=True)
    @patch("majesty_cam.manager.workshop.subprocess.Popen", side_effect=OSError("blocked"))
    @patch("majesty_cam.manager.workshop.find_steam_executable")
    def test_browser_is_fallback_when_installed_steam_cannot_start(
        self, find_steam, popen, open_browser
    ):
        find_steam.return_value = Path(r"C:\Steam\steam.exe")

        method = open_workshop_item("123456")

        self.assertEqual(method, WorkshopOpenMethod.BROWSER)
        popen.assert_called_once()
        open_browser.assert_called_once()

    @patch("majesty_cam.manager.workshop.webbrowser.open_new_tab", return_value=False)
    @patch("majesty_cam.manager.workshop.find_steam_executable", return_value=None)
    def test_failed_browser_open_is_reported(self, find_steam, open_browser):
        with self.assertRaises(OSError):
            open_workshop_item("123456")


if __name__ == "__main__":
    unittest.main()
