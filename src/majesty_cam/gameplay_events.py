"""Opt-in observers at audited stock GPL success/consumption boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Mapping, Sequence

from .gpl import (DefinitionKind, SemanticItem, SemanticMergeResult,
                  _mask_non_code, parse_gpl)
from .shared_features import EVENT_SIGNATURES, StockGameplayEventObserver

STOCK_EVENT_FILES = {
    "heal_self": "TaskModules/Subtasks/mx_heal_self.gpl",
    "heal_self_fleeing": "TaskModules/Subtasks/mx_heal_self.gpl",
    **{name + "_effect": "TaskModules/Subtasks/mx_Spells.gpl" for name in (
        "speed_tonic", "strength_potion", "shapeshift_potion",
        "regeneration_elixer", "invisibility_brew", "fire_balm")},
    "explore_flag_poll": "DecisionTrees/Modules/mx_check_rewards.gpl",
    "attack_flag_poll": "DecisionTrees/Modules/mx_check_rewards.gpl",
    "attack_flag_death_callback": "DecisionTrees/Modules/mx_check_rewards.gpl",
    "dropgoldinradius": "mx_Monster_Deaths.gpl",
    "dropgoldinradius_sameplayer": "mx_Monster_Deaths.gpl",
    "caravan_go_trade": "TaskModules/Characters/Henchmen/mx_caravan.gpl",
    "enter_tourney": "TaskModules/Buildings/mx_Fairgrounds.gpl",
    "exit_fair": "TaskModules/Buildings/mx_Fairgrounds.gpl",
    "attack_end": "TaskModules/Subtasks/mx_make_attack.gpl",
    "travel_to_exp": "TaskModules/Characters/mx_Travel_to.gpl",
}
EVENT_FUNCTIONS = {
    "potion-consumed": ("heal_self", "heal_self_fleeing", "speed_tonic_effect",
                        "strength_potion_effect", "shapeshift_potion_effect",
                        "regeneration_elixer_effect", "invisibility_brew_effect", "fire_balm_effect"),
    "reward-flag-paid": ("explore_flag_poll", "attack_flag_poll",
                         "attack_flag_death_callback", "dropgoldinradius",
                         "dropgoldinradius_sameplayer"),
    "attack-flag-completed": ("attack_flag_poll", "attack_flag_death_callback"),
    "caravan-delivered": ("caravan_go_trade",),
    "tournament-completed": ("enter_tourney", "exit_fair"),
    "combat-experience-awarded": ("attack_end",),
    "exploration-experience-awarded": ("travel_to_exp",),
}


def event_stock_paths(features) -> tuple[Path, ...]:
    """Only selected event owners add stock source inputs to a build plan."""
    return tuple(Path("SDK/OriginalQuests/GPLMx") / relative for relative in sorted({
        STOCK_EVENT_FILES[name]
        for feature in features if isinstance(feature, StockGameplayEventObserver)
        for name in EVENT_FUNCTIONS[feature.event]
    }))

# Strings must remain literal: masking them would admit a changed item identity
# or attribute while claiming it is stock. Only comments/spacing/case of code
# identifiers are immaterial for the stock-boundary comparison.
_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/|'
                     r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s]", re.MULTILINE)


def stock_tokens(text: str) -> tuple[str, ...]:
    return tuple(token if token.startswith('"') else token.casefold()
                 for token in _TOKENS.findall(text)
                 if not token.startswith(("//", "/*")))


def _early_consumption_returns(reference: str, current: str) -> tuple[int, ...] | None:
    """Prove inserted consume-only branches without accepting arbitrary rewrites.

    Stock's dead-caster guard, normal effects, consumption and cleanup must all
    remain literal. The only admitted addition is one or more conditional
    consume/forget/return blocks between that guard and the first effector.
    Predicates stay author-owned; no title, package ID or private type is known
    here. Return source offsets at which to observe the additional consumption.
    """
    expected = stock_tokens(reference)
    matches = [m for m in _TOKENS.finditer(current)
               if not m.group().startswith(("//", "/*"))]
    actual = tuple(m.group() if m.group().startswith('"') else m.group().casefold()
                   for m in matches)
    if actual == expected:
        return ()
    calls = lambda name: [i for i in range(len(expected) - 1)
                          if expected[i:i + 2] == ("$", name)]
    effects, consumed, forgotten = calls("createeffector"), calls("deleteinventoryitem"), calls("forgetspell")
    if not effects or len(consumed) != 1 or len(forgotten) != 1:
        return None
    start = effects[0]
    try:
        consumed_end = expected.index(";", consumed[0]) + 1
        forgotten_end = expected.index(";", forgotten[0]) + 1
    except ValueError:
        return None
    if consumed_end != forgotten[0] or actual[:start] != expected[:start]:
        return None
    body = expected[consumed[0]:forgotten_end] + ("return", ";", "end")
    cursor = start
    returns = []
    while actual[cursor:cursor + 2] == ("if", "("):
        condition = cursor + 2
        depth = 1
        while condition < len(actual) and depth:
            depth += (actual[condition] == "(") - (actual[condition] == ")")
            condition += 1
        if depth or actual[condition:condition + 1] != ("begin",):
            return None
        body_start = condition + 1
        if actual[body_start:body_start + len(body)] != body:
            return None
        returns.append(matches[body_start + len(body) - 3].start())
        cursor = body_start + len(body)
    if not returns or actual[:start] + actual[cursor:] != expected:
        return None
    return tuple(returns)


def _stock_preserving_prelude(reference: str, current: str) -> bool:
    """Allow straight-line callback preludes while retaining the entire stock body.

    Cloning an existing wrapper must also clone its prelude; dropping it would
    remove another mod's behavior from reward-flag calls. No branches, local
    changes, reordered stock statements or calls back into observed owners are
    admitted as a prelude.
    """
    expected, actual = stock_tokens(reference), stock_tokens(current)
    try:
        start = expected.index("begin") + 1
    except ValueError:
        return False
    if actual[:start] != expected[:start]:
        return False
    cursor = start
    while (cursor + 2 < len(actual) and actual[cursor] == "$"
           and re.fullmatch(r"[a-z_][a-z0-9_]*", actual[cursor + 1])
           and actual[cursor + 1] not in STOCK_EVENT_FILES
           and actual[cursor + 2] == "("):
        cursor += 3
        depth = 1
        while cursor < len(actual) and depth:
            depth += (actual[cursor] == "(") - (actual[cursor] == ")")
            if actual[cursor] == ";":
                return False
            cursor += 1
        if depth or actual[cursor:cursor + 1] != (";",):
            return False
        cursor += 1
        if actual[:start] + actual[cursor:] == expected:
            return True
    return False


def require_callback(item: SemanticItem, symbol: str, types: Sequence[str],
                     boolean: bool = False) -> None:
    args = r"\s*,\s*".join(kind + r"\s+[A-Za-z_][A-Za-z0-9_]*" for kind in types)
    returns = r"\s+is\s+boolean" if boolean else ""
    pattern = (r"\s*function\s+" + re.escape(symbol) + r"\s*\(\s*" + args
               + r"\s*\)" + returns + r"\s*(?:declare|begin)\b")
    if not re.match(pattern, _mask_non_code(item.text), re.IGNORECASE):
        raise ValueError(f"shared callback {symbol!r} requires ({', '.join(types)})"
                         + (" is boolean" if boolean else " with no return value"))


def _once(text: str, pattern: str, transform) -> str:
    masked = _mask_non_code(text)
    matches = [m for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
               if masked[m.start():m.end()].strip()]
    if len(matches) != 1:
        raise ValueError(f"stock event boundary is missing or ambiguous: {pattern}")
    match = matches[0]
    return text[:match.start()] + transform(match) + text[match.end():]


def add_gameplay_event_observers(
    result: SemanticMergeResult,
    subscribers: Mapping[str, Sequence[str]],
    stock: Mapping[str, SemanticItem],
) -> SemanticMergeResult:
    """Append every declared observer without replacing stock or another mod."""
    requested = {key: tuple(values) for key, values in subscribers.items() if values}
    if not requested:
        return result
    result.require_clean()
    items = {item.key: item for item in result.items}
    functions = {item.normalized_name: item for item in result.items
                 if item.kind is DefinitionKind.FUNCTION}
    for event, symbols in requested.items():
        if event not in EVENT_SIGNATURES:
            raise ValueError(f"unsupported gameplay event {event!r}")
        if len({s.casefold() for s in symbols}) != len(symbols):
            raise ValueError(f"duplicate {event} observer")
        for symbol in symbols:
            callback = functions.get(symbol.casefold())
            if callback is None:
                raise ValueError(f"missing package-owned {event} observer {symbol!r}")
            require_callback(callback, symbol, EVENT_SIGNATURES[event])

    def target(name: str) -> SemanticItem:
        reference = stock.get(name)
        if reference is None:
            raise ValueError(f"{name}: installed stock source is required for event composition")
        current = functions.get(name, reference)
        if (stock_tokens(current.text) != stock_tokens(reference.text)
                and not _stock_preserving_prelude(reference.text, current.text)):
            raise ValueError(f"{name} ({current.source_name}): selected source changes the stock gameplay-event owner; "
                             "its success/cleanup boundary cannot be safely combined")
        # Prove the authored input, then continue from any edits already made
        # by this composition. Two events can share one stock owner; starting
        # from `current` again would silently discard its earlier observers.
        return items.get(current.key, current)

    def save(item: SemanticItem, text: str) -> None:
        items[item.key] = replace(item, text=text, span=None,
                                  source_name="<Manager stock gameplay events>")

    def generated(text: str) -> None:
        for item in parse_gpl(text, "<Manager stock gameplay events>").items:
            if item.key in items:
                raise ValueError(f"generated gameplay-event symbol collides with package: {item.name}")
            items[item.key] = item

    def calls(event: str, arguments: str) -> str:
        return "\n".join(f"\t${symbol}({arguments});" for symbol in requested[event])

    for event, name, wrapper, argument in (
        ("combat-experience-awarded", "attack_end", "MM_Event_CombatXP",
         r"exp_given\s*/\s*new_exp_div"),
        ("exploration-experience-awarded", "travel_to_exp", "MM_Event_ExploreXP",
         r"#explore_exp"),
    ):
        if event not in requested:
            continue
        item = target(name)
        # Replace only the audited recipient call, inside its original branch.
        # The argument is evaluated once, before give_exp can change a level.
        # Familiar awards and all unrelated give_exp callers stay unobserved.
        save(item, _once(item.text,
            r"\$give_exp\s*\(\s*thisagent\s*,\s*" + argument + r"\s*\)\s*;",
            lambda m: re.sub(r"\$give_exp\b", "$" + wrapper, m.group(),
                             count=1, flags=re.IGNORECASE)))
        generated(f'''function {wrapper}(agent Recipient, integer Base)
declare
begin
    $give_exp(Recipient, Base);
    if (Base > 0)
        begin
''' + calls(event, "Recipient, Base") + '''
        end
end
''')

    if "potion-consumed" in requested:
        for name in EVENT_FUNCTIONS["potion-consumed"]:
            identity = "healing_potion" if name.startswith("heal_self") else name[:-7]
            notify = calls("potion-consumed", f'ThisAgent, "{identity}"')
            if name.startswith("heal_self"):
                item = target(name)
                text = _once(item.text,
                             r"\$AdjustAttribute\s*\(\s*ThisAgent\s*,\s*"
                             r"#ATTRIB_NumHealingPotions\s*,\s*-1\s*\)\s*;",
                             lambda m: m.group() + "\n" + notify)
            else:
                reference = stock.get(name)
                if reference is None:
                    target(name)  # Report the same missing-stock evidence error.
                item = functions.get(name, reference)
                extra_returns = _early_consumption_returns(reference.text, item.text)
                if extra_returns is None:
                    target(name)  # Preserve fail-closed handling for other rewrites.
                    extra_returns = ()
                text = item.text
                for position in reversed(extra_returns):
                    text = text[:position] + notify + "\n\t\t" + text[position:]
                # The early dead-caster return must bypass this normal tail.
                text = _once(text, r"\bend\s*\Z", lambda m: notify + "\n" + m.group())
            save(item, text)

    if "reward-flag-paid" in requested:
        for name, private in (("dropgoldinradius", "MM_Event_AttackGold"),
                              ("dropgoldinradius_sameplayer", "MM_Event_ExploreGold")):
            item = target(name)
            text = _once(item.text, r"\bfunction\s+" + name + r"\b",
                         lambda _: "function " + private)
            text = _once(text, r"\$give_gold\s*\(\s*guy\s*,\s*goldper\s*\)\s*;",
                         lambda m: "begin\n" + m.group() + "\n"
                         + calls("reward-flag-paid", "ThisAgent, guy, goldper") + "\nend")
            generated(text)
        for name, original, private in (
            ("explore_flag_poll", "dropgoldinradius_sameplayer", "MM_Event_ExploreGold"),
            ("attack_flag_poll", "dropgoldinradius", "MM_Event_AttackGold"),
            ("attack_flag_death_callback", "dropgoldinradius", "MM_Event_AttackGold"),
        ):
            item = target(name)
            save(item, _once(item.text, r"\$" + original + r"\b", lambda _: "$" + private))

    if "attack-flag-completed" in requested:
        for name in EVENT_FUNCTIONS["attack-flag-completed"]:
            item = target(name)
            save(item, _once(item.text,
                r'\$playsound\s*\(\s*thisagent\s*,\s*"completed_reward"\s*,\s*"begin"\s*\)\s*;',
                lambda m: calls("attack-flag-completed", "ThisAgent, target") + "\n" + m.group()))

    if "caravan-delivered" in requested:
        item = target("caravan_go_trade")
        save(item, _once(item.text, r"\$henchman_dead\s*\(\s*thisagent\s*,\s*thisagent\s*\)\s*;",
                         lambda m: calls("caravan-delivered", "ThisAgent, Target, Gold_To_Give")
                         + "\n" + m.group()))

    if "tournament-completed" in requested:
        # Validate Exit_Fair even though we retain it, since it owns payout and
        # cleanup. Dump_Contestants must keep calling it without notification.
        target("exit_fair")
        item = target("enter_tourney")
        save(item, _once(item.text, r'"ActiveScript"\s*=\s*\$Exit_Fair\s*;',
                         lambda _: '"ActiveScript" = $MM_Event_FairFinished;'))
        generated('''function MM_Event_FairFinished(agent ThisAgent)
declare
    agent Target;
    integer Event, Rank, Participants;
    boolean Completed;
begin
    Target = ThisAgent's "Target";
    Completed = False;
    if ($IsValidGamePiece(Target))
        if ($IsDead(Target) == False)
            if (Target's "Cleaning_Combatants" == False)
                if ($GetAttribute(ThisAgent, #ATTRIB_ContestantInFair) == 1)
                    if ($AgentInList(ThisAgent, Target's "Occupants"))
                        if (Target's "Current_Contest" == $GetAttribute(Target, #ATTRIB_CurrentEvent))
                            if (Target's "Current_XPLevel" == $GetAttribute(Target, #ATTRIB_MaxContestant))
                                if (ThisAgent's "counter" > 0)
                                    begin
                                        Event = Target's "Current_Contest";
                                        Rank = $GetAttribute(ThisAgent, #ATTRIB_ContestantRank);
                                        Participants = ThisAgent's "counter";
                                        Completed = True;
                                    end
    $Exit_Fair(ThisAgent);
    if (Completed)
        begin
''' + calls("tournament-completed", "ThisAgent, Target, Event, Rank, Participants") + '''
        end
end
''')
    return SemanticMergeResult(tuple(items.values()), result.conflicts)
