"""Source-only checks for stock event hooks after instruction-merge rendering."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from majesty_cam.gameplay_events import (
    EVENT_FUNCTIONS, EVENT_SIGNATURES, STOCK_EVENT_FILES,
    add_gameplay_event_observers,
)
from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from majesty_cam.gpl_function_merge import (
    _Parser, _code, _render, same_function_instructions,
)


STOCK = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/OriginalQuests/GPLMx")


def rendered(text):
    signature, declarations, body = _Parser(text).function()
    return (_code(signature) + "\ndeclare\n"
            + "".join(f"{kind} {name};\n" for name, kind in sorted(declarations.items()))
            + "begin\n" + "\n".join(_render(body)) + "\nend\n")




@unittest.skipUnless(STOCK.is_dir(), "requires installed stock GPL source")
class RenderedStockEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sources = {relative: parse_gpl((STOCK / relative).read_text(encoding="cp1252"))
                   for relative in set(STOCK_EVENT_FILES.values())}
        cls.stock = {name: sources[relative].require(DefinitionKind.FUNCTION, name)
                     for name, relative in STOCK_EVENT_FILES.items()}

    def callback(self, event):
        args = ", ".join(f"{kind} Arg{index}" for index, kind in enumerate(EVENT_SIGNATURES[event]))
        return parse_gpl(f"function Observe({args}) declare begin end").items[0]

    def compose(self, event, items):
        return add_gameplay_event_observers(
            SemanticMergeResult((*items, self.callback(event)), ()), {event: ("Observe",)}, self.stock)

    def test_every_event_retains_identical_instructions_after_rendering(self):
        for event, names in EVENT_FUNCTIONS.items():
            if not names:
                continue
            with self.subTest(event=event):
                owners = (*names, *(("shapeshift_potion_end",) if event == "potion-consumed" else ()))
                original = tuple(self.stock[name] for name in owners)
                rendered_items = tuple(replace(item, text=rendered(item.text)) for item in original)
                first = {item.key: item for item in self.compose(event, original).items}
                second = {item.key: item for item in self.compose(event, rendered_items).items}
                self.assertEqual(first.keys(), second.keys())
                for key in first:
                    self.assertTrue(same_function_instructions(first[key].text, second[key].text), (event, key))

    def test_rendered_potion_additions_keep_normal_and_extra_consumption_events(self):
        item = self.stock["regeneration_elixer_effect"]
        pair = '$DeleteInventoryItem(#Bazaar_Item_Four, ThisAgent); $ForgetSpell(ThisAgent, "Regeneration_Elixer");'
        branch = 'if (ThisAgent\'s "Title" == "PrivateType") begin ' + pair + ' return; end\n'
        modified = re.sub(r'\$createeffector\b', lambda m: branch + m.group(), item.text, count=1, flags=re.I)
        for text in (modified, rendered(modified)):
            observed = next(result.text for result in self.compose("potion-consumed", (replace(item, text=text),)).items
                            if result.key == item.key)
            self.assertEqual(observed.count('$Observe('), 2)
            restored = re.sub(r'\$Observe\(ThisAgent, "regeneration_elixer"\);', '', observed)
            self.assertTrue(same_function_instructions(restored, modified))

    def test_shared_rendered_owners_keep_all_observers_and_compile(self):
        from majesty_cam.compose import compile_gpl
        subscribers, callbacks = {}, []
        for index, event in enumerate(EVENT_FUNCTIONS):
            if not EVENT_FUNCTIONS[event]:
                continue
            name = "Observe" + str(index)
            subscribers[event] = (name,)
            callbacks.extend(parse_gpl(self.callback(event).text.replace("Observe", name)).items)
        outputs = []
        for normalize in (False, True):
            owners = tuple(replace(item, text=rendered(item.text)) if normalize else item
                           for item in self.stock.values())
            outputs.append(add_gameplay_event_observers(
                SemanticMergeResult((*owners, *callbacks), ()), subscribers, self.stock))
        first = {item.key: item for item in outputs[0].items}
        second = {item.key: item for item in outputs[1].items}
        self.assertEqual(first.keys(), second.keys())
        for key in first:
            self.assertTrue(same_function_instructions(first[key].text, second[key].text), key)
        compiler = STOCK.parents[1] / "Gplbcc.exe"
        if compiler.is_file():
            with TemporaryDirectory(prefix="rendered-event-source-fixture-") as temp:
                compile_gpl(outputs[1].emit_project_source_set(), compiler, Path(temp) / "compiler")

    def test_notification_does_not_validate_or_replace_selected_transformation(self):
        names = ("shapeshift_potion_effect", "shapeshift_potion_end")
        additions = tuple(replace(self.stock[name], text=rendered(self.stock[name].text.replace(
            'title == "Healer"', 'title == "Healer" || title == "Private Caster"'))) for name in names)
        final = {item.key: item for item in self.compose("potion-consumed", additions).items}
        self.assertEqual(final[additions[1].key].text, additions[1].text)
        self.assertEqual(final[additions[0].key].text.count('$Observe('), 1)
        for effect, expiry in (
            (additions[0], self.stock[names[1]]),
            (additions[0], replace(additions[1], text=additions[1].text.replace('Private Caster', 'Other Caster'))),
            (replace(additions[0], text=additions[0].text.replace('#attrib_maxhp , 30', '#attrib_maxhp , 31')), additions[1]),
            (additions[0], replace(additions[1], text=additions[1].text.replace('#attrib_maxhp , - 30', '#attrib_maxhp , - 31'))),
        ):
            with self.subTest(effect=effect.text, expiry=expiry.text):
                final = {item.key: item for item in self.compose("potion-consumed", (effect, expiry)).items}
                self.assertEqual(final[expiry.key].text, expiry.text)
                restored = re.sub(r'\$Observe\(ThisAgent, "shapeshift_potion"\);', '', final[effect.key].text)
                self.assertTrue(same_function_instructions(restored, effect.text))
