import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from majesty_cam.inventory_items import parse, bindings, TYPE
from majesty_cam.package import parse_mod_definition, _runtime_feature_mapping
from majesty_cam.gpl import parse_gpl, merge_sources, add_inventory_death_drop_exclusions


class InventoryItemsTests(unittest.TestCase):
    def test_actual_stock_and_installed_inline_drop_conditions(self):
        game = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        paths = [game/'SDK/OriginalQuests/GPL/Hero_Deaths.gpl',
                 game/'SDK/OriginalQuests/GPLMx/mx_Hero_Deaths.gpl',
                 Path('C:/Users/bterr/Documents/My Games/MajestyHD/Mods/CustomGuildPhantomsHauntExpanded/GPL/Phantom.gpl')]
        for path in paths:
            if not path.is_file():
                continue
            with self.subTest(path=path):
                item = next(i for i in parse_gpl(path.read_text(encoding='latin1')).items
                            if i.normalized_name == 'hero_drop_quest_items')
                from majesty_cam.gpl import SemanticMergeResult
                source = SemanticMergeResult((*parse_gpl('Expression #PrivateDose 114\n').items, item), ())
                output = add_inventory_death_drop_exclusions(source, ('#PrivateDose',))
                changed = next(i for i in output.items if i.key == item.key)
                self.assertEqual(changed.text.replace(' && WhatItem != #PrivateDose', ''), item.text)
                self.assertEqual(add_inventory_death_drop_exclusions(output, ('#PrivateDose',)), output)

    def test_inline_comment_does_not_create_or_satisfy_an_exclusion(self):
        source = parse_gpl('''Expression #PrivateDose 114
Function Hero_Drop_Quest_Items(agent ThisAgent)
Declare integer WhatItem;
Begin
// WhatItem != #PrivateDose; WhatItem != #MarketItem_Market3_Item)
If (WhatItem != #QItem_Magic_Sword && WhatItem /*keep*/ != #MarketItem_Market3_Item)
    $SpawnUnit(ThisAgent,"Special_Item");
End
''')
        result = add_inventory_death_drop_exclusions(merge_sources([], {'mod':[source]}), ('#PrivateDose',))
        text = result.emit_project_source_set().gpl_text
        self.assertIn('WhatItem /*keep*/ != #MarketItem_Market3_Item && WhatItem != #PrivateDose)', text)

    def feature(self, expression="#PrivateDose"):
        return parse(dict(type=TYPE, feature_key="dose", item_expression=expression))

    def fixture(self, source, feature=None):
        feature = feature or self.feature()
        inventory = NS(selected=NS(alias="mod", package=NS(definition=NS(runtime_features=(feature,)))))
        return [inventory], {"mod": [parse_gpl(source, "dose.gpl")]}

    def test_binding_is_package_owned(self):
        self.assertEqual(bindings(*self.fixture("Expression #PrivateDose 114\n")), ("#PrivateDose",))
        with self.assertRaisesRegex(ValueError, "package-owned"):
            bindings(*self.fixture("Expression #Other 114\n"))

    def test_literal_signed_index_and_injection(self):
        for value in ("128", "-1", '"named"', "#Other"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "literal"):
                bindings(*self.fixture(f"Expression #PrivateDose {value}\n"))
        with self.assertRaises(ValueError):
            self.feature("#Dose); call()")

    def test_serialization(self):
        feature = self.feature()
        self.assertEqual(parse(_runtime_feature_mapping(feature)), feature)
        definition = parse_mod_definition(dict(schema_version=3,
            mod_id="11111111-1111-1111-1111-111111111111", internal_name="Items",
            display_name="Items", custom_buildings=[], runtime_features=[_runtime_feature_mapping(feature)]))
        self.assertEqual(definition.runtime_features, (feature,))

    def test_extends_without_removing_selected_drop_logic(self):
        source = parse_gpl('''Expression #PrivateDose 114
Function Hero_Drop_Quest_Items(agent ThisAgent)
Declare
    integer WhatItem;
Begin
    $DeleteInventoryItem(WhatItem,ThisAgent);
    If (WhatItem != #QItem_Magic_Sword &&
        WhatItem != #MarketItem_Ring_Protection &&
        WhatItem != #MarketItem_Market3_Item)
    Begin
        if (WhatItem < 80 || WhatItem > 112)
            $SpawnUnit(ThisAgent,"Special_Item");
    End
End
''', "selected.gpl")
        result = add_inventory_death_drop_exclusions(merge_sources([], {"selected": [source]}), ("#PrivateDose",))
        text = result.emit_project_source_set().gpl_text
        self.assertIn("WhatItem != #PrivateDose)", text)
        self.assertIn("WhatItem < 80 || WhatItem > 112", text)
        self.assertLess(text.index("$DeleteInventoryItem"), text.index("WhatItem != #PrivateDose"))

    def test_production_source_composer_loads_destination_function(self):
        from majesty_cam.compose import merge_gpl_resources
        from majesty_cam.gpl import DefinitionKind
        inventories, sources = self.fixture("Expression #PrivateDose 114\n")
        stock = parse_gpl('''Function Hero_Drop_Quest_Items(agent ThisAgent)
Declare
    integer WhatItem;
Begin
    $DeleteInventoryItem(WhatItem,ThisAgent);
    If (WhatItem != #QItem_Magic_Sword &&
        WhatItem != #MarketItem_Ring_Protection &&
        WhatItem != #MarketItem_Market3_Item)
        $SpawnUnit(ThisAgent,"Special_Item");
End
''', "stock.gpl").items[0]
        with patch("majesty_cam.compose._parse_inventory_gpl_sources", return_value=sources["mod"]):
            result = merge_gpl_resources(inventories, stock_function_loader=lambda names: {stock.key: stock})
        self.assertIn("WhatItem != #PrivateDose)", result.source_set.gpl_text)
        self.assertEqual(result.inventory_death_drop_exclusions, ("#PrivateDose",))


if __name__ == "__main__":
    unittest.main()
