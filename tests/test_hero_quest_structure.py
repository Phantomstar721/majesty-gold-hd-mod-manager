"""Source-only regressions for stock hero lifecycle continuation boundaries."""

from dataclasses import replace
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.gpl import add_hero_quest_lifecycle_callbacks, merge_sources, parse_gpl
from majesty_cam.gpl_function_merge import _Parser, _code, _render, _tokens, merge_function


CALLBACKS = """
function Quest_Resume(agent thisagent) is boolean begin return FALSE; end
function Quest_Consider(agent thisagent) is boolean begin return FALSE; end
function Quest_Reset(agent thisagent) begin end
function Quest_Death(agent thisagent) begin end
function Other_Resume(agent thisagent) is boolean begin return FALSE; end
function Other_Consider(agent thisagent) is boolean begin return FALSE; end
function Other_Reset(agent thisagent) begin end
function Other_Death(agent thisagent) begin end
"""

RESET = """function reset_tasks(agent thisagent)
begin
    $StopMoving(ThisAgent);
    thisagent's "target" = $Nullagent();
    thisagent's "activescript" = thisagent's "basicscript";
end
"""

DEATH = """function Unit_Call_Deathscript(agent thisagent)
begin
    $DeleteAllEffectors(thisagent);
    $ExtraCleanup(thisagent);
    if ($validfunction(thisagent's "IGDeathScript") == TRUE)
        begin
            (thisagent's "IGDeathScript")(thisagent);
            $AfterDispatch(thisagent);
        end
    else
        $MissingDeathScript(thisagent);
    $AfterDeath(thisagent);
end
"""

BASE_RESET = """function reset_tasks(agent thisagent)
declare
begin
    thisagent's "target" = $Nullagent();
    thisagent's "activescript" = thisagent's "basicscript";
    thisagent's "backscript" = thisagent's "basicscript";
    $clearlist(thisagent's "hostiles");
end
"""

BASE_DEATH = """function Unit_Call_Deathscript(agent thisagent)
declare
begin
    if ($validfunction(thisagent's "IGDeathScript") == TRUE)
        (thisagent's "IGDeathScript")(thisagent);
end
"""


def _function(name, body):
    return f"function {name}(agent thisagent)\nbegin\n{body}\nend\n"


def _render_function(text):
    signature, declarations, body = _Parser(text).function()
    return "\n".join((
        _code(signature), "declare",
        *(f"{kind} {name};" for name, kind in declarations.items()),
        "begin", *_render(body), "end", "",
    ))


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.body)
        yield from _walk(node.otherwise)


def _callback(node):
    return any(token.startswith(("$quest_", "$other_")) for token in node.head)


def _remove_callbacks(nodes):
    """Remove only generated guards/calls, retaining all original structure."""
    output = []
    for node in nodes:
        if _callback(node):
            if node.kind == "if":
                if node.otherwise:
                    raise AssertionError("generated callback captured a stock else branch")
                output.extend(_remove_callbacks(node.body))
            elif node.kind != "statement":
                raise AssertionError("unexpected generated callback structure")
        else:
            output.append(replace(
                node, body=_remove_callbacks(node.body),
                otherwise=_remove_callbacks(node.otherwise),
            ))
    return tuple(output)


def _tree(consider="$Pursue_Entertainment(thisagent)", name="Priestess_tree"):
    # Explicit blocks, else branches and siblings are intentional: a guard
    # spliced onto just the first child must not let the remaining body escape.
    return _function(name, f"""
        $Before(thisagent, 1);
        if ($Check_Nearby(thisagent) == FALSE)
        begin
            if ($Check_rewards(thisagent, FALSE) == FALSE)
            begin
                if ({consider} == FALSE)
                begin
                    if ($Go_home(thisagent, 95) == FALSE)
                        $Wander(thisagent);
                    else
                        $AtHome(thisagent);
                    $AfterConsider(thisagent);
                end
                else
                    $EntertainmentAccepted(thisagent);
                $AfterRewards(thisagent);
            end
            else
                $RewardAccepted(thisagent);
        end
        else
            $NearbyAccepted(thisagent);
        $After(thisagent, 2);
    """)


class HeroQuestStructureTests(unittest.TestCase):
    def compose(self, tree, *, script="mx_priestess", reset=RESET, death=DEATH,
                stock_reset=None, stock_death=None, other_callbacks=False):
        tree_item = parse_gpl(tree, "selected-tree.gpl").items[0]
        selected = parse_gpl("\n".join((CALLBACKS, tree, reset, death)), "selected.gpl")
        hooks = [((script,), "Quest_Resume", "Quest_Consider", "Quest_Reset", "Quest_Death")]
        if other_callbacks:
            hooks.append(((script,), "Other_Resume", "Other_Consider", "Other_Reset", "Other_Death"))
        result = add_hero_quest_lifecycle_callbacks(
            merge_sources([], {"selected": [selected]}), hooks,
            stock_hero_trees={script: tree_item},
            stock_reset_tasks=parse_gpl(stock_reset or reset, "stock-reset.gpl").items[0],
            stock_unit_death=parse_gpl(stock_death or death, "stock-death.gpl").items[0],
        )
        return {item.normalized_name: item.text for item in result.items}

    def assert_structure_preserved(self, original, composed):
        signature, declarations, body = _Parser(composed).function()
        self.assertEqual(
            (signature, declarations, _remove_callbacks(body)),
            _Parser(original).function(),
        )

    def assert_guard_wraps_body(self, original, composed, call, callback_names):
        before = [node for node in _walk(_Parser(original).function()[2]) if call in node.head]
        after = [node for node in _walk(_Parser(composed).function()[2]) if call in node.head]
        self.assertEqual(len(before), 1)
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].otherwise, before[0].otherwise)
        body = after[0].body
        for callback in callback_names:
            self.assertEqual(len(body), 1, "a stock sibling escaped the generated guard")
            self.assertEqual(body[0].head, _tokens(f"if (${callback}(ThisAgent) == False)"))
            self.assertFalse(body[0].otherwise)
            body = body[0].body
        self.assertEqual(_remove_callbacks(body), before[0].body)

    def test_raw_and_renderer_trees_keep_full_branches_and_else_ownership(self):
        raw = _tree()
        for variant in (raw, _render_function(raw)):
            with self.subTest(rendered=variant != raw):
                output = self.compose(variant, other_callbacks=True)["priestess_tree"]
                self.assert_structure_preserved(variant, output)
                self.assert_guard_wraps_body(
                    variant, output, "$check_nearby", ("Quest_Resume", "Other_Resume"),
                )
                self.assert_guard_wraps_body(
                    variant, output, "$pursue_entertainment", ("Quest_Consider", "Other_Consider"),
                )

    def test_actual_disjoint_function_merge_output_is_accepted(self):
        raw = _tree()
        merged = merge_function(raw, {
            "before": raw.replace("$Before(thisagent, 1)", "$Before(thisagent, 5)"),
            "after": raw.replace("$After(thisagent, 2)", "$After(thisagent, 9)"),
        })
        self.assertNotEqual(merged, raw)
        output = self.compose(merged)["priestess_tree"]
        self.assert_structure_preserved(merged, output)
        self.assert_guard_wraps_body(merged, output, "$check_nearby", ("Quest_Resume",))
        self.assert_guard_wraps_body(merged, output, "$pursue_entertainment", ("Quest_Consider",))

    def test_same_line_comments_and_redundant_blocks_do_not_define_scope(self):
        raw = _function("Priestess_tree", """
            // if ($Check_Nearby(thisagent) == False) is not a second anchor.
            if ($Check_Nearby /* nearby */ (thisagent) == FALSE) begin begin
                if ($Check_rewards(thisagent, FALSE) == FALSE) begin
                    if ($Pursue_Entertainment(thisagent) == FALSE) begin begin
                        $Go_home(thisagent, 95); $AfterConsider(thisagent);
                    end end else $EntertainmentAccepted(thisagent);
                end else $RewardAccepted(thisagent);
            end end else $NearbyAccepted(thisagent);
            $After(thisagent, 2);
        """)
        output = self.compose(raw)["priestess_tree"]
        self.assert_structure_preserved(raw, output)
        self.assertIn("/* nearby */", output)
        self.assertIn("// if ($Check_Nearby", output)
        self.assert_guard_wraps_body(raw, output, "$check_nearby", ("Quest_Resume",))
        self.assert_guard_wraps_body(raw, output, "$pursue_entertainment", ("Quest_Consider",))

    def test_healer_and_monk_expansion_use_bazaar_false_branch(self):
        for script in ("mx_healer", "mx_monk"):
            name = script[3:] + "_tree"
            raw = _tree("$Purchase_Bazaar(thisagent, 70)", name)
            for variant in (raw, _render_function(raw)):
                with self.subTest(script=script, rendered=variant != raw):
                    output = self.compose(variant, script=script)[name]
                    self.assert_structure_preserved(variant, output)
                    self.assert_guard_wraps_body(variant, output, "$purchase_bazaar", ("Quest_Consider",))

    def test_healer_and_monk_original_quests_use_audited_stock_gap(self):
        cases = (
            ("mx_healer", '$Follow_Heal_Check(thisagent, "tax_collector", 50)',
             "$Seed_Resource_Check(thisagent, 50)", "$follow_heal_check"),
            ("mx_monk", "$Collect_Special_Item(thisagent, 70)",
             "$Go_home(thisagent, 60)", "$collect_special_item"),
        )
        for script, before, after, before_token in cases:
            name = script[3:] + "_tree"
            raw = _function(name, f"""
                if ($Check_Nearby(thisagent) == FALSE)
                if ($Check_rewards(thisagent, TRUE) == FALSE)
                if ({before} == FALSE)
                begin
                    if ({after} == FALSE) $Wander(thisagent);
                end
                $AfterTree(thisagent);
            """)
            for variant in (raw, _render_function(raw)):
                with self.subTest(script=script, rendered=variant != raw):
                    output = self.compose(variant, script=script)[name]
                    self.assert_structure_preserved(variant, output)
                    self.assert_guard_wraps_body(variant, output, before_token, ("Quest_Consider",))

    def test_structurally_different_resume_or_consider_anchors_fail_closed(self):
        nearby = "if ($Check_Nearby(thisagent) == FALSE)"
        reward = "if ($Check_rewards(thisagent, FALSE) == FALSE)"
        pursue = "if ($Pursue_Entertainment(thisagent) == FALSE)"
        leaf = "$Go_home(thisagent, 95);"
        cases = {
            "reordered": f"{reward} {nearby} {pursue} {leaf}",
            "duplicate-nearby": f"{nearby} {reward} {pursue} {leaf} {nearby} {leaf}",
            "duplicate-reward": f"{nearby} {reward} {pursue} {leaf} {reward} {leaf}",
            "missing-nearby": f"{reward} {pursue} {leaf}",
            "missing-reward": f"{nearby} {pursue} {leaf}",
            "missing-consider": f"{nearby} {reward} {leaf}",
            "separate-branches": f"if ($Ready(thisagent)) begin {nearby} {leaf} end else begin {reward} {pursue} {leaf} end",
            "intervening-work": f"{nearby} begin $DifferentWork(thisagent); {reward} {pursue} {leaf} end",
            "trailing-resume-work": f"{nearby} begin {reward} {pursue} {leaf} $DifferentWork(thisagent); end",
            "intervening-branch": f"{nearby} if ($DifferentChoice(thisagent) == FALSE) {reward} {pursue} {leaf}",
            "loop": f"while ($Ready(thisagent)) do begin {nearby} {reward} {pursue} {leaf} end",
            "consider-separate": f"{nearby} {reward} {leaf} {pursue} {leaf}",
            "consider-in-else": f"{nearby} {reward} {leaf} else {pursue} {leaf}",
        }
        for label, body in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    self.compose(_function("Priestess_tree", body))

    def test_bazaar_gap_is_not_a_fallback_for_unrelated_hero_types(self):
        with self.assertRaises(ValueError):
            self.compose(_tree("$Purchase_Bazaar(thisagent, 70)"))

    def test_reset_and_death_renderer_and_same_line_sources_preserve_instructions(self):
        tree = _tree()
        for mode in ("raw", "rendered", "same-line"):
            transform = {"raw": lambda s: s, "rendered": _render_function,
                         "same-line": lambda s: " ".join(s.splitlines())}[mode]
            reset, death = transform(RESET), transform(DEATH)
            with self.subTest(mode=mode):
                result = self.compose(tree, reset=reset, death=death, other_callbacks=True)
                self.assert_structure_preserved(reset, result["reset_tasks"])
                self.assert_structure_preserved(death, result["unit_call_deathscript"])
                reset_body = _Parser(result["reset_tasks"]).function()[2]
                self.assertEqual(reset_body[0].head, _tokens("$Quest_Reset(ThisAgent);"))
                self.assertEqual(reset_body[1].head, _tokens("$Other_Reset(ThisAgent);"))
                death_body = _Parser(result["unit_call_deathscript"]).function()[2]
                dispatch = next(i for i, node in enumerate(death_body) if "$validfunction" in node.head)
                self.assertEqual(death_body[dispatch - 2].head, _tokens("$Quest_Death(ThisAgent);"))
                self.assertEqual(death_body[dispatch - 1].head, _tokens("$Other_Death(ThisAgent);"))
                self.assertEqual(death_body[dispatch - 3].head, _tokens("$ExtraCleanup(ThisAgent);"))

    def test_original_game_reset_and_death_keep_their_stock_boundaries(self):
        for transform in (_render_function, lambda s: " ".join(s.splitlines())):
            reset, death = transform(BASE_RESET), transform(BASE_DEATH)
            with self.subTest(transform=transform.__name__):
                result = self.compose(_tree(), reset=reset, death=death,
                                      stock_reset=BASE_RESET, stock_death=BASE_DEATH)
                self.assert_structure_preserved(reset, result["reset_tasks"])
                self.assert_structure_preserved(death, result["unit_call_deathscript"])


if __name__ == "__main__":
    unittest.main()
