from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.package import (
    CamLoad,
    CustomBuildingDefinition,
    DescriptionsLoad,
    GplLoad,
    ModDefinition,
    PackageFormatError,
    load_mod_definition,
    load_package,
    parse_mod_definition,
)


MOD_ID = "{42ba4603-2b13-446d-a2a4-6cf3a55ddac3}"


class PackageTests(unittest.TestCase):
    def test_loads_manifest_and_default_definition_in_declared_order(self):
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            for relative in (
                "Data/first.cam",
                "Data/descriptions.xml",
                "Data/package.bcd",
                "GPL/first.gpl",
                "GPL/second.dat",
                "Data/second.cam",
                "Data/base.cam",
            ):
                _write_file(package / relative)

            _write_manifest(
                package,
                """
                <Dataset base="MajestyExpansion">
                  <Load>
                    <CAM>Data\\first.cam</CAM>
                    <Descriptions>Data\\descriptions.xml</Descriptions>
                    <GPL>
                      <Target>Data\\package.bcd</Target>
                      <Source>GPL\\first.gpl</Source>
                      <Source>GPL\\second.dat</Source>
                    </GPL>
                    <CAM>Data\\second.cam</CAM>
                  </Load>
                </Dataset>
                <Dataset base="Majesty">
                  <Load><CAM>Data\\base.cam</CAM></Load>
                </Dataset>
                """,
            )
            (package / "mod-definition.json").write_text(
                json.dumps(_definition_mapping()), encoding="utf-8"
            )

            result = load_package(package)

            self.assertEqual(result.mod_id, MOD_ID)
            self.assertEqual(result.display_name, "Fixture Mod")
            self.assertEqual(result.metadata.short_descriptions[0].text, "Short fixture")
            self.assertEqual(result.metadata.long_descriptions[0].text, "Long fixture")
            self.assertEqual(
                [dataset.base for dataset in result.datasets],
                ["MajestyExpansion", "Majesty"],
            )

            directives = result.datasets[0].loads[0].directives
            self.assertEqual(
                [type(item) for item in directives],
                [CamLoad, DescriptionsLoad, GplLoad, CamLoad],
            )
            self.assertEqual(
                [item.file.relative_path for item in directives if isinstance(item, CamLoad)],
                ["Data/first.cam", "Data/second.cam"],
            )
            gpl = directives[2]
            self.assertIsInstance(gpl, GplLoad)
            self.assertEqual([item.role for item in gpl.files], ["target", "source", "source"])
            self.assertEqual(gpl.target.relative_path, "Data/package.bcd")
            self.assertEqual(
                [source.relative_path for source in gpl.sources],
                ["GPL/first.gpl", "GPL/second.dat"],
            )
            self.assertEqual(result.definition.internal_name, "CustomGuildAlchemist")
            self.assertEqual(result.definition.custom_buildings[0].dialog_id, "CGAL")

    def test_definition_is_optional_and_can_be_supplied_as_an_object(self):
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><CAM>Data\\fixture.cam</CAM></Load></Dataset>',
            )

            without_definition = load_package(package)
            self.assertIsNone(without_definition.definition)

            supplied = ModDefinition(
                schema_version=1,
                mod_id=MOD_ID.strip("{}").upper(),
                internal_name="HauntCompatibility",
                display_name="Haunt Compatibility Definition",
                custom_buildings=(
                    CustomBuildingDefinition(
                        local_name="PhantomsHaunt",
                        dialog_id="CGPH",
                        controller_base="AP10",
                        panel_resource_template="AP10",
                    ),
                ),
            )
            with_definition = load_package(package, definition=supplied)
            self.assertEqual(with_definition.definition.internal_name, "HauntCompatibility")
            self.assertIsInstance(with_definition.definition.custom_buildings, tuple)

            supplied_v2 = ModDefinition(
                schema_version=2,
                mod_id=MOD_ID.strip("{}").upper(),
                internal_name="PackageOwnedCapabilities",
                display_name="Package-Owned Capabilities",
                custom_buildings=(),
                runtime_capabilities=("example.stock-clone.v1",),
            )
            with_v2_definition = load_package(package, definition=supplied_v2)
            self.assertEqual(
                with_v2_definition.definition.runtime_capabilities,
                ("example.stock-clone.v1",),
            )

    def test_definition_can_be_supplied_from_an_explicit_external_path(self):
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            package = temp_root / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><CAM>Data\\fixture.cam</CAM></Load></Dataset>',
            )
            external_definition = temp_root / "haunt-definition.json"
            external_definition.write_text(
                json.dumps(_definition_mapping(internal_name="HauntCompatibility")),
                encoding="utf-8",
            )

            result = load_package(package, definition=external_definition)

            self.assertEqual(result.definition.internal_name, "HauntCompatibility")

    def test_relative_definition_override_cannot_escape_package_root(self):
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            package = temp_root / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><CAM>Data\\fixture.cam</CAM></Load></Dataset>',
            )
            external_definition = temp_root / "outside.json"
            external_definition.write_text(
                json.dumps(_definition_mapping()), encoding="utf-8"
            )

            with self.assertRaisesRegex(PackageFormatError, "escapes package root"):
                load_package(package, definition="../outside.json")

    def test_rejects_missing_escaping_and_absolute_manifest_resources(self):
        cases = {
            "missing": "Data\\missing.cam",
            "escaping": "..\\outside.cam",
            "absolute": "C:\\Majesty\\outside.cam",
        }
        for name, declared_path in cases.items():
            with self.subTest(name=name), TemporaryDirectory() as tmp:
                temp_root = Path(tmp)
                package = temp_root / "package"
                package.mkdir()
                _write_file(temp_root / "outside.cam")
                _write_manifest(
                    package,
                    (
                        '<Dataset base="Any"><Load><CAM>'
                        + declared_path
                        + "</CAM></Load></Dataset>"
                    ),
                )

                with self.assertRaises(PackageFormatError):
                    load_package(package)

    def test_rejects_duplicate_resource_paths_after_normalization(self):
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                """
                <Dataset base="Any"><Load>
                  <CAM>Data\\fixture.cam</CAM>
                  <CAM>Data/./fixture.cam</CAM>
                </Load></Dataset>
                """,
            )

            with self.assertRaisesRegex(PackageFormatError, "duplicate package path"):
                load_package(package)

    def test_rejects_ambiguous_manifest_or_mod_elements(self):
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><CAM>Data\\fixture.cam</CAM></Load></Dataset>',
            )
            (package / "second.mmxml").write_text("<Majesty/>", encoding="utf-8")
            with self.assertRaisesRegex(PackageFormatError, "multiple top-level"):
                load_package(package)

            (package / "second.mmxml").unlink()
            (package / "fixture.mmxml").write_text(
                "<Majesty><Mod id=\"one\"><DisplayName>One</DisplayName>"
                "<DataConfiguration><Dataset><Load/></Dataset></DataConfiguration></Mod>"
                "<Mod id=\"two\"><DisplayName>Two</DisplayName>"
                "<DataConfiguration><Dataset><Load/></Dataset></DataConfiguration></Mod>"
                "</Majesty>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PackageFormatError, "exactly one Mod"):
                load_package(package)

    def test_definition_requires_exact_v1_fields_and_unique_buildings(self):
        valid = _definition_mapping()

        extra = dict(valid)
        extra["future_field"] = True
        with self.assertRaisesRegex(PackageFormatError, "unknown future_field"):
            parse_mod_definition(extra)

        bad_version = dict(valid)
        bad_version["schema_version"] = 3
        with self.assertRaisesRegex(PackageFormatError, "unsupported"):
            parse_mod_definition(bad_version)

        duplicate = dict(valid)
        duplicate_building = dict(valid["custom_buildings"][0])
        duplicate_building["local_name"] = "AnotherBuilding"
        duplicate["custom_buildings"] = [
            dict(valid["custom_buildings"][0]),
            duplicate_building,
        ]
        with self.assertRaisesRegex(PackageFormatError, "duplicate custom building dialog_id"):
            parse_mod_definition(duplicate)

        building_extra = _definition_mapping()
        building_extra["custom_buildings"][0]["future_field"] = True
        with self.assertRaisesRegex(PackageFormatError, "unknown future_field"):
            parse_mod_definition(building_extra)

    def test_definition_v2_owns_strict_runtime_capability_declarations(self):
        value = _definition_mapping()
        value["schema_version"] = 2
        value["runtime_capabilities"] = [
            "example.stock-clone.v1",
            "example.private-resource.v2",
        ]

        parsed = parse_mod_definition(value)

        self.assertEqual(parsed.schema_version, 2)
        self.assertEqual(
            parsed.runtime_capabilities,
            (
                "example.stock-clone.v1",
                "example.private-resource.v2",
            ),
        )

        for capabilities, message in (
            (["Example.MixedCase"], "lowercase dotted capability"),
            (["not-dotted"], "lowercase dotted capability"),
            (["example."], "lowercase dotted capability"),
            (["example..feature"], "lowercase dotted capability"),
            (["example.bad_feature"], "lowercase dotted capability"),
            (["example.valid", "example.valid"], "duplicate runtime capability"),
            ("example.not-an-array", "must be an array"),
        ):
            with self.subTest(capabilities=capabilities):
                invalid = _definition_mapping()
                invalid["schema_version"] = 2
                invalid["runtime_capabilities"] = capabilities
                with self.assertRaisesRegex(PackageFormatError, message):
                    parse_mod_definition(invalid)

    def test_definition_v1_stays_backward_compatible_without_capabilities(self):
        parsed = parse_mod_definition(_definition_mapping())

        self.assertEqual(parsed.schema_version, 1)
        self.assertEqual(parsed.runtime_capabilities, ())

        invalid = _definition_mapping()
        invalid["runtime_capabilities"] = []
        with self.assertRaisesRegex(PackageFormatError, "unknown runtime_capabilities"):
            parse_mod_definition(invalid)

    def test_rejects_duplicate_json_keys_and_definition_id_mismatch(self):
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            duplicate_json = temp_root / "duplicate.json"
            duplicate_json.write_text(
                '{"schema_version":1,"mod_id":"one","mod_id":"two",'
                '"internal_name":"x","display_name":"x","custom_buildings":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PackageFormatError, "duplicate JSON key"):
                load_mod_definition(duplicate_json)

            package = temp_root / "package"
            package.mkdir()
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><CAM>Data\\fixture.cam</CAM></Load></Dataset>',
            )
            mismatch = _definition_mapping()
            mismatch["mod_id"] = "a-different-mod"
            with self.assertRaisesRegex(PackageFormatError, "does not match"):
                load_package(package, definition=mismatch)

    def test_rejects_unknown_load_and_gpl_directives(self):
        with TemporaryDirectory() as tmp:
            package = Path(tmp)
            _write_file(package / "Data" / "fixture.cam")
            _write_manifest(
                package,
                '<Dataset base="Any"><Load><Future>Data\\fixture.cam</Future>'
                '</Load></Dataset>',
            )
            with self.assertRaisesRegex(PackageFormatError, "unsupported manifest"):
                load_package(package)

            _write_manifest(
                package,
                '<Dataset base="Any"><Load><GPL>'
                '<Target>Data\\fixture.cam</Target>'
                '<Future>Data\\fixture.cam</Future>'
                '</GPL></Load></Dataset>',
            )
            with self.assertRaisesRegex(PackageFormatError, "unsupported GPL"):
                load_package(package)


def _write_manifest(package: Path, datasets_xml: str) -> None:
    manifest = f"""
    <Majesty>
      <Mod id="{MOD_ID}">
        <DisplayName lang="fr_FR">Module d'essai</DisplayName>
        <DisplayName lang="en_US">Fixture Mod</DisplayName>
        <Description lang="en_US">
          <Short>Short fixture</Short>
          <Long>Long fixture</Long>
        </Description>
        <DataConfiguration>
          {datasets_xml}
        </DataConfiguration>
      </Mod>
    </Majesty>
    """
    (package / "fixture.mmxml").write_text(manifest, encoding="utf-8")


def _write_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _definition_mapping(internal_name: str = "CustomGuildAlchemist") -> dict:
    return {
        "schema_version": 1,
        "mod_id": MOD_ID,
        "internal_name": internal_name,
        "display_name": "Custom Guild: Alchemist Lab",
        "custom_buildings": [
            {
                "local_name": "AlchemistsLaboratory",
                "dialog_id": "CGAL",
                "controller_base": "AP10",
                "panel_resource_template": "AP10",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
