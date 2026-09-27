"""Source-only purchase continuations; never prepares a game profile."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam import compose
from majesty_cam.gpl import (SemanticMergeResult, parse_gpl,
    add_purchase_bazaar_tail_callbacks, add_purchase_equipment_tail_callbacks)
from majesty_cam.gpl_function_merge import _Parser, _tokens
from majesty_cam.standard_scripts import Providers
from test_standard_scripts import provider


BAZAAR = '''Function Purchase_Bazaar (agent Hero, integer Chance) is boolean
Declare
Begin
    If ($IsExpansion(Hero) == FALSE)
        return FALSE;
    return $Private_Shopping(Hero, Chance);
End
'''
HELPER = '''Function Private_Shopping (agent Hero, integer Chance) is boolean
Declare
Begin
    If (Chance <= $RandomNumber(100) + 1)
        return FALSE;
    Hero's "ActiveScript" = $Use_Building;
    return TRUE;
End
'''


def callback(name="Extra_Visit"):
    return f"Function {name}(agent Customer) is boolean\nDeclare\nBegin\nreturn FALSE;\nEnd\n"


def merged(text):
    return SemanticMergeResult(parse_gpl(text).items, ())


class PurchaseCallbackTests(unittest.TestCase):
    def bazaar(self, text=BAZAAR + HELPER, **kwargs):
        return add_purchase_bazaar_tail_callbacks(merged(text + callback()),
                                                 ("Extra_Visit",), **kwargs)

    def test_delegated_body_and_helpers_are_preserved_exactly(self):
        parsed = parse_gpl(self.bazaar().emit_project_source_set().gpl_text)
        private = parsed.require("function", "CAM_Purchase_Bazaar_BeforeTail")
        self.assertEqual(private.text.replace("CAM_Purchase_Bazaar_BeforeTail", "Purchase_Bazaar", 1), BAZAAR)
        self.assertEqual(parsed.require("function", "Private_Shopping").text, HELPER)
        wrapper = parsed.require("function", "Purchase_Bazaar")
        self.assertEqual(_tokens(wrapper.text), _tokens('''
            Function Purchase_Bazaar(agent Hero, integer Chance) is boolean
            Declare
            Begin
                If ($CAM_Purchase_Bazaar_BeforeTail(Hero, Chance))
                    return TRUE;
                If ($Extra_Visit(Hero))
                    begin
                        Hero's "ActiveScript" = $Use_Building;
                        return TRUE;
                    end
                return FALSE;
            End
        '''))

    def test_equipment_uses_same_boolean_boundary_without_stock_internals(self):
        selected = "Function Purchase_Equipment(agent Buyer) is boolean\nBegin\nreturn $Custom_Shop(Buyer);\nEnd\n"
        result = add_purchase_equipment_tail_callbacks(merged(selected + callback()), ("Extra_Visit",))
        parsed = parse_gpl(result.emit_project_source_set().gpl_text)
        private = parsed.require("function", "CAM_Purchase_Equipment_BeforeTail")
        self.assertEqual(private.text.replace("CAM_Purchase_Equipment_BeforeTail", "Purchase_Equipment", 1), selected)
        self.assertIn("$Extra_Visit (Buyer)", parsed.require("function", "Purchase_Equipment").text)

    def test_callback_order_and_single_handoff_on_every_return_path(self):
        result = add_purchase_bazaar_tail_callbacks(merged(BAZAAR + callback("First") + callback("Second")),
                                                   ("First", "Second"))
        wrapper = next(i for i in result.items if i.name == "Purchase_Bazaar")
        _, _, body = _Parser(wrapper.text).function()
        self.assertEqual(len(body), 4)
        self.assertEqual(body[0].body[0].head, ("return", "true", ";"))
        for node, symbol in zip(body[1:3], ("$first", "$second")):
            self.assertEqual(node.head, ("if", "(", symbol, "(", "hero", ")", ")"))
            self.assertEqual(tuple(n.head for n in node.body), (
                ("hero", "'s", '"ActiveScript"', "=", "$use_building", ";"),
                ("return", "true", ";")))
        self.assertEqual(body[-1].head, ("return", "false", ";"))

    def test_empty_callbacks_are_identity_and_generate_nothing(self):
        original = merged(BAZAAR)
        self.assertIs(add_purchase_bazaar_tail_callbacks(original, ()), original)
        self.assertIs(add_purchase_equipment_tail_callbacks(original, ()), original)

    def test_private_symbol_collisions_include_native_and_prototypes(self):
        for extra, reserved in ((callback("CAM_Purchase_Bazaar_BeforeTail"), ()),
                                ("Prototype CAM_Purchase_Bazaar_BeforeTail\nEnd\n", ()),
                                ("", ("cam_purchase_bazaar_beforetail",))):
            with self.subTest(extra=extra, reserved=reserved), self.assertRaisesRegex(ValueError, "symbol collides"):
                self.bazaar(BAZAAR + extra, reserved_function_names=reserved)

    def test_self_calls_and_function_identity_fail_closed(self):
        for statement in ("return $Purchase_Bazaar(Hero, Chance);",
                          'Hero\'s "ActiveScript" = $Purchase_Bazaar;\nreturn FALSE;'):
            source = "Function Purchase_Bazaar(agent Hero, integer Chance) is boolean\nBegin\n" + statement + "\nEnd\n"
            with self.subTest(statement=statement), self.assertRaisesRegex(ValueError, "own function identity"):
                self.bazaar(source)

    def test_comments_strings_and_helper_prefix_are_not_self_references(self):
        source = BAZAAR.replace("Begin", 'Begin\n// $Purchase_Bazaar(Hero, Chance)\n$DebugOut("$Purchase_Bazaar");', 1)
        source = source.replace("$Private_Shopping", "$Purchase_Bazaar_Extension")
        result = self.bazaar(source)
        private = next(i for i in result.items if i.name == "CAM_Purchase_Bazaar_BeforeTail")
        self.assertEqual(private.text.replace("CAM_Purchase_Bazaar_BeforeTail", "Purchase_Bazaar", 1), source)

    def test_wrong_callback_signatures_or_missing_callback_rejected(self):
        for bad in (callback().replace("agent Customer", "integer Customer"),
                    callback().replace("is boolean", "is integer"), ""):
            with self.subTest(callback=bad), self.assertRaises(ValueError):
                add_purchase_bazaar_tail_callbacks(merged(BAZAAR + bad), ("Extra_Visit",))

    def test_bad_duplicate_or_recursive_callback_symbols_rejected(self):
        for symbols in (("Bad symbol",), ("Extra_Visit", "extra_visit"), ("Purchase_Bazaar",)):
            with self.subTest(symbols=symbols), self.assertRaises(ValueError):
                add_purchase_bazaar_tail_callbacks(merged(BAZAAR + callback()), symbols)

    def test_native_body_reconciliation_and_generated_tail_in_both_scopes(self):
        stock = parse_gpl(BAZAAR.replace("return $Private_Shopping(Hero, Chance);", "return FALSE;"))
        for scope in ("majesty", "majestyexpansion"):
            with self.subTest(scope=scope), patch("majesty_cam.standard_scripts.verify"), \
                 patch("majesty_cam.compose._parse_inventory_gpl_sources", return_value=[parse_gpl(callback())]), \
                 patch("majesty_cam.compose.validate_gpl_feature_evidence", return_value=[SimpleNamespace(
                     lifecycle="bazaar", mod_id="callback-owner", feature_key="visit", callback_symbol="Extra_Visit")]):
                native = provider(BAZAAR + HELPER)
                providers = Providers((native,), lambda names: {i.key: i for i in stock.items}, Path("unused"), scope)
                inventory = SimpleNamespace(selected=SimpleNamespace(alias="callback-owner"))
                result = compose.merge_gpl_resources((inventory,), standard_providers=providers,
                    stock_purchase_bazaar_source=stock, script_dataset=scope)
                parsed = parse_gpl(result.source_set.gpl_text)
                private = parsed.require("function", "CAM_Purchase_Bazaar_BeforeTail")
                self.assertEqual(private.text.replace("CAM_Purchase_Bazaar_BeforeTail", "Purchase_Bazaar", 1), BAZAAR)
                self.assertIn("$CAM_Purchase_Bazaar_BeforeTail", parsed.require("function", "Purchase_Bazaar").text)
                self.assertEqual(providers.lookup((private.kind, "private_shopping")).text, HELPER)


if __name__ == "__main__":
    unittest.main()
