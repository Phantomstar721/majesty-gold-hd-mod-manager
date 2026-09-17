from dataclasses import replace
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.runtime_features import (
    MapFogQueryFeature, encode_runtime_feature_registry, decode_runtime_feature_registry,
    derive_feature_runtime_capabilities, normalize_runtime_features,
)
from majesty_cam.package import (
    ModDefinition, CustomBuildingDefinition, mod_definition_mapping, parse_mod_definition,
)
from majesty_cam.manager.build import _canonical_mod_definition
from majesty_cam.stock_controller_features import (
    StockMx05DataRecordListPanel, parse_controller_feature, controller_feature_mapping,
    ControllerFeatureError,
)
from majesty_cam.stock_controller_registry import (
    LiveAgentListTextIds, resolve_stock_controller_registry,
    encode_stock_controller_registry, decode_stock_controller_registry,
    ControllerRegistryError,
)


class DataRecordInterfaces(unittest.TestCase):
    def feature(self):
        return StockMx05DataRecordListPanel(
            "notices", "library", "PN01", 0x4101, "Count", "Key", "Revision",
            "Destination", "Read the notice", None, None, "Cost", "Refresh")

    def test_public_schema_uses_keys_not_agents(self):
        value = controller_feature_mapping(self.feature())
        self.assertEqual(value["row_key_callback_symbol"], "Key")
        self.assertNotIn("row_agent_id_callback_symbol", value)
        self.assertEqual(parse_controller_feature(value), self.feature())
        for field in ("stay_on_panel_after_action", "focus_selected_row_on_click", "action_agent_scope"):
            value.pop(field)
        self.assertEqual(parse_controller_feature(value), self.feature())

    def test_map_queries_and_record_rows_share_validation_and_fingerprint_mapping(self):
        definition = ModDefinition(
            3, "00000000-0000-4000-8000-000000000001", "Notices", "Notices",
            (CustomBuildingDefinition("library", None, "AP08", "AP08"),),
            runtime_features=(MapFogQueryFeature(), self.feature()),
        )
        value = mod_definition_mapping(definition)
        self.assertEqual(parse_mod_definition(value), definition)
        self.assertEqual(_canonical_mod_definition(definition), value)
        self.assertEqual(value["runtime_features"][0], {"type": "stock.map-fog-query.v1"})
        self.assertEqual(value["runtime_features"][1]["row_key_callback_symbol"], "Key")

    def test_records_never_request_unit_focus_or_unit_actions(self):
        for changes in ({"focus_selected_row_on_click": True},
                        {"action_agent_scope": "selected-row"},
                        {"stay_on_panel_after_action": False}, {"row_title_text": None}):
            with self.assertRaises(ControllerFeatureError):
                controller_feature_mapping(replace(self.feature(), **changes))

    def test_native_record_kind_roundtrip_and_malformed_flags(self):
        registry = resolve_stock_controller_registry(
            (self.feature(),), {"notices": (0x31305050, 0x32305050)},
            occupant_parent_bases={"notices": "AP08"},
            list_text_ids={"notices": LiveAgentListTextIds(0x60000001, 0x60000002, 0)})
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(struct.unpack_from("<I", payload, 4)[0], 16)
        self.assertTrue(registry.live_agent_lists[0].data_record_rows)
        self.assertEqual(decode_stock_controller_registry(payload), registry)
        with self.assertRaises(ControllerRegistryError):
            decode_stock_controller_registry(payload[:-4] + struct.pack("<I", 2))

    def test_map_queries_are_explicit_shared_read_only_capability(self):
        registry = normalize_runtime_features((MapFogQueryFeature(), MapFogQueryFeature()))
        self.assertTrue(registry.map_fog_query)
        self.assertEqual(len(registry.features), 1)
        payload = encode_runtime_feature_registry(registry)
        self.assertEqual(payload, struct.pack("<4s4I", b"MMFR", 2, 0, 0, 1))
        self.assertEqual(decode_runtime_feature_registry(payload), registry)
        self.assertIn("stock.map-fog-query.v1", derive_feature_runtime_capabilities((), registry))
        self.assertNotIn("stock.map-fog-query.v1", derive_feature_runtime_capabilities(
            ("stock.map-fog-query.v1",), normalize_runtime_features()))
        for broken in (payload[:-1], payload[:-4]+struct.pack("<I",4)):
            with self.assertRaises(ValueError):
                decode_runtime_feature_registry(broken)
