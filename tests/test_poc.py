from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.poc import build_haunt_profile, build_poc_profiles


class HauntProofTests(unittest.TestCase):
    def test_freestyle_haunt_build_has_no_alchemist_input_dependency(self):
        definition = object()
        package = object()
        composed = object()
        with (
            patch("majesty_cam.poc.load_mod_definition", return_value=definition),
            patch("majesty_cam.poc.load_package", return_value=package) as load_package,
            patch("majesty_cam.poc.compose_package", return_value=composed) as compose,
        ):
            result = build_haunt_profile(
                Path("game"),
                Path("inputs"),
                Path("output"),
                definition_root=Path("definitions"),
            )

        self.assertIs(result, composed)
        load_package.assert_called_once_with(
            Path("inputs/haunt-ap07"), definition=definition
        )
        args, kwargs = compose.call_args
        self.assertEqual(args[0], Path("game"))
        self.assertEqual(args[1], Path("output"))
        self.assertEqual([selected.alias for selected in args[2]], ["haunt"])
        self.assertEqual(kwargs["profile_slug"], "haunt-freestyle")
        self.assertEqual(
            kwargs["runtime_capabilities"],
            (
                "expanded-building-slots.cg-prefix",
                "freestyle-cam-rebind.v1",
            ),
        )

    def test_combined_profile_does_not_treat_named_reagent_as_numeric_item(self):
        definition = object()
        package = object()
        composed = object()
        with (
            patch("majesty_cam.poc.load_mod_definition", return_value=definition),
            patch("majesty_cam.poc.load_package", return_value=package),
            patch("majesty_cam.poc.compose_package", return_value=composed) as compose,
        ):
            build_poc_profiles(
                Path("game"),
                Path("inputs"),
                Path("output"),
                definition_root=Path("definitions"),
            )

        combined = compose.call_args_list[2]
        self.assertNotIn(
            "inventory_death_drop_exclusions",
            combined.kwargs,
        )


if __name__ == "__main__":
    unittest.main()
