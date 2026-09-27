"""Stock follower boundaries must survive instruction-merge source rendering."""
from dataclasses import replace
from pathlib import Path
import unittest

from majesty_cam.gpl import (
    SemanticMergeResult, add_controlled_follower_movement_adjustments, parse_gpl,
)
from majesty_cam.gpl_function_merge import _Parser, _code, _render, _tokens


CONTROL = '''Function Control_Monster(agent ThisAgent, agent Target)
Declare
Begin
    If ($IsDead(Target)) return;
    (ThisAgent's "Num_Followers") ++;
    Target's "ActiveScript" = $fake_wander;
    Target's "Type" = "Hidden";
    $createeffector(target, "Charm_icon", 1, "infinite");
    target's "counter" = 0;
    Target's "BackScript" = $Controlled_Monster;
    Target's "IGDeathScript" = $Controlled_Monster_Death;
    Target's "leader" = ThisAgent;
    $DebugOut(thisagent's "title", "CONTROLS a", target's "Title", "!!!");
    $setunitplayernumber(target, $getunitplayernumber(thisagent));
End'''
DEATH = '''Function Controlled_Monster_Death(agent ThisAgent)
Declare agent Leader;
Begin
    Leader = ThisAgent's "Leader";
    If ($IsValidGamePiece(Leader)) (Leader's "Num_Followers") --;
    $Monster_Gravestone(ThisAgent);
End'''
LEADER = '''function leader_dead(agent thisagent) is boolean
declare agent leader;
begin
    leader = thisagent's "leader";
    if ($isvalidgamepiece(leader) == false)
        begin
            ThisAgent's "ActiveScript" = $fake_stop;
            ThisAgent's "Type" = "Dead";
            thisagent's "counter" == 0;
            $deleteeffector(thisagent,"charm_icon");
            return TRUE;
        end
    return FALSE;
end'''
CALLBACK = '''function Rental_Speed_Applies(agent Leader, agent Follower) is boolean
begin return TRUE; end'''
MARKERS = tuple(f"MCF0123456789AB{tier}" for tier in range(1, 5))
HOOKS = (("Rental_Speed_Applies", -125, MARKERS),)
STOCK_FILES = {
    "control_monster": "TaskModules/Subtasks/mx_Control_Monster.gpl",
    "controlled_monster_death": "TaskModules/Characters/Monsters/mx_Controlled_Monster.gpl",
    "leader_dead": "TaskModules/Characters/Monsters/mx_Controlled_Monster.gpl",
}
INSTALLS = (
    Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD"),
    Path("C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD"),
)


def rendered(text):
    signature, declarations, body = _Parser(text).function()
    return (_code(signature) + "\ndeclare\n"
            + "".join(f"{kind} {name};\n" for name, kind in sorted(declarations.items()))
            + "begin\n" + "\n".join(_render(body)) + "\nend\n")


def items(control=CONTROL, death=DEATH, leader=LEADER):
    return tuple(parse_gpl(text).items[0] for text in (control, death, leader))


def composed(stock, *, materialize=False):
    callback = parse_gpl(CALLBACK).items[0]
    selected = (callback,) if materialize else (callback, *stock)
    result = add_controlled_follower_movement_adjustments(
        SemanticMergeResult(selected, ()), HOOKS,
        stock_control_monster=stock[0],
        stock_controlled_monster_death=stock[1],
        stock_leader_dead=stock[2],
    )
    return {item.normalized_name: item for item in result.items}


class ControlledFollowerStructureTests(unittest.TestCase):
    def assert_only_hooks_added(self, before, after):
        expected = _Parser(before).function()
        signature, declarations, body = _Parser(after).function()
        removed = []

        def strip(nodes):
            kept = []
            for node in nodes:
                generated = node.kind == "if" and (
                    "$rental_speed_applies" in node.head
                    or ("$checkeffector" in node.head
                        and any(f'"{marker}"' in node.head for marker in MARKERS))
                )
                if generated:
                    removed.append(node)
                else:
                    kept.append(replace(node, body=strip(node.body), otherwise=strip(node.otherwise)))
            return tuple(kept)

        self.assertEqual((signature, declarations, strip(body)), expected)
        self.assertEqual(len(removed), 1 if expected[0][1] == "control_monster" else 4)

    def test_layout_variants_preserve_original_instructions_and_scopes(self):
        layouts = (
            lambda text: text,
            rendered,
            lambda text: _code(_tokens(text)).replace("; end", ";end"),
            lambda text: rendered(text).replace("\n", "\r\n"),
            lambda text: rendered(text).replace(" = ", "\n=\n").replace(" + +", " + /* count */ +"),
        )
        for layout in layouts:
            stock = tuple(replace(item, text=layout(item.text)) for item in items())
            for materialize in (False, True):
                with self.subTest(layout=layout, materialize=materialize):
                    result = composed(stock, materialize=materialize)
                    for item in stock:
                        self.assert_only_hooks_added(item.text, result[item.normalized_name].text)
                    body = _Parser(result["control_monster"].text).function()[2]
                    self.assertEqual(body[-2].head[0], "$setunitplayernumber")
                    self.assertEqual(body[-1].head[2], "$rental_speed_applies")

    def test_cleanup_keeps_unbraced_body_and_else_ownership(self):
        death = DEATH.replace("$Monster_Gravestone(ThisAgent);",
                              'if ($Valid(ThisAgent)) $Monster_Gravestone(ThisAgent); '
                              'else $DebugOut("other");')
        leader = LEADER.replace('$deleteeffector(thisagent,"charm_icon");',
                                'if ($Valid(ThisAgent)) $deleteeffector(thisagent,"charm_icon"); '
                                'else $DebugOut("other");')
        stock = tuple(replace(item, text=_code(_tokens(item.text)))
                      for item in items(death=death, leader=leader))
        result = composed(stock)
        for item in stock:
            self.assert_only_hooks_added(item.text, result[item.normalized_name].text)

    def test_changed_or_ambiguous_setup_and_handoff_are_rejected(self):
        handoff = "$setunitplayernumber(target, $getunitplayernumber(thisagent));"
        variants = (
            CONTROL.replace("$IsDead(Target)", "$IsDead(ThisAgent)"),
            CONTROL.replace(" ++;", " --;"),
            CONTROL.replace("$fake_wander", "$different_wander"),
            CONTROL.replace('"Charm_icon", 1', '"Charm_icon", 2'),
            CONTROL.replace("$Controlled_Monster;", "$different_follower;"),
            CONTROL.replace("$Controlled_Monster_Death;", "$different_death;"),
            CONTROL.replace('"leader" = ThisAgent', '"leader" = Target'),
            CONTROL.replace(handoff, "$different_handoff(Target);"),
            CONTROL.replace(handoff, "$setunitplayernumber(ThisAgent, $getunitplayernumber(Target));"),
            CONTROL.replace(handoff, handoff + handoff),
            CONTROL.replace(handoff, handoff + " if ($Valid(Target)) " + handoff),
            CONTROL.replace(handoff, "if ($Valid(Target)) " + handoff),
            CONTROL.replace('Target\'s "leader" = ThisAgent;', "")
                   .replace(handoff, handoff + 'Target\'s "leader" = ThisAgent;'),
            CONTROL.replace("If ($IsDead(Target)) return;", ""),
            CONTROL.replace(" ++;", " ++; (ThisAgent's \"Num_Followers\") ++;"),
        )
        for control in variants:
            with self.subTest(control=control), self.assertRaisesRegex(ValueError, "stock"):
                composed(items(control=rendered(control)))

    def test_cleanup_rejects_changed_missing_or_ambiguous_call(self):
        for source, anchor, keyword in (
            (DEATH, "$Monster_Gravestone(ThisAgent);", "death"),
            (LEADER, '$deleteeffector(thisagent,"charm_icon");', "leader"),
        ):
            replacements = (
                anchor.replace("thisagent", "leader").replace("ThisAgent", "Leader"),
                "",
                anchor + anchor,
                anchor + " if ($Valid(ThisAgent)) " + anchor,
                "// " + anchor + "\n",
            )
            for replacement in replacements:
                with self.subTest(keyword=keyword, replacement=replacement):
                    stock = items(**{keyword: rendered(source.replace(anchor, replacement))})
                    with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                        composed(stock)

    def test_comment_and_string_decoys_do_not_move_cleanup_boundary(self):
        death = DEATH.replace("$Monster_Gravestone(ThisAgent);",
                              '// $Monster_Gravestone(ThisAgent);\n'
                              '$DebugOut("$Monster_Gravestone(ThisAgent);");\n'
                              '$Monster_Gravestone(ThisAgent);')
        stock = items(death=death)
        result = composed(stock)
        self.assert_only_hooks_added(death, result["controlled_monster_death"].text)

    def test_installed_steam_and_gog_stock_original_and_rendered(self):
        found = False
        for game in INSTALLS:
            root = game / "SDK/OriginalQuests/GPLMx"
            if not root.is_dir():
                continue
            found = True
            stock = tuple(parse_gpl((root / relative).read_text(encoding="cp1252"))
                          .require("function", name) for name, relative in STOCK_FILES.items())
            # The fixtures document the exact stock lifecycle in both SDKs.
            for installed, fixture in zip(stock, items()):
                self.assertEqual(_Parser(installed.text).function(), _Parser(fixture.text).function())
            for normalize in (False, True):
                selected = tuple(replace(item, text=rendered(item.text)) if normalize else item
                                 for item in stock)
                with self.subTest(game=game, normalize=normalize):
                    result = composed(selected)
                    for item in selected:
                        self.assert_only_hooks_added(item.text, result[item.normalized_name].text)
        if not found:
            self.skipTest("installed stock GPL source not available")


if __name__ == "__main__":
    unittest.main()
