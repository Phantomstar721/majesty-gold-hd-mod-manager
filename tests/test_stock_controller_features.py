from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.stock_controller_features import (
    CONTROLLER_FEATURE_FORMAT,
    ControllerFeatureError,
    LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,
    StockAp10Ap69SecondaryPanel,
    StockAp41Fl00HostileMonsterFlag,
    StockMx09Ap41RewardPanel,
    StockAp17UpgradeResearchGate,
    StockAp22ResourceMeter,
    StockAp24RageCommandAction,
    StockAp24TimedRageAction,
    StockAp69SovereignTargetAction,
    StockAp99ResearchRow,
    controller_feature_mapping,
    decode_controller_features,
    encode_controller_features,
    legacy_alchemist_controller_features,
    legacy_controller_features,
    normalize_controller_features,
    parse_controller_feature,
)


class StockControllerFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.features = legacy_alchemist_controller_features(
            "AlchemistsLaboratory"
        )

    def test_legacy_translation_decomposes_exact_stock_lifecycles(self) -> None:
        self.assertEqual(len(self.features), 8)
        self.assertEqual(
            [feature.type for feature in self.features],
            [
                "stock.ap10-ap69-secondary-panel.v1",
                "stock.ap22-resource-meter.v1",
                "stock.ap99-research-row.v1",
                "stock.ap99-research-row.v1",
                "stock.ap17-upgrade-research-gate.v1",
                "stock.ap24-timed-rage-action.v1",
                "stock.ap24-rage-command-action.v1",
                "stock.ap69-sovereign-target-action.v1",
            ],
        )

        panel = next(
            item
            for item in self.features
            if isinstance(item, StockAp10Ap69SecondaryPanel)
        )
        self.assertEqual(panel.parent_building, "AlchemistsLaboratory")
        self.assertEqual(panel.source_dialog_id, "CGBR")
        self.assertEqual(panel.building_family_id, "ALB")
        self.assertEqual(panel.open_command_id, 0x1F49)

        meter = next(
            item for item in self.features if isinstance(item, StockAp22ResourceMeter)
        )
        self.assertEqual(
            (
                meter.attribute_id,
                meter.label_control_id,
                meter.count_control_id,
                meter.binding_control_id,
            ),
            ("APV0", 0x2A23, 0x2A24, 0x2A25),
        )

        research = {
            item.recipe_key: item
            for item in self.features
            if isinstance(item, StockAp99ResearchRow)
        }
        weapon = research["weapon-oil"]
        self.assertEqual(
            (
                weapon.action_control_id,
                weapon.descriptor_template_control_id,
                weapon.completion_template_control_id,
                weapon.required_level,
                weapon.price,
                weapon.progress_control_id,
                weapon.active_display_control_id,
                weapon.completion_text,
            ),
            (0x2A13, 0x139C, 0x139C, 1, 250, 0x2A11, 0x2A12, "Weapon Oil"),
        )
        phoenix = research["phoenix-phial"]
        self.assertEqual(
            (
                phoenix.action_control_id,
                phoenix.descriptor_template_control_id,
                phoenix.completion_template_control_id,
                phoenix.required_level,
                phoenix.price,
                phoenix.progress_control_id,
                phoenix.active_display_control_id,
                phoenix.completion_text,
            ),
            (0x2A16, 0x139C, 0x13B3, 2, 750, 0x2A17, 0x2A18, "Phoenix Phial"),
        )

        gate = next(
            item
            for item in self.features
            if isinstance(item, StockAp17UpgradeResearchGate)
        )
        self.assertEqual(gate.upgrade_control_id, 0x1F47)
        self.assertEqual(gate.upgrade_price_control_id, 0x1F4F)
        self.assertEqual(
            [(item.building_level, item.recipe_key) for item in gate.requirements],
            [(1, "weapon-oil"), (2, "phoenix-phial")],
        )

        vigor = next(
            item
            for item in self.features
            if isinstance(item, StockAp24TimedRageAction)
        )
        self.assertEqual(
            (
                vigor.action_control_id,
                vigor.descriptor_template_control_id,
                vigor.level_price_template_control_id,
                vigor.required_level,
                vigor.gold_cost,
                vigor.resource_cost,
                vigor.callback_symbol,
                vigor.duration_ms,
                vigor.progress_control_id,
                vigor.active_display_control_id,
            ),
            (
                0x2A10,
                0x1140,
                0x113E,
                3,
                1500,
                1,
                "Alchemist_DoInvigoratingElixer",
                30000,
                0x2009,
                0x227A,
            ),
        )

        infusion = next(
            item
            for item in self.features
            if isinstance(item, StockAp24RageCommandAction)
        )
        self.assertEqual(
            (
                infusion.action_control_id,
                infusion.visual_template_control_id,
                infusion.completion_template_research_control_id,
                infusion.required_level,
                infusion.resource_cost,
                infusion.callback_symbol,
            ),
            (0x1132, 0x1132, 0x139C, 3, 10, "Alchemist_Arcane_Infusion"),
        )

        stone = next(
            item
            for item in self.features
            if isinstance(item, StockAp69SovereignTargetAction)
        )
        self.assertEqual(
            (
                stone.visual_control_id,
                stone.private_control_id,
                stone.visual_template_control_id,
                stone.target_template_control_id,
                stone.stock_target_mode,
                stone.stock_executor_mode,
                stone.private_mode,
                stone.private_unit_id,
                stone.cursor_ordinal,
                stone.required_level,
                stone.resource_cost,
            ),
            (0x1133, 0x2A21, 0x1133, 0x1132, "Sp23", "Sp14", "AlS1", "ALS1", 39, 3, 10),
        )

    def test_legacy_adapter_needs_only_parent_building_not_package_identity(self) -> None:
        features = legacy_controller_features(
            (LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,),
            parent_building="AnyLocalBuilding",
        )
        panel = next(
            item for item in features if isinstance(item, StockAp10Ap69SecondaryPanel)
        )
        self.assertEqual(panel.parent_building, "AnyLocalBuilding")
        encoded = encode_controller_features(features)
        self.assertNotIn(b"42ba4603", encoded)
        self.assertNotIn(b"Custom Guild", encoded)

        with self.assertRaisesRegex(ControllerFeatureError, "parent building"):
            legacy_controller_features((LEGACY_ALCHEMIST_CONTROLLER_CAPABILITY,))
        self.assertEqual(legacy_controller_features(("example.other.v1",)), ())

    def test_canonical_encoding_is_deterministic_and_round_trips(self) -> None:
        forward = encode_controller_features(self.features)
        reverse = encode_controller_features(tuple(reversed(self.features)))
        duplicate = encode_controller_features((*self.features, *self.features))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward, duplicate)
        self.assertEqual(decode_controller_features(forward), self.features)
        root = json.loads(forward.decode("utf-8"))
        self.assertEqual(root["format"], CONTROLLER_FEATURE_FORMAT)
        self.assertEqual(len(root["features"]), 8)

    def test_each_mapping_parses_with_an_exact_field_contract(self) -> None:
        for feature in self.features:
            with self.subTest(feature=feature.type):
                mapping = controller_feature_mapping(feature)
                self.assertEqual(parse_controller_feature(mapping), feature)
                with self.assertRaisesRegex(ControllerFeatureError, "unknown"):
                    parse_controller_feature({**mapping, "rva": 0x123456})
                with self.assertRaisesRegex(ControllerFeatureError, "missing"):
                    missing = dict(mapping)
                    missing.pop(next(key for key in mapping if key != "type"))
                    parse_controller_feature(missing)

    def test_callback_is_a_bounded_gpl_symbol_not_code_path_or_dll(self) -> None:
        vigor = next(
            item
            for item in self.features
            if isinstance(item, StockAp24TimedRageAction)
        )
        for callback in (
            "plugin.dll",
            "C:/mod/plugin",
            "run();",
            "A" * 65,
        ):
            with self.subTest(callback=callback):
                with self.assertRaisesRegex(ControllerFeatureError, "callback_symbol"):
                    normalize_controller_features(
                        (replace(vigor, callback_symbol=callback),)
                    )

    def test_references_and_per_panel_controls_fail_closed(self) -> None:
        meter = next(
            item for item in self.features if isinstance(item, StockAp22ResourceMeter)
        )
        with self.assertRaisesRegex(ControllerFeatureError, "unknown panel_key"):
            normalize_controller_features((replace(meter, panel_key="missing"),))

        vigor = next(
            item
            for item in self.features
            if isinstance(item, StockAp24TimedRageAction)
        )
        with self.assertRaisesRegex(ControllerFeatureError, "unknown resource_key"):
            normalize_controller_features(
                tuple(
                    replace(item, resource_key="unknown")
                    if item is vigor
                    else item
                    for item in self.features
                )
            )

        with self.assertRaisesRegex(ControllerFeatureError, "claimed by both"):
            normalize_controller_features(
                tuple(
                    replace(item, action_control_id=meter.label_control_id)
                    if item is vigor
                    else item
                    for item in self.features
                )
            )

        gate = next(
            item
            for item in self.features
            if isinstance(item, StockAp17UpgradeResearchGate)
        )
        without_research = tuple(
            item for item in self.features if not isinstance(item, StockAp99ResearchRow)
        )
        self.assertIn(gate, without_research)
        with self.assertRaisesRegex(ControllerFeatureError, "unknown AP99"):
            normalize_controller_features(without_research)

    def test_private_ap99_keys_stay_outside_the_complete_stock_range(self) -> None:
        research = next(
            item
            for item in self.features
            if isinstance(item, StockAp99ResearchRow)
        )
        for action_control_id in (0x1388, 0x139C, 0x13EB):
            with self.subTest(action_control_id=action_control_id):
                with self.assertRaisesRegex(
                    ControllerFeatureError, "reserved stock AP99 control range"
                ):
                    normalize_controller_features(
                        tuple(
                            replace(item, action_control_id=action_control_id)
                            if item is research
                            else item
                            for item in self.features
                        )
                    )

        for action_control_id in (0x1387, 0x13EC):
            with self.subTest(boundary=action_control_id):
                normalize_controller_features(
                    tuple(
                        replace(item, action_control_id=action_control_id)
                        if item is research
                        else item
                        for item in self.features
                    )
                )

    def test_ap99_templates_use_only_the_complete_constructed_descriptor_set(self) -> None:
        research = next(
            item
            for item in self.features
            if isinstance(item, StockAp99ResearchRow)
        )
        proven_templates = (
            *range(0x1388, 0x138E),
            0x1392,
            *range(0x139C, 0x139E),
            *range(0x13A6, 0x13AC),
            *range(0x13B0, 0x13B4),
            0x13BA,
            *range(0x13C5, 0x13CB),
        )
        self.assertEqual(len(proven_templates), 26)
        for template in proven_templates:
            with self.subTest(template=template):
                normalize_controller_features(
                    tuple(
                        replace(
                            item,
                            descriptor_template_control_id=template,
                            completion_template_control_id=template,
                        )
                        if item is research
                        else item
                        for item in self.features
                    )
                )

        for field_name in (
            "descriptor_template_control_id",
            "completion_template_control_id",
        ):
            for template in (0x138E, 0x1393, 0x13EC, 0x1140):
                with self.subTest(field_name=field_name, template=template):
                    with self.assertRaisesRegex(
                        ControllerFeatureError, "26 proven stock AP99"
                    ):
                        normalize_controller_features(
                            tuple(
                                replace(item, **{field_name: template})
                                if item is research
                                else item
                                for item in self.features
                            )
                        )

        rage = next(
            item
            for item in self.features
            if isinstance(item, StockAp24RageCommandAction)
        )
        normalize_controller_features(
            tuple(
                replace(item, completion_template_research_control_id=0x13CA)
                if item is rage
                else item
                for item in self.features
            )
        )
        with self.assertRaisesRegex(ControllerFeatureError, "26 proven stock AP99"):
            normalize_controller_features(
                tuple(
                    replace(item, completion_template_research_control_id=0x13EC)
                    if item is rage
                    else item
                    for item in self.features
                )
            )

    def test_ap24_templates_must_match_proven_stock_metadata(self) -> None:
        timed = next(
            item
            for item in self.features
            if isinstance(item, StockAp24TimedRageAction)
        )
        for changes, error in (
            ({"descriptor_template_control_id": 0x1132}, "template pair"),
            ({"level_price_template_control_id": 0x1140}, "template pair"),
            ({"required_level": 2}, "required_level 3"),
            ({"gold_cost": 1499}, "gold_cost 1500"),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ControllerFeatureError, error):
                    normalize_controller_features(
                        tuple(
                            replace(item, **changes) if item is timed else item
                            for item in self.features
                        )
                    )

        rage = next(
            item
            for item in self.features
            if isinstance(item, StockAp24RageCommandAction)
        )
        with self.assertRaisesRegex(ControllerFeatureError, "proven stock visual"):
            normalize_controller_features(
                tuple(
                    replace(item, visual_template_control_id=0x1133)
                    if item is rage
                    else item
                    for item in self.features
                )
            )
        with self.assertRaisesRegex(ControllerFeatureError, "required_level 3"):
            normalize_controller_features(
                tuple(
                    replace(item, required_level=2) if item is rage else item
                    for item in self.features
                )
            )

    def test_ap69_templates_must_match_proven_stock_metadata(self) -> None:
        sovereign = next(
            item
            for item in self.features
            if isinstance(item, StockAp69SovereignTargetAction)
        )
        for changes, error in (
            ({"visual_template_control_id": 0x1132}, "proven stock visual"),
            ({"target_template_control_id": 0x1133}, "proven stock target"),
            ({"stock_target_mode": "Sp24"}, "stock_target_mode 'Sp23'"),
            ({"required_level": 2}, "required_level 3"),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ControllerFeatureError, error):
                    normalize_controller_features(
                        tuple(
                            replace(item, **changes) if item is sovereign else item
                            for item in self.features
                        )
                    )

    def test_multiple_panels_are_composable_without_uuid_or_mod_names(self) -> None:
        first = StockAp10Ap69SecondaryPanel(
            panel_key="alpha.panel",
            parent_building="alpha.building",
            source_dialog_id="PX01",
            building_family_id="AXA",
            open_command_id=0x4001,
        )
        second = StockAp10Ap69SecondaryPanel(
            panel_key="beta.panel",
            parent_building="beta.building",
            source_dialog_id="PX02",
            building_family_id="BXB",
            open_command_id=0x4001,
        )
        self.assertEqual(
            normalize_controller_features((second, first)),
            (first, second),
        )

        overlapping = replace(
            second,
            building_family_id="AA",
        )
        broad = replace(
            first,
            building_family_id="A",
        )
        with self.assertRaisesRegex(ControllerFeatureError, "prefixes overlap"):
            normalize_controller_features((broad, overlapping))

    def test_ap22_attribute_id_is_unique_across_the_registry(self) -> None:
        first_panel = StockAp10Ap69SecondaryPanel(
            panel_key="alpha.panel",
            parent_building="alpha.building",
            source_dialog_id="PX01",
            building_family_id="AXA",
            open_command_id=0x4001,
        )
        second_panel = StockAp10Ap69SecondaryPanel(
            panel_key="beta.panel",
            parent_building="beta.building",
            source_dialog_id="PX02",
            building_family_id="BXB",
            open_command_id=0x4002,
        )
        first_meter = StockAp22ResourceMeter(
            panel_key=first_panel.panel_key,
            resource_key="alpha.resource",
            attribute_id="PV01",
            label_control_id=0x5001,
            count_control_id=0x5002,
            binding_control_id=0x5003,
        )
        second_meter = StockAp22ResourceMeter(
            panel_key=second_panel.panel_key,
            resource_key="beta.resource",
            attribute_id="PV01",
            label_control_id=0x5101,
            count_control_id=0x5102,
            binding_control_id=0x5103,
        )
        with self.assertRaisesRegex(
            ControllerFeatureError, "duplicate AP22.*attribute_id"
        ):
            normalize_controller_features(
                (first_panel, first_meter, second_panel, second_meter)
            )

    def test_duplicate_dialog_and_parent_command_are_rejected(self) -> None:
        first = StockAp10Ap69SecondaryPanel(
            panel_key="first",
            parent_building="building",
            source_dialog_id="PX01",
            building_family_id="AAA",
            open_command_id=1,
        )
        duplicate_dialog = replace(
            first,
            panel_key="second",
            parent_building="other",
        )
        with self.assertRaisesRegex(ControllerFeatureError, "source dialog"):
            normalize_controller_features((first, duplicate_dialog))
        duplicate_command = replace(
            first,
            panel_key="second",
            source_dialog_id="PX02",
        )
        with self.assertRaisesRegex(ControllerFeatureError, "parent command"):
            normalize_controller_features((first, duplicate_command))

    def test_private_sovereign_modes_never_collide_with_stock_modes(self) -> None:
        stone = next(
            item
            for item in self.features
            if isinstance(item, StockAp69SovereignTargetAction)
        )
        with self.assertRaisesRegex(ControllerFeatureError, "reserved Sp"):
            normalize_controller_features(
                tuple(
                    replace(item, private_mode=item.stock_executor_mode)
                    if item is stone
                    else item
                    for item in self.features
                )
            )

        with self.assertRaisesRegex(ControllerFeatureError, "reserved Sp"):
            normalize_controller_features(
                tuple(
                    replace(item, private_mode="Sp37")
                    if item is stone
                    else item
                    for item in self.features
                )
            )

        with self.assertRaisesRegex(ControllerFeatureError, "only the traced Sp14"):
            normalize_controller_features(
                tuple(
                    replace(item, stock_executor_mode="Sp15")
                    if item is stone
                    else item
                    for item in self.features
                )
            )

    def test_decoder_rejects_noncanonical_duplicate_and_unknown_data(self) -> None:
        canonical = encode_controller_features(self.features)
        with self.assertRaisesRegex(ControllerFeatureError, "canonical"):
            decode_controller_features(canonical + b" ")

        root = json.loads(canonical.decode("utf-8"))
        root["features"][0]["dll"] = "unsafe.dll"
        payload = json.dumps(
            root, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        with self.assertRaisesRegex(ControllerFeatureError, "unknown"):
            decode_controller_features(payload)

        duplicate_key = b'{"format":"a","format":"b","version":1,"features":[]}'
        with self.assertRaisesRegex(ControllerFeatureError, "invalid JSON"):
            decode_controller_features(duplicate_key)

    def test_generic_reward_recipe_is_linked_bounded_and_order_independent(self) -> None:
        first = StockMx09Ap41RewardPanel(
            "first-panel", "first-building", "RA01", 5001
        )
        first_action = StockAp41Fl00HostileMonsterFlag(
            "first-panel", "capture", "RF01", "RF01", 38,
            "AZ0", "No room",
        )
        second = StockMx09Ap41RewardPanel(
            "second-panel", "second-building", "RB01", 5001
        )
        second_action = StockAp41Fl00HostileMonsterFlag(
            "second-panel", "bind", "RF02", "RF02", 40, None, None,
        )
        forward = normalize_controller_features(
            (first, first_action, second, second_action)
        )
        reverse = normalize_controller_features(
            (second_action, second, first_action, first)
        )
        self.assertEqual(forward, reverse)

        with self.assertRaisesRegex(ControllerFeatureError, "both be null"):
            normalize_controller_features((
                first,
                replace(first_action, unavailable_alert_text=None),
            ))
        with self.assertRaisesRegex(ControllerFeatureError, "same Overlay"):
            normalize_controller_features((
                first,
                replace(first_action, private_flag_id="RF03"),
            ))
        with self.assertRaisesRegex(ControllerFeatureError, "cursor ordinal"):
            normalize_controller_features((
                first, first_action, second,
                replace(second_action, cursor_ordinal=38),
            ))


if __name__ == "__main__":
    unittest.main()
