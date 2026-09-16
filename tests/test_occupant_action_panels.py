from dataclasses import replace
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.compose import (
    ComposeError, _require_occupant_callback_signature,
    _require_live_agent_list_callback_signature,
    _validate_mx05_live_agent_list_panel, _split_smnu_records,
    _validate_controller_panel_controls, resolve_controller_registry,
)
from majesty_cam.cam import CamEntry
from majesty_cam.strt import StrtRecord, StrtTable
from majesty_cam.stock_controller_features import (
    ControllerFeatureError, LiveAgentListRowVariant,
    StockMx05LiveAgentListPanel,
    StockMx04Mx05OccupantActionPanel,
    normalize_controller_features, parse_controller_feature, controller_feature_mapping,
    legacy_alchemist_controller_features,
)
from majesty_cam.stock_controller_registry import (
    ControllerRegistryError, encode_stock_controller_registry,
    LiveAgentListTextIds, decode_stock_controller_registry,
    resolve_stock_controller_registry,
)
from test_compose import _v3_controller_inventory, _panel_pair, _smnu_payload


CONTROLS = (
    0x1388, 0x138B, 0x138C, 0x1392, 0x1F40,
    0x1F41, 0x1F45, 0x1F46, 0x1F4D,
)


def quest_feature():
    return StockMx05LiveAgentListPanel(
        panel_key="quests",
        parent_building="AdventurerGuild",
        source_dialog_id="QB01",
        open_command_id=0x7101,
        row_count_callback_symbol="Quest_Count",
        row_agent_id_callback_symbol="Quest_Agent_Id",
        revision_callback_symbol="Quest_Revision",
        row_title_text=None,
        row_text="Deliver orders",
        row_value_callback_symbol="Quest_Reward",
        row_value_suffix_text=" Gold",
        action_cost_callback_symbol="Quest_RefreshCost",
        action_callback_symbol="Quest_Refresh",
    )


def feature(key="visitors", parent="Stable", source="P001", symbol="Stable"):
    return StockMx04Mx05OccupantActionPanel(
        key, parent, source, 0x4101, symbol + "_Cost", symbol + "_Action"
    )


class OccupantPanelTests(unittest.TestCase):
    def test_live_agent_list_requires_exact_stock_mx05_action_row(self):
        def record(size, rectangle, control_offset, control_id):
            value = bytearray(size)
            struct.pack_into("<4I", value, 8, *rectangle)
            struct.pack_into("<I", value, control_offset, control_id)
            value[-4:] = b"\xff" * 4
            return bytes(value)

        action = bytearray(record(0xAC, (51, 219, 103, 21), 0x88, 0x138B))
        struct.pack_into("<2I", action, 0x2C, 0, 0)
        records = [
            record(0x90, (10, 55, 164, 160), 0x5C, 0x1388),
            bytes(action),
            record(0x74, (33, 219, 16, 17), 0x64, 0x138C),
            record(0x54, (174, 51, 25, 167), 0x4C, 0x1392),
            record(0xA8, (115, 222, 39, 16), 0x7C, 0x1F46),
            b"\xff" * 4,
        ]
        source = b"".join(records)
        stock_entry = CamEntry(name=b"MX05" + b"\0" * 16, data=source)
        labels = StrtTable(
            version=b"\x01\x00",
            records=(StrtRecord(string_id=0, text=b"REFRESH"),),
        ).to_bytes()
        with patch("majesty_cam.compose._require_cam_entry", return_value=stock_entry):
            _validate_mx05_live_agent_list_panel(
                Path("."), source, labels,
                owner="test", label="QB01",
            )

        moved = list(records)
        moved_list = bytearray(moved[0])
        struct.pack_into("<4I", moved_list, 8, 10, 55, 164, 135)
        moved[0] = bytes(moved_list)
        with patch("majesty_cam.compose._require_cam_entry", return_value=stock_entry):
            with self.assertRaisesRegex(ComposeError, "exact stock MX05"):
                _validate_mx05_live_agent_list_panel(
                    Path("."), b"".join(moved), labels,
                    owner="test", label="QB01",
                )

        duplicate = source[:-4] + struct.pack(
            "<III", 0x7102, 0xFFFFFFFF, 0xFFFFFFFF
        )
        with patch("majesty_cam.compose._require_cam_entry", return_value=stock_entry):
            with self.assertRaisesRegex(ComposeError, "exact record count"):
                _validate_mx05_live_agent_list_panel(
                    Path("."), duplicate, labels,
                    owner="test", label="QB01",
                )

    def test_schema_is_generic_and_rejects_unknown_fields(self):
        item = feature()
        self.assertEqual(parse_controller_feature(controller_feature_mapping(item)), item)
        opted_in = replace(
            quest_feature(),
            stay_on_panel_after_action=True,
            focus_selected_row_on_click=False,
        )
        self.assertEqual(
            parse_controller_feature(controller_feature_mapping(opted_in)),
            opted_in,
        )
        invalid_policy = controller_feature_mapping(quest_feature())
        invalid_policy["stay_on_panel_after_action"] = 1
        with self.assertRaisesRegex(ControllerFeatureError, "true or false"):
            parse_controller_feature(invalid_policy)
        invalid_focus_policy = controller_feature_mapping(quest_feature())
        invalid_focus_policy["focus_selected_row_on_click"] = 1
        with self.assertRaisesRegex(ControllerFeatureError, "true or false"):
            parse_controller_feature(invalid_focus_policy)
        bad = controller_feature_mapping(item)
        bad["dll"] = "unsafe.dll"
        with self.assertRaises(ControllerFeatureError):
            parse_controller_feature(bad)

    def test_live_agent_list_value_is_optional_but_paired(self):
        without_value = replace(
            quest_feature(),
            row_value_callback_symbol=None,
            row_value_suffix_text=None,
        )
        self.assertEqual(
            normalize_controller_features((without_value,)),
            (without_value,),
        )
        with self.assertRaisesRegex(ControllerFeatureError, "both be present"):
            normalize_controller_features((replace(
                without_value,
                row_value_callback_symbol="Quest_Reward",
            ),))
        with self.assertRaisesRegex(ControllerFeatureError, "customize at least"):
            normalize_controller_features((replace(
                without_value,
                row_title_text=None,
                row_text=None,
            ),))

    def test_live_agent_list_variants_are_bounded_static_presentation(self):
        variants = (
            LiveAgentListRowVariant("Delivery", "Deliver goods"),
            LiveAgentListRowVariant("Escort", "Protect a traveler"),
        )
        item = replace(
            quest_feature(),
            row_text=None,
            row_variant_callback_symbol="Quest_Variant",
            row_variants=variants,
        )
        self.assertEqual(
            parse_controller_feature(controller_feature_mapping(item)), item
        )
        with self.assertRaisesRegex(ControllerFeatureError, "both be present"):
            normalize_controller_features((replace(
                item, row_variant_callback_symbol=None,
            ),))
        with self.assertRaisesRegex(ControllerFeatureError, "must be null"):
            normalize_controller_features((replace(
                item, row_text="ambiguous fallback",
            ),))
        with self.assertRaisesRegex(ControllerFeatureError, "title_text or row_text"):
            normalize_controller_features((replace(
                item,
                row_variants=(LiveAgentListRowVariant(None, None),),
            ),))
        with self.assertRaisesRegex(ControllerFeatureError, "64-variant"):
            normalize_controller_features((replace(
                item, row_variants=variants * 33,
            ),))

    def test_v3_round_trip_and_order_independence(self):
        items = (feature(), feature("animals", "Menagerie", "P002", "Menagerie"))
        mapping = {p.panel_key: (int.from_bytes(b"B001", "little"),
                                  int.from_bytes(p.source_dialog_id.encode(), "little")) for p in items}
        # Same parent can expose multiple independent action panels, but not
        # claim the same opener twice.
        mapping["animals"] = (int.from_bytes(b"B002", "little"), int.from_bytes(b"P002", "little"))
        forward = resolve_stock_controller_registry(items, mapping)
        reverse = resolve_stock_controller_registry(reversed(items), mapping)
        encoded = encode_stock_controller_registry(forward)
        self.assertEqual(struct.unpack_from("<I", encoded, 4)[0], 3)
        self.assertEqual(encoded, encode_stock_controller_registry(reverse))
        self.assertEqual(forward, decode_stock_controller_registry(encoded))
        self.assertEqual([p.action_command_id for p in forward.occupant_action_panels], [0x10000, 0x10001])
        self.assertFalse(decode_stock_controller_registry(encode_stock_controller_registry(
            resolve_stock_controller_registry((), {}))).occupant_action_panels)

    def test_rejects_callback_and_parent_command_collisions(self):
        with self.assertRaisesRegex(ControllerFeatureError, "callback"):
            normalize_controller_features((feature(), feature("other", "Other", "P002")))
        with self.assertRaisesRegex(ControllerFeatureError, "same parent command"):
            normalize_controller_features((feature(), feature("other", "Stable", "P002", "Other")))

    def test_v2_legacy_bytes_remain_v2_and_new_panel_coexists(self):
        legacy = legacy_alchemist_controller_features("AlchemistsLaboratory")
        mapping = {"brewing": (int.from_bytes(b"B001", "little"), int.from_bytes(b"P002", "little"))}
        old = encode_stock_controller_registry(resolve_stock_controller_registry(legacy, mapping))
        self.assertEqual(struct.unpack_from("<I", old, 4)[0], 2)
        mapping["visitors"] = (int.from_bytes(b"B001", "little"), int.from_bytes(b"P001", "little"))
        merged = resolve_stock_controller_registry((*legacy, feature()), mapping)
        self.assertEqual(merged, decode_stock_controller_registry(encode_stock_controller_registry(merged)))

    def test_unassigned_transaction_and_truncated_wire_rejected(self):
        r = resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303050)})
        with self.assertRaisesRegex(ControllerRegistryError, "manager-allocated"):
            encode_stock_controller_registry(replace(r, occupant_action_panels=(
                replace(r.occupant_action_panels[0], action_command_id=21),)))
        data = encode_stock_controller_registry(r)
        for index in range(len(data)):
            with self.assertRaises(ControllerRegistryError):
                decode_stock_controller_registry(data[:index])

    def test_callback_signatures_and_comments(self):
        _require_occupant_callback_signature("Function Price(agent a) // comment\n is integer\ndeclare\nbegin return 1; end", "Price", True)
        _require_occupant_callback_signature("Function Act(agent a) begin end", "Act", False)
        for text, symbol, cost in (("Function Price(integer a) is integer begin end", "Price", True),
                                   ("Function Price(agent a, agent b) is integer begin end", "Price", True),
                                   ("Function Price(agent a) begin end", "Price", True),
                                   ("Function Act(agent a) is integer begin end", "Act", False)):
            with self.assertRaises(ComposeError):
                _require_occupant_callback_signature(text, symbol, cost)

    def test_live_agent_list_callback_signatures(self):
        _require_live_agent_list_callback_signature(
            "Function OfferReward(agent g, integer row) is integer begin return 500; end",
            "OfferReward", ("agent", "integer"), "integer",
        )
        _require_live_agent_list_callback_signature(
            "Function OfferCount(agent g) is integer begin return 1; end",
            "OfferCount", ("agent",), "integer",
        )
        _require_live_agent_list_callback_signature(
            "Function CanRefresh(agent g) is integer begin return 0; end",
            "CanRefresh", ("agent",), "integer",
        )
        for text in (
            "Function OfferReward(agent g) is integer begin return 1; end",
            "Function OfferReward(agent g, integer row) is string begin return \"bad\"; end",
        ):
            with self.assertRaises(ComposeError):
                _require_live_agent_list_callback_signature(
                    text,
                    "OfferReward", ("agent", "integer"), "integer",
                )

    def test_parent_classes_and_parent_child_aliasing(self):
        for base in (
            "AP01", "AP07", "AP08", "AP10", "AP31", "APa9",
            "MX00", "MX09", "MX22",
        ):
            r = resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303050)},
                occupant_parent_bases={"visitors": base})
            self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(r)).occupant_action_panels[0].parent_controller_base, base)
            live = resolve_stock_controller_registry(
                (quest_feature(),),
                {"quests": (0x31303042, 0x31303050)},
                occupant_parent_bases={"quests": base},
                list_text_ids={"quests": LiveAgentListTextIds(
                    0, 0x68000001, 0x68000002
                )},
            )
            self.assertEqual(
                decode_stock_controller_registry(
                    encode_stock_controller_registry(live)
                ).live_agent_lists[0].parent_controller_base,
                base,
            )
        with self.assertRaisesRegex(ControllerRegistryError, "collides with a parent"):
            resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303042)})

    def test_ap08_parent_uses_unchanged_occupant_action_recipe(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="Dispatch",
                mod_id="{00000000-0000-0000-0000-000000000008}",
                local_name="AdventurerGuild",
                building_source=b"AG01",
                family="AG",
            )
            panel = feature(
                key="dispatch",
                parent="AdventurerGuild",
                source="DP01",
                symbol="Dispatch",
            )
            definition = inventory.selected.package.definition
            parent = replace(
                definition.custom_buildings[0],
                controller_base="AP08",
                panel_resource_template="AP08",
            )
            inventory.selected.package.definition = replace(
                definition,
                custom_buildings=(parent,),
                runtime_features=(panel,),
            )
            inventory.resources = (
                *_panel_pair("Dispatch", b"AG01", (panel.open_command_id,)),
                *_panel_pair("Dispatch", b"DP01", CONTROLS),
            )
            callback_source = root / "dispatch.gpl"
            callback_source.write_text(
                "Function Dispatch_Cost(agent selected) is integer begin return 0; end\n"
                "Function Dispatch_Action(agent selected) begin end\n",
                encoding="cp1252",
            )
            from types import SimpleNamespace
            inventory.gpl_loads = (
                SimpleNamespace(
                    sources=(SimpleNamespace(absolute_path=callback_source),)
                ),
            )

            resolved = resolve_controller_registry((inventory,)).registry
            self.assertEqual(
                resolved.occupant_action_panels[0].parent_controller_base,
                "AP08",
            )
            self.assertFalse(resolved.live_agent_lists)

            inventory.selected.package.definition = replace(
                inventory.selected.package.definition,
                custom_buildings=(
                    replace(parent, panel_resource_template="AP10"),
                ),
            )
            with self.assertRaisesRegex(
                ComposeError, "cataloged stock primary-building controller"
            ):
                resolve_controller_registry((inventory,))

    def test_required_controls_rejected_before_launch(self):
        registry = resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303050)})
        for missing in (None, *CONTROLS):
            args = (registry, "visitors", _smnu_payload(0x4101),
                    _smnu_payload(*(c for c in CONTROLS if c != missing)))
            kwargs = dict(owner="test", parent_label="B001", child_label="P001")
            if missing is None:
                _validate_controller_panel_controls(*args, **kwargs)
            else:
                with self.assertRaises(ComposeError):
                    _validate_controller_panel_controls(*args, **kwargs)

    def test_live_agent_list_requires_literal_mx05_records_not_constructor_ids(self):
        board = quest_feature()
        registry = resolve_stock_controller_registry(
            (board,),
            {"quests": (int.from_bytes(b"AG01", "little"),
                         int.from_bytes(b"QB01", "little"))},
            occupant_parent_bases={"quests": "AP08"},
            list_text_ids={"quests": LiveAgentListTextIds(
                0, 0x68000001, 0x68000002
            )},
        )
        parent = _smnu_payload(board.open_command_id)
        child = _smnu_payload(*CONTROLS)
        resolved = registry.live_agent_lists[0]
        self.assertEqual(resolved.action_command_id, 0x20000)

        # These IDs are referenced or constructed by MX05 code but are not
        # literal records in stock SMNU/MX05.  Their absence must not make an
        # exact stock-resource clone fail preflight.
        for constructor_id in (
            0x138D, 0x138E, 0x138F, 0x1F44, 0x1F4B, 0x1F4E,
        ):
            self.assertNotIn(struct.pack("<I", constructor_id), child)

        args = (
            registry,
            "quests",
            parent,
            child,
        )
        kwargs = dict(owner="test", parent_label="AG01", child_label="QB01")
        _validate_controller_panel_controls(*args, **kwargs)

        for missing in CONTROLS:
            reduced = _smnu_payload(
                *(control for control in CONTROLS if control != missing),
            )
            with self.assertRaisesRegex(ComposeError, "MX05 stock control"):
                _validate_controller_panel_controls(
                    registry,
                    "quests",
                    parent,
                    reduced,
                    **kwargs,
                )

        with self.assertRaisesRegex(ComposeError, "SMNU/AG01"):
            _validate_controller_panel_controls(
                registry,
                "quests",
                _smnu_payload(),
                child,
                **kwargs,
            )

    def test_live_agent_list_composition_allocates_optional_private_text(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="Dispatch",
                mod_id="{00000000-0000-0000-0000-000000000008}",
                local_name="AdventurerGuild",
                building_source=b"AG01",
                family="AG",
            )
            board = quest_feature()
            definition = inventory.selected.package.definition
            inventory.selected.package.definition = replace(
                definition,
                custom_buildings=(replace(
                    definition.custom_buildings[0],
                    controller_base="AP08",
                    panel_resource_template="AP08",
                ),),
                runtime_features=(board,),
            )
            inventory.resources = (
                *_panel_pair("Dispatch", b"AG01", (board.open_command_id,)),
                *_panel_pair("Dispatch", b"QB01", CONTROLS),
            )
            callback_source = root / "dispatch.gpl"
            callback_source.write_text(
                "Function Quest_Count(agent g) is integer begin return 3; end\n"
                "Function Quest_Agent_Id(agent g, integer row) is integer begin return 123; end\n"
                "Function Quest_Revision(agent g) is integer begin return 1; end\n"
                "Function Quest_Reward(agent g, integer row) is integer begin return 100; end\n"
                "Function Quest_RefreshCost(agent g) is integer begin return 25; end\n"
                "Function Quest_Refresh(agent g) is boolean begin return TRUE; end\n",
                encoding="cp1252",
            )
            from types import SimpleNamespace
            inventory.gpl_loads = (
                SimpleNamespace(sources=(
                    SimpleNamespace(absolute_path=callback_source),
                )),
            )

            result = resolve_controller_registry((inventory,))
            resolved = result.registry.live_agent_lists[0]
            self.assertEqual(len(result.private_texts), 2)
            by_id = {item.runtime_id: item.text for item in result.private_texts}
            self.assertEqual(resolved.row_title_intent_id, 0)
            self.assertEqual(by_id[resolved.row_text_intent_id], b"Deliver orders")
            self.assertEqual(by_id[resolved.row_value_suffix_intent_id], b" Gold")
            self.assertTrue(0x68000000 <= resolved.row_text_intent_id < 0x70000000)

    def test_live_agent_list_composition_allocates_variant_private_text(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _v3_controller_inventory(
                root,
                alias="Dispatch",
                mod_id="{00000000-0000-0000-0000-000000000009}",
                local_name="OrderHall",
                building_source=b"OH01",
                family="OH",
            )
            board = replace(
                quest_feature(),
                parent_building="OrderHall",
                source_dialog_id="VL01",
                row_text=None,
                row_variant_callback_symbol="Quest_Variant",
                row_variants=(
                    LiveAgentListRowVariant("Delivery", "Deliver goods"),
                    LiveAgentListRowVariant(None, "Protect a traveler"),
                ),
            )
            definition = inventory.selected.package.definition
            inventory.selected.package.definition = replace(
                definition,
                custom_buildings=(replace(
                    definition.custom_buildings[0],
                    controller_base="AP08",
                    panel_resource_template="AP08",
                ),),
                runtime_features=(board,),
            )
            inventory.resources = (
                *_panel_pair("Dispatch", b"OH01", (board.open_command_id,)),
                *_panel_pair("Dispatch", b"VL01", CONTROLS),
            )
            callback_source = root / "dispatch-variants.gpl"
            callback_source.write_text(
                "Function Quest_Count(agent g) is integer begin return 3; end\n"
                "Function Quest_Agent_Id(agent g, integer row) is integer begin return 123; end\n"
                "Function Quest_Revision(agent g) is integer begin return 1; end\n"
                "Function Quest_Variant(agent g, integer row) is integer begin return row; end\n"
                "Function Quest_Reward(agent g, integer row) is integer begin return 100; end\n"
                "Function Quest_RefreshCost(agent g) is integer begin return 25; end\n"
                "Function Quest_Refresh(agent g) is boolean begin return TRUE; end\n",
                encoding="cp1252",
            )
            from types import SimpleNamespace
            inventory.gpl_loads = (
                SimpleNamespace(sources=(
                    SimpleNamespace(absolute_path=callback_source),
                )),
            )

            result = resolve_controller_registry((inventory,))
            resolved = result.registry.live_agent_lists[0]
            by_id = {item.runtime_id: item.text for item in result.private_texts}

            self.assertEqual(len(result.private_texts), 4)
            self.assertEqual(resolved.row_variant_callback_symbol, "Quest_Variant")
            self.assertEqual(len(resolved.row_variants), 2)
            first, second = resolved.row_variants
            self.assertEqual(by_id[first.row_title_intent_id], b"Delivery")
            self.assertEqual(by_id[first.row_text_intent_id], b"Deliver goods")
            self.assertEqual(second.row_title_intent_id, 0)
            self.assertEqual(by_id[second.row_text_intent_id], b"Protect a traveler")
            self.assertEqual(by_id[resolved.row_value_suffix_intent_id], b" Gold")

    def test_two_unrelated_packages_compose_remove_and_reverse(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventories = []
            for i, name in enumerate(("Stable", "Clinic"), 1):
                inv = _v3_controller_inventory(root, alias=name, mod_id=f"{{00000000-0000-0000-0000-{i:012d}}}",
                                               local_name=name, building_source=f"B00{i}".encode(), family=f"Y{i}")
                f = feature(parent=name, symbol=name)
                inv.selected.package.definition = replace(inv.selected.package.definition, runtime_features=(f,))
                inv.resources = (*_panel_pair(name, f"B00{i}".encode(), (0x4101,)), *_panel_pair(name, b"P001", CONTROLS))
                source = root / f"{name}.gpl"
                source.write_text(f"Function {name}_Cost(agent a) is integer begin return 5; end\nFunction {name}_Action(agent a) begin end", encoding="utf-8")
                from types import SimpleNamespace
                inv.gpl_loads = (SimpleNamespace(sources=(SimpleNamespace(absolute_path=source),)),)
                inventories.append(inv)
            a = resolve_controller_registry(inventories)
            b = resolve_controller_registry(tuple(reversed(inventories)))
            self.assertEqual(encode_stock_controller_registry(a.registry), encode_stock_controller_registry(b.registry))
            self.assertEqual(len(a.registry.occupant_action_panels), 2)
            one = resolve_controller_registry(inventories[:1])
            self.assertEqual(len(one.registry.occupant_action_panels), 1)
            self.assertNotIn(b"Clinic", encode_stock_controller_registry(one.registry))


if __name__ == "__main__":
    unittest.main()
