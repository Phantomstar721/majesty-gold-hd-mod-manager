from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.package import (
    Ap78EnchantmentRowFeature,
    CamLoad,
    CustomBuildingDefinition,
    DescriptionsLoad,
    GplLoad,
    ModDefinition,
    NameGeneratorFeature,
    PackageFormatError,
    load_mod_definition,
    load_package,
    parse_mod_definition,
    _validate_definition_object,
)
from majesty_cam.gpl_features import (
    StockControlledFollowerSpeedSync,
    StockHeroQuestLifecycle,
    StockGplmxPurchaseBazaarTail,
    StockGplmxPurchaseEquipmentTail,
)
from majesty_cam.stock_controller_features import (
    StockMx05LiveAgentListPanel,
    StockMx22BuildingOpenToggle,
    StockAp69SovereignTargetAction,
    controller_feature_mapping,
    legacy_alchemist_controller_features,
)


MOD_ID = "{42ba4603-2b13-446d-a2a4-6cf3a55ddac3}"


class PackageTests(unittest.TestCase):
    def test_definition_v3_parses_bounded_live_agent_list(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "QuestBoardExample",
            "display_name": "Quest Board Example",
            "custom_buildings": [{
                "local_name": "QuestGuild",
                "controller_base": "AP08",
                "panel_resource_template": "AP08",
            }],
            "runtime_features": [{
                "type": "stock.mx05-live-agent-list-panel.v1",
                "panel_key": "quests",
                "parent_building": "QuestGuild",
                "source_dialog_id": "QB01",
                "open_command_id": 29001,
                "row_count_callback_symbol": "QB_Count",
                "row_agent_id_callback_symbol": "QB_Agent_Id",
                "revision_callback_symbol": "QB_Revision",
                "row_title_text": None,
                "row_text": "Deliver orders to an allied building",
                "row_value_callback_symbol": "QB_Reward",
                "row_value_suffix_text": " Gold",
                "action_cost_callback_symbol": "QB_Cost",
                "action_callback_symbol": "QB_Refresh",
            }],
        }
        parsed = parse_mod_definition(value)
        board = parsed.runtime_features[0]
        self.assertIsInstance(board, StockMx05LiveAgentListPanel)
        self.assertEqual(board.row_count_callback_symbol, "QB_Count")
        self.assertEqual(board.row_agent_id_callback_symbol, "QB_Agent_Id")
        self.assertIsNone(board.row_title_text)

    def test_definition_v3_rejects_obsolete_quest_board_agent_contract(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "ObsoleteQuestBoard",
            "display_name": "Obsolete Quest Board",
            "custom_buildings": [{
                "local_name": "QuestGuild",
                "controller_base": "AP08",
                "panel_resource_template": "AP08",
            }],
            "runtime_features": [{
                "type": "stock.ap08-mx05-quest-list-panel.v4",
            }],
        }
        with self.assertRaisesRegex(PackageFormatError, "type is unsupported"):
            parse_mod_definition(value)

    def test_definition_v3_rejects_obsolete_live_list_agent_field(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "ObsoleteLiveList",
            "display_name": "Obsolete Live List",
            "custom_buildings": [{
                "local_name": "ListParent",
                "controller_base": "AP08",
                "panel_resource_template": "AP08",
            }],
            "runtime_features": [{
                "type": "stock.mx05-live-agent-list-panel.v1",
                "panel_key": "offers",
                "parent_building": "ListParent",
                "source_dialog_id": "LP01",
                "open_command_id": 29001,
                "row_count_callback_symbol": "Rows_Count",
                "row_agent_callback_symbol": "Rows_Agent",
                "revision_callback_symbol": "Rows_Revision",
                "row_title_text": None,
                "row_text": "Available",
                "row_value_callback_symbol": None,
                "row_value_suffix_text": None,
                "action_cost_callback_symbol": "Rows_Cost",
                "action_callback_symbol": "Rows_Action",
            }],
        }
        with self.assertRaisesRegex(
            PackageFormatError, "row_agent_id_callback_symbol"
        ):
            parse_mod_definition(value)

    def test_definition_v3_parses_generic_toggle_and_purchase_tail(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "GenericStockFeatures",
            "display_name": "Generic Stock Features",
            "custom_buildings": [
                {
                    "local_name": "PrivateBuilding",
                    "controller_base": "MX09",
                    "panel_resource_template": "MX09",
                }
            ],
            "runtime_features": [
                {
                    "type": "stock.mx22-building-open-toggle.v1",
                    "toggle_key": "rentals",
                    "parent_building": "PrivateBuilding",
                    "open_command_id": 24001,
                    "close_command_id": 24002,
                },
                {
                    "type": "stock.gplmx-purchase-equipment-tail.v1",
                    "callback_key": "rental-check",
                    "callback_symbol": "Private_Rental_Check",
                },
                {
                    "type": "stock.gplmx-purchase-bazaar-tail.v1",
                    "callback_key": "late-rental-check",
                    "callback_symbol": "Private_Late_Rental_Check",
                },
                {
                    "type": "stock.controlled-follower-speed-sync.v1",
                    "feature_key": "rental-speed",
                    "eligibility_callback_symbol": "Private_Rental_Speed_Applies",
                    "movement_rate_modifier_per_tier": -100,
                },
                {
                    "type": "stock.hero-quest-lifecycle.v1",
                    "feature_key": "guild-quests",
                    "hero_scripts": ["mx_ranger", "mx_adept"],
                    "decision_callback_symbol": "Guild_Quest_Decide",
                    "reset_callback_symbol": "Guild_Quest_Reset",
                    "death_callback_symbol": "Guild_Quest_Death",
                },
            ],
        }

        parsed = parse_mod_definition(value)

        self.assertIsInstance(parsed.runtime_features[0], StockMx22BuildingOpenToggle)
        self.assertIsInstance(parsed.runtime_features[1], StockGplmxPurchaseEquipmentTail)
        self.assertEqual(parsed.runtime_features[1].callback_symbol, "Private_Rental_Check")
        self.assertIsInstance(parsed.runtime_features[2], StockGplmxPurchaseBazaarTail)
        self.assertIsInstance(parsed.runtime_features[3], StockControlledFollowerSpeedSync)
        self.assertEqual(
            parsed.runtime_features[3].movement_rate_modifier_per_tier, -100
        )
        self.assertIsInstance(parsed.runtime_features[4], StockHeroQuestLifecycle)
        self.assertEqual(parsed.runtime_features[4].hero_scripts, ("mx_adept", "mx_ranger"))
        self.assertEqual(_validate_definition_object(parsed), parsed)

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

            supplied_v3 = ModDefinition(
                schema_version=3,
                mod_id=MOD_ID.strip("{}").upper(),
                internal_name="DeclarativeFeatures",
                display_name="Declarative Features",
                custom_buildings=(),
                runtime_features=(
                    NameGeneratorFeature(
                        generator_id="NM42",
                        name_part_ids=("HN81", "HN82", "HN83", "HN84"),
                    ),
                ),
            )
            with_v3_definition = load_package(package, definition=supplied_v3)
            self.assertEqual(
                with_v3_definition.definition.runtime_features,
                supplied_v3.runtime_features,
            )

            controller_features = legacy_alchemist_controller_features(
                "FixtureGuild"
            )
            supplied_v3_controllers = ModDefinition(
                schema_version=3,
                mod_id=MOD_ID.strip("{}").upper(),
                internal_name="DeclarativeControllers",
                display_name="Declarative Controllers",
                custom_buildings=(
                    CustomBuildingDefinition(
                        local_name="FixtureGuild",
                        dialog_id=None,
                        controller_base="AP10",
                        panel_resource_template="AP10",
                    ),
                ),
                runtime_features=controller_features,
            )
            with_controllers = load_package(
                package, definition=supplied_v3_controllers
            )
            self.assertEqual(
                with_controllers.definition.runtime_features,
                controller_features,
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
        bad_version["schema_version"] = 4
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

    def test_definition_v3_uses_typed_features_and_manager_owned_dialog_ids(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "DeclarativeFixture",
            "display_name": "Declarative Fixture",
            "custom_buildings": [
                {
                    "local_name": "FixtureGuild",
                    "controller_base": "AP10",
                    "panel_resource_template": "AP10",
                }
            ],
            "runtime_features": [
                {
                    "type": "stock.name-generator.v1",
                    "generator_id": "NM42",
                    "name_tables": ["HN81", "HN82", "HN83", "HN84"],
                },
                {
                    "type": "stock.ap78-enchantment-row.v1",
                    "overlay_id": "OV42",
                    "display_text": "Vigorous heroes",
                },
            ],
        }

        parsed = parse_mod_definition(value)

        self.assertEqual(parsed.schema_version, 3)
        self.assertIsNone(parsed.custom_buildings[0].dialog_id)
        self.assertIsInstance(parsed.runtime_features[0], NameGeneratorFeature)
        self.assertEqual(
            parsed.runtime_features[0].name_part_ids,
            ("HN81", "HN82", "HN83", "HN84"),
        )
        self.assertIsInstance(
            parsed.runtime_features[1], Ap78EnchantmentRowFeature
        )
        self.assertEqual(parsed.runtime_capabilities, ())

    def test_definition_v3_feature_shapes_fail_closed(self):
        base = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "DeclarativeFixture",
            "display_name": "Declarative Fixture",
            "custom_buildings": [],
            "runtime_features": [],
        }
        invalid_features = (
            (
                {"type": "future.native-hook.v1"},
                "type is unsupported",
            ),
            (
                {
                    "type": "stock.name-generator.v1",
                    "generator_id": "NM42",
                    "name_tables": ["HN81", "HN82", "HN83"],
                },
                "exactly four",
            ),
            (
                {
                    "type": "stock.name-generator.v1",
                    "generator_id": "TOO-LONG",
                    "name_tables": ["HN81", "HN82", "HN83", "HN84"],
                },
                "exactly four printable ASCII",
            ),
            (
                {
                    "type": "stock.ap78-enchantment-row.v1",
                    "overlay_id": "OV42",
                    "display_text": "not cp1252: \U0001f9ea",
                },
                "Windows-1252",
            ),
            (
                {
                    "type": "stock.ap78-enchantment-row.v1",
                    "overlay_id": "OV42",
                    "display_text": "x" * 513,
                },
                "1..512",
            ),
            (
                {
                    "type": "stock.ap78-enchantment-row.v1",
                    "overlay_id": "OV42",
                    "display_text": "valid",
                    "future": True,
                },
                "unknown future",
            ),
        )
        for feature, message in invalid_features:
            with self.subTest(feature=feature):
                value = dict(base)
                value["runtime_features"] = [feature]
                with self.assertRaisesRegex(PackageFormatError, message):
                    parse_mod_definition(value)

        with_legacy_field = dict(base)
        with_legacy_field["runtime_capabilities"] = []
        with self.assertRaisesRegex(PackageFormatError, "unknown runtime_capabilities"):
            parse_mod_definition(with_legacy_field)

        building_with_dialog = dict(base)
        building_with_dialog["custom_buildings"] = [
            {
                "local_name": "FixtureGuild",
                "dialog_id": "CGFX",
                "controller_base": "AP10",
                "panel_resource_template": "AP10",
            }
        ]
        with self.assertRaisesRegex(PackageFormatError, "unknown dialog_id"):
            parse_mod_definition(building_with_dialog)

    def test_definition_v3_parses_every_stock_controller_recipe(self):
        controller_features = legacy_alchemist_controller_features("FixtureGuild")
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "DeclarativeFixture",
            "display_name": "Declarative Fixture",
            "custom_buildings": [
                {
                    "local_name": "FixtureGuild",
                    "controller_base": "AP10",
                    "panel_resource_template": "AP10",
                }
            ],
            "runtime_features": [
                controller_feature_mapping(feature)
                for feature in controller_features
            ],
        }

        parsed = parse_mod_definition(value)

        self.assertEqual(parsed.runtime_features, controller_features)
        sovereign = next(
            feature
            for feature in parsed.runtime_features
            if isinstance(feature, StockAp69SovereignTargetAction)
        )
        self.assertEqual(sovereign.stock_target_mode, "Sp23")
        self.assertEqual(sovereign.stock_executor_mode, "Sp14")

        second_timed = next(
            dict(feature)
            for feature in value["runtime_features"]
            if feature["type"] == "stock.ap24-timed-rage-action.v1"
        )
        second_timed.update(
            {
                "action_key": "second-timed-action",
                "action_control_id": 0x6A01,
                "callback_symbol": "Example_SecondTimedAction",
                "icon_control_id": 0x6A02,
                "price_control_id": 0x6A03,
                "progress_control_id": 0x6A04,
                "active_display_control_id": 0x6A05,
            }
        )
        multiple_actions = json.loads(json.dumps(value))
        multiple_actions["runtime_features"].append(second_timed)
        self.assertEqual(
            len(parse_mod_definition(multiple_actions).runtime_features),
            len(controller_features) + 1,
        )

        missing_executor = json.loads(json.dumps(value))
        target = next(
            feature
            for feature in missing_executor["runtime_features"]
            if feature["type"] == "stock.ap69-sovereign-target-action.v1"
        )
        del target["stock_executor_mode"]
        with self.assertRaisesRegex(PackageFormatError, "stock_executor_mode"):
            parse_mod_definition(missing_executor)

    def test_definition_v3_rejects_unproven_building_controller_combinations(self):
        value = {
            "schema_version": 3,
            "mod_id": MOD_ID,
            "internal_name": "DeclarativeFixture",
            "display_name": "Declarative Fixture",
            "custom_buildings": [
                {
                    "local_name": "FixtureGuild",
                    "controller_base": "AP69",
                    "panel_resource_template": "AP10",
                }
            ],
            "runtime_features": [],
        }
        with self.assertRaisesRegex(PackageFormatError, "unsupported stock"):
            parse_mod_definition(value)

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
