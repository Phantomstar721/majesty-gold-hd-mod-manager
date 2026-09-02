from dataclasses import replace
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.compose import (
    ComposeError, _require_occupant_callback_signature,
    _validate_controller_panel_controls, resolve_controller_registry,
)
from majesty_cam.stock_controller_features import (
    ControllerFeatureError, StockMx04Mx05OccupantActionPanel,
    normalize_controller_features, parse_controller_feature, controller_feature_mapping,
    legacy_alchemist_controller_features,
)
from majesty_cam.stock_controller_registry import (
    ControllerRegistryError, encode_stock_controller_registry,
    decode_stock_controller_registry, resolve_stock_controller_registry,
)
from test_compose import _v3_controller_inventory, _panel_pair, _smnu_payload


CONTROLS = (0x1388, 0x138B, 0x1F46, 0x1F45, 0x1F4D, 0x1392, 0x1F41, 0x1F40)


def feature(key="visitors", parent="Stable", source="P001", symbol="Stable"):
    return StockMx04Mx05OccupantActionPanel(
        key, parent, source, 0x4101, symbol + "_Cost", symbol + "_Action"
    )


class OccupantPanelTests(unittest.TestCase):
    def test_schema_is_generic_and_rejects_unknown_fields(self):
        item = feature()
        self.assertEqual(parse_controller_feature(controller_feature_mapping(item)), item)
        bad = controller_feature_mapping(item)
        bad["dll"] = "unsafe.dll"
        with self.assertRaises(ControllerFeatureError):
            parse_controller_feature(bad)

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

    def test_parent_classes_and_parent_child_aliasing(self):
        for base in ("AP07", "AP10", "MX09"):
            r = resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303050)},
                occupant_parent_bases={"visitors": base})
            self.assertEqual(decode_stock_controller_registry(encode_stock_controller_registry(r)).occupant_action_panels[0].parent_controller_base, base)
        with self.assertRaisesRegex(ControllerRegistryError, "collides with a parent"):
            resolve_stock_controller_registry((feature(),), {"visitors": (0x31303042, 0x31303042)})

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
