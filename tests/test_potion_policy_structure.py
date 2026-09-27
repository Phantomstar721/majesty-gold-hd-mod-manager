"""Isolated potion source composition, never a prepared Manager profile."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.compose import _decode_source_text, compile_gpl
from majesty_cam.gameplay_events import (
    EVENT_FUNCTIONS, add_gameplay_event_observers,
)
from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from majesty_cam.gpl_function_merge import _Parser, _code, _render
from majesty_cam.potion_policy import Action, Plan, POTIONS, compose, parse_feature
from majesty_cam.private_phantom_policy import POLICY


STEAM = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD")
GOG = Path("C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD")
NATIVE = Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3743606613/GPL")


def rendered(text):
    signature, declarations, body = _Parser(text).function()
    result = "\n".join((
        _code(signature), "declare",
        *(f"{kind} {name};" for name, kind in sorted(declarations.items())),
        "begin", *_render(body), "end", "",
    ))
    if _Parser(text).function() != _Parser(result).function():
        raise AssertionError("fixture rendering changed instructions")
    return result


def read_items(path):
    return {item.key: item for item in parse_gpl(
        _decode_source_text(path.read_bytes(), path), str(path)).items}


def function(name):
    return DefinitionKind.FUNCTION, name.casefold()


def nodes(source):
    return _Parser(source).function()[2]


def statements(source):
    return nodes("function Fixture() declare begin\n" + source + "\nend")


def walk(sequence):
    for node in sequence:
        yield node
        yield from walk(node.body)
        yield from walk(node.otherwise)


class PotionPolicyStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_root = STEAM / "SDK/OriginalQuests/GPLMx"
        if not source_root.is_dir():
            raise unittest.SkipTest("requires installed stock source")
        cls.stock = {}
        for relative in (
            "TaskModules/Buildings/Magic_Bazaar.gpl",
            "TaskModules/Subtasks/mx_Spells.gpl",
            "TaskModules/Subtasks/mx_heal_self.gpl",
        ):
            cls.stock.update(read_items(source_root / relative))
        cls.actions = tuple(
            Action(potion, name, name + "_Effect", "", f"P0{index:02d}")
            for index, (potion, (_, name)) in enumerate(POTIONS.items())
        )
        policy = deepcopy(POLICY)
        policy.update(feature_key="fixture-potion-policy", hero_title="FixtureCaster")
        cls.plan = Plan((parse_feature(policy),), cls.actions)
        cls.callback = parse_gpl(
            "function FixtureObserve(agent Actor, string Item) declare begin end"
        ).items[0]

    def loader(self, names):
        return {function(name): self.stock[function(name)] for name in names}

    def native_items(self):
        paths = (NATIVE / "MiscEnhancements/AI_Bazarr.gpl",
                 NATIVE / "TaskModules/Subtasks/MK_Spells.gpl")
        if not all(path.is_file() for path in paths):
            self.skipTest("requires installed native source fixture")
        parsed = {}
        for path in paths:
            parsed.update(read_items(path))
        return {function(name): parsed[function(name)] for name in (
            "Bazaar_Item_Check", "Shapeshift_Potion_Effect", "Shapeshift_Potion_End",
        )}

    def inputs(self, native=None, render=False):
        names = {
            "bazaar_item_check", "shapeshift_potion_end",
            *EVENT_FUNCTIONS["potion-consumed"],
            *("purchase_bazaar_item_" + number.casefold() for number, _ in POTIONS.values()),
        }
        selected = {key: item for key, item in self.stock.items() if key[1] in names}
        selected.update(native or {})
        return {key: replace(item, text=rendered(item.text), span=None) if render else item
                for key, item in selected.items()}

    def compose_sources(self, selected=None, *, observe=False):
        selected = {} if selected is None else selected
        native = dict(self.stock)
        native.update(selected)
        native_loader = lambda names: {function(name): native[function(name)] for name in names}
        evidence = {name: self.stock[function(name)] for name in (
            *EVENT_FUNCTIONS["potion-consumed"], "shapeshift_potion_end",
        )}
        result, evidence = compose(
            SemanticMergeResult((self.callback, *selected.values()), ()),
            self.plan, self.loader, evidence, native_loader=native_loader,
        )
        if observe:
            result = add_gameplay_event_observers(
                result, {"potion-consumed": ("FixtureObserve",)}, evidence,
            )
        return result

    def assert_same_instructions(self, first, second):
        first = {item.key: _Parser(item.text).function() for item in first.items}
        second = {item.key: _Parser(item.text).function() for item in second.items}
        self.assertEqual(first, second)

    def test_raw_and_explicit_block_views_have_identical_policy_and_observers(self):
        # The original view uses stock owners; the expansion view retains its
        # native owner. This is source composition only, not Prepare/build.
        for scope, native in (("Majesty", {}), ("MajestyExpansion", self.native_items())):
            with self.subTest(scope=scope):
                raw = self.compose_sources(self.inputs(native), observe=True)
                blocked = self.compose_sources(self.inputs(native, render=True), observe=True)
                self.assert_same_instructions(raw, blocked)
                items = {item.normalized_name: item for item in blocked.items}
                for _, action_name in POTIONS.values():
                    body = nodes(items[action_name.casefold() + "_effect"].text)
                    dead = statements("if ($IsDead(ThisAgent)) return;")[0]
                    self.assertEqual(body[0], dead)
                    self.assertIn("$mm_bp_eligibility", body[1].head)
                    observed = [node for node in walk(body)
                                if "$fixtureobserve" in node.head]
                    self.assertEqual(len(observed), 1)
                    self.assertEqual(body[-1], observed[0])

    def test_native_shopping_restrictions_costs_and_intent_survive(self):
        native = self.native_items()
        original = nodes(native[function("Bazaar_Item_Check")].text)
        result = self.compose_sources(self.inputs(native, render=True))
        text = next(item.text for item in result.items if item.key == function("Bazaar_Item_Check"))
        actual = nodes(text)
        restriction_nodes = statements('''
            if ((thisagent's "title" == "cultist") && (item == #Bazaar_Item_Six)) return False;
            if (item == #Bazaar_Item_Two)
                if ((thisagent's "title" != "ranger") && (thisagent's "title" != "rogue") && (thisagent's "title" != "elf")) return False;
        ''')
        # All original statements remain, in order. Only the recognized stock
        # restrictions move under an eligibility fallback wrapper.
        restored = []
        wrapped = []
        for node in actual:
            if "$mm_bp_eligibility" not in node.head:
                restored.append(node)
            elif node.body != statements("return False;"):
                restored.extend(node.body)
                wrapped.extend(node.body)
        self.assertEqual(tuple(restored), original)
        self.assertEqual(tuple(wrapped), restriction_nodes)

    def test_private_stock_shopping_clone_gets_guard_after_rendering(self):
        original = self.stock[function("Bazaar_Item_Check")]
        text = original.text.replace("Bazaar_Item_Check", "Fixture_Private_Shop", 1)
        private = parse_gpl(rendered(text)).items[0]
        result = self.compose_sources({private.key: private})
        final = next(item for item in result.items if item.key == private.key)
        expected_guard = statements("if ($MM_BP_Eligibility(ThisAgent, item) == 0) return False;")
        self.assertEqual(nodes(final.text), (*expected_guard, *nodes(private.text)))

    def test_changed_private_shopping_tail_is_not_mistaken_for_stock_clone(self):
        original = self.stock[function("Bazaar_Item_Check")]
        text = original.text.replace("Bazaar_Item_Check", "Fixture_Custom_Shop", 1)
        text = text.replace("#ATTRIB_Intelligence", "#ATTRIB_Willpower")
        private = parse_gpl(rendered(text)).items[0]
        result = self.compose_sources({private.key: private})
        final = next(item for item in result.items if item.key == private.key)
        self.assertEqual(_Parser(final.text).function(), _Parser(private.text).function())

    def test_additive_native_shape_titles_remain_paired_after_rendering(self):
        native = self.native_items()
        result = self.compose_sources(self.inputs(native, render=True), observe=True)
        items = {item.normalized_name: item for item in result.items}
        effect = nodes(items["shapeshift_potion_effect"].text)
        expiry = nodes(items["shapeshift_potion_end"].text)
        native_titles = next(node.head for node in walk(nodes(
            native[function("Shapeshift_Potion_Effect")].text))
            if '"MK_Goblin_Priest"' in node.head)
        self.assertIn(native_titles, [node.head for node in walk(effect)])
        self.assertIn(native_titles, [node.head for node in walk(expiry)])
        declaration = '"FixtureCaster"'
        self.assertEqual(sum(declaration in node.head for node in walk(effect)), 1)
        self.assertEqual(sum(declaration in node.head for node in walk(expiry)), 1)

    def test_changed_stock_rejection_body_still_fails_closed(self):
        original = self.stock[function("Bazaar_Item_Check")]
        for replacement in ("return True;", "$UnexpectedSideEffect(ThisAgent); return False;"):
            with self.subTest(replacement=replacement):
                # Put additional statements inside the guard, never outside it.
                text = original.text.replace("return False;", "begin " + replacement + " end", 1)
                changed = replace(original, text=rendered(text), span=None)
                with self.assertRaises(ValueError):
                    self.compose_sources({changed.key: changed})

    def test_changed_effect_cleanup_and_unpaired_titles_still_fail_closed(self):
        effect = self.stock[function("Shapeshift_Potion_Effect")]
        expiry = self.stock[function("Shapeshift_Potion_End")]
        for item, before, after in (
            (effect, "#ATTRIB_MaxHP, 30", "#ATTRIB_MaxHP, 99"),
            (expiry, "#ATTRIB_MaxHP, -30", "#ATTRIB_MaxHP, -99"),
            (effect, 'title == "Healer"', 'title == "Healer" || title == "OnlyInEffect"'),
            (expiry, 'title == "Healer"', 'title == "Healer" || title == "OnlyInExpiry"'),
        ):
            with self.subTest(function=item.name, change=after):
                text = item.text.replace(before, after)
                self.assertNotEqual(text, item.text)
                changed = replace(item, text=rendered(text), span=None)
                with self.assertRaises(ValueError):
                    self.compose_sources({changed.key: changed})

    def test_changed_or_missing_dead_guard_is_rejected_for_every_potion(self):
        from majesty_cam.gpl_function_merge import _SourceParser
        for _, action_name in POTIONS.values():
            item = self.stock[function(action_name + "_Effect")]
            parser = _SourceParser(item.text)
            body = parser.function()[2]
            self.assertEqual(body[0], statements("if ($IsDead(ThisAgent)) return;")[0])
            start, end = parser.node_spans[id(body[0])]
            for replacement in ("", "if ($IsDead(ThisAgent)) begin $UnsafeChange(ThisAgent); return; end"):
                with self.subTest(action=action_name, replacement=replacement):
                    changed = replace(item, text=rendered(
                        item.text[:start] + replacement + item.text[end:]), span=None)
                    with self.assertRaises(ValueError):
                        self.compose_sources({changed.key: changed})

    def test_rendered_source_views_compile_with_each_installed_sdk(self):
        compilers = [game / "SDK/Gplbcc.exe" for game in (STEAM, GOG)
                     if (game / "SDK/Gplbcc.exe").is_file()]
        if not compilers:
            self.skipTest("requires an installed stock compiler")
        # No package manifests, installed profiles or game settings are touched.
        with TemporaryDirectory() as temporary:
            for scope, native in (("Majesty", {}), ("MajestyExpansion", self.native_items())):
                output = self.compose_sources(self.inputs(native, render=True), observe=True)
                for index, compiler in enumerate(compilers):
                    with self.subTest(scope=scope, compiler=compiler):
                        compile_gpl(output.emit_project_source_set(), compiler,
                                    Path(temporary) / f"{scope}-{index}")


if __name__ == "__main__":
    unittest.main()
