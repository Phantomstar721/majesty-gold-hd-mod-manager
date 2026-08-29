from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.gpl import DefinitionKind
from majesty_cam.manager.compatibility import (
    CompatibilityFormatError,
    load_compatibility_registry,
)


class ManagerCompatibilityTests(unittest.TestCase):
    def test_registry_and_adapter_rows_reject_unknown_or_missing_fields(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, row = _compatibility_fixture(root)
            content_id = "5F6B48D1-7B27-4D0E-92A4-52F12A997384"

            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mods": {content_id: row},
                        "runtime_capabilties": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                CompatibilityFormatError,
                "must contain only",
            ):
                load_compatibility_registry(registry_path, repo_root=root)

            missing_capabilities = dict(row)
            del missing_capabilities["runtime_capabilities"]
            missing_capabilities["runtime_capabilties"] = []
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mods": {content_id: missing_capabilities},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                CompatibilityFormatError,
                "missing runtime_capabilities.*unknown runtime_capabilties",
            ):
                load_compatibility_registry(registry_path, repo_root=root)

    def test_registry_rejects_duplicate_json_and_normalized_mod_keys(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, row = _compatibility_fixture(root)
            registry_path.write_text(
                '{"schema_version":1,"schema_version":1,"mods":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CompatibilityFormatError, "duplicate JSON key"):
                load_compatibility_registry(registry_path, repo_root=root)

            content_id = "5F6B48D1-7B27-4D0E-92A4-52F12A997384"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mods": {
                            content_id: row,
                            "{5f6b48d1-7b27-4d0e-92a4-52f12a997384}": row,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                CompatibilityFormatError,
                "repeats normalized Mod UUID",
            ):
                load_compatibility_registry(registry_path, repo_root=root)

    def test_combinations_require_distinct_mods_and_unique_requested_items(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, row = _compatibility_fixture(root)
            first_id = "5F6B48D1-7B27-4D0E-92A4-52F12A997384"
            second_id = "818F1460-3095-4B42-A64C-D55C11D7624E"
            base = {
                "schema_version": 1,
                "mods": {first_id: row},
                "combination_resolutions": [
                    {
                        "requires": [first_id, "{" + first_id.casefold() + "}"],
                        "source": "profiles/manager/resolution.gpl",
                        "items": [{"kind": "function", "name": "Resolve_This"}],
                    }
                ],
            }
            registry_path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaisesRegex(
                CompatibilityFormatError,
                "at least two distinct UUIDs",
            ):
                load_compatibility_registry(registry_path, repo_root=root)

            base["combination_resolutions"][0] = {
                "requires": [first_id, second_id],
                "source": "profiles/manager/resolution.gpl",
                "items": [
                    {"kind": "function", "name": "Resolve_This"},
                    {"kind": "function", "name": "resolve_this"},
                ],
            }
            registry_path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaisesRegex(
                CompatibilityFormatError,
                "items repeats function:resolve_this",
            ):
                load_compatibility_registry(registry_path, repo_root=root)

    def test_compatibility_registry_contains_no_private_text_bindings(self):
        registry_path = REPO_ROOT / "profiles" / "manager" / "compatibility.json"
        payload = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertNotIn("private_activity_texts", registry_path.read_text(encoding="utf-8"))
        self.assertNotIn(
            "private-activity-text-registry.v1",
            registry_path.read_text(encoding="utf-8"),
        )
        self.assertTrue(payload["mods"])

    def test_builtin_profiles_cover_current_haunt_and_alchemist(self):
        registry = load_compatibility_registry(repo_root=REPO_ROOT)

        haunt = registry.get("{8c48289e-7c70-4426-8913-133f3544a182}")
        self.assertEqual(haunt.alias, "phantoms-haunt")
        self.assertIn("expanded-building-slots.cg-prefix", haunt.runtime_capabilities)
        self.assertTrue(haunt.definition_path.is_file())
        self.assertIn("Elf Guild", haunt.badge)

        alchemist = registry.get("42ba4603-2b13-446d-a2a4-6cf3a55ddac3")
        self.assertEqual(alchemist.alias, "alchemist")
        self.assertEqual(alchemist.merge_priority, 100)
        self.assertEqual(alchemist.resolution_owners, ())
        combined = registry.combination_resolutions[0]
        self.assertEqual(
            set(combined.required_mod_ids),
            {
                "8C48289E-7C70-4426-8913-133F3544A182",
                "42BA4603-2B13-446D-A2A4-6CF3A55DDAC3",
            },
        )
        self.assertTrue(combined.source_path.is_file())
        self.assertEqual(
            [(item.kind, item.name) for item in combined.items],
            [
                (DefinitionKind.FUNCTION, "Random_Hero_Type"),
                (DefinitionKind.FUNCTION, "spell_extra_value"),
            ],
        )


def _compatibility_fixture(root: Path) -> tuple[Path, dict]:
    registry_path = root / "profiles/manager/compatibility.json"
    definition = root / "profiles/poc/fixture.json"
    resolution = root / "profiles/manager/resolution.gpl"
    registry_path.parent.mkdir(parents=True)
    definition.parent.mkdir(parents=True)
    definition.write_text("{}", encoding="utf-8")
    resolution.write_text(
        "function Resolve_This() is integer\nbegin\nreturn 1;\nend\n",
        encoding="cp1252",
    )
    row = {
        "alias": "fixture",
        "definition": "profiles/poc/fixture.json",
        "replacement_roots": [],
        "merge_priority": 1000,
        "badge": "Fixture",
        "runtime_capabilities": [],
        "resolution_owners": [],
    }
    return registry_path, row


if __name__ == "__main__":
    unittest.main()
