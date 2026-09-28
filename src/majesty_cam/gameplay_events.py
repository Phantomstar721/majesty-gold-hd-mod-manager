"""Opt-in observers at audited stock GPL success/consumption boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Mapping, Sequence

from .gpl import (DefinitionKind, SemanticItem, SemanticMergeResult,
                  _mask_non_code, parse_gpl)
from .gpl_function_merge import _Node, _SourceParser, _tokens, _unparen
from .shared_features import EVENT_SIGNATURES, StockGameplayEventObserver
from .event_boundaries import EventBoundary

STOCK_EVENT_FILES = {
    "shapeshift_potion_end": "TaskModules/Subtasks/mx_Spells.gpl",
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
    "give_gold": "mx_Monster_Deaths.gpl",
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
    "source-terrain-revealed": (),
}


def event_stock_paths(features) -> tuple[Path, ...]:
    """Only selected event owners add stock source inputs to a build plan."""
    features = tuple(features)
    paths = {
        STOCK_EVENT_FILES[name]
        for feature in features if isinstance(feature, StockGameplayEventObserver)
        for name in EVENT_FUNCTIONS[feature.event]
    }
    if any(getattr(feature, "type", "") == "stock.bazaar-potion-policy.v1" for feature in features):
        paths.update(("TaskModules/Buildings/Magic_Bazaar.gpl", "TaskModules/Subtasks/mx_Spells.gpl"))
    return tuple(Path("SDK/OriginalQuests/GPLMx") / relative for relative in sorted(paths))

# Strings must remain literal: masking them would admit a changed item identity
# or attribute while claiming it is stock. Only comments/spacing/case of code
# identifiers are immaterial for the stock-boundary comparison.
_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/|'
                     r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s]", re.MULTILINE)


def stock_tokens(text: str) -> tuple[str, ...]:
    return tuple(token if token.startswith('"') else token.casefold()
                 for token in _TOKENS.findall(text)
                 if not token.startswith(("//", "/*")))


def _additive_title_reference(reference: str, current: str):
    """Expand only literal title-disjunction tails; callers prove all other code.

    No new predicate, reordered/removed stock title, duplicate title or call is
    accepted. Return the expanded stock source and its registration signature.
    The same signature must be proved on the stock expiry owner.
    """
    def conditions(text):
        matches = [m for m in _TOKENS.finditer(text)
                   if not m.group().startswith(("//", "/*"))]
        tokens = stock_tokens(text)
        found = []
        for i in range(len(tokens) - 2):
            if tokens[i:i+2] != ("if", "("):
                continue
            j, titles = i + 2, []
            while (tokens[j:j+3] == ("title", "=", "=")
                   and j + 3 < len(tokens) and tokens[j+3].startswith('"')):
                titles.append(tokens[j+3])
                j += 4
                if tokens[j:j+2] != ("|", "|"):
                    break
                j += 2
            if len(titles) >= 2 and tokens[j:j+1] == (")",):
                found.append((tuple(titles), matches[i+2].start(), matches[j].start()))
        return found
    before, after = conditions(reference), conditions(current)
    if not before or len(before) != len(after):
        return None
    changes, expanded = [], reference
    for (old, start, end), (new, _, _) in reversed(list(zip(before, after))):
        if new[:len(old)] != old or len(set(new)) != len(new):
            return None
        if new != old:
            changes.append((old, new))
            expanded = expanded[:start] + " || ".join("title == " + title for title in new) + " " + expanded[end:]
    return expanded, tuple(reversed(changes))


def _potion_consumption_boundaries(editor):
    """Observe actual consume/forget pairs, not the selected potion's effects.

    Preserve the entry guard and exact item, spell and recipient arguments.
    The selected effects remain author-owned. Notify on completion of every
    path that consumed the item, including explicit early returns.
    """
    def is_call(node, symbol):
        return node.kind == "statement" and node.head[:2] == ("$" + symbol, "(")
    reference = editor.stock_body
    indices = [i for i, node in enumerate(reference) if is_call(node, "deleteinventoryitem")]
    if (len(indices) != 1 or indices[0] + 1 >= len(reference)
            or not is_call(reference[indices[0] + 1], "forgetspell")):
        editor.fail("stock potion must have one adjacent consume/forget pair")
    pair = reference[indices[0]:indices[0]+2]
    guard = reference[0]
    if (guard.head != _tokens('if ($IsDead(ThisAgent))')
            or guard.body != (_Node("statement", ("return", ";")),) or guard.otherwise
            or not editor.body):
        editor.fail("potion dead-caster guard changed")
    normal = [node for node in editor.body if is_call(node, "deleteinventoryitem")]
    if len(normal) != 1:
        editor.fail("potion must have one unconditional consume/forget pair")
    editor.guard_before('if ($IsDead(ThisAgent))', normal[0])
    editor.types((*pair[0].head, *pair[1].head))
    consumed, forgotten = [], []
    for node, path, siblings, index in editor.actual_entries:
        if is_call(node, "deleteinventoryitem"):
            consumed.append(node)
            if tuple(siblings[index:index+2]) != pair:
                editor.fail("potion item, recipient or forget-spell pairing changed")
            if path:
                if (path[-1][0] != "if" or path[-1][2] != "body"
                        or any(kind != "if" for kind, _, _ in path)
                        or siblings != (*pair, _Node("statement", ("return", ";")))
                        or editor.offset(node) > editor.offset(normal[0])):
                    editor.fail("additional potion consumption must be a consume-only conditional return")
                editor.guard_before('if ($IsDead(ThisAgent))', node)
            forgotten.append(siblings[index+1])
    tokens = _tokens(editor.current.text)
    if (tokens.count("$deleteinventoryitem") != len(consumed)
            or tokens.count("$forgetspell") != len(forgotten)):
        editor.fail("unpaired or indirect potion consumption")
    if any(token == "thisagent" and tokens[index+1:index+2] in
           (("=",), ("+=",), ("-=",), ("*=",), ("/=",))
           for index, token in enumerate(tokens)):
        editor.fail("potion callback reassigns its recipient")
    if any(editor.offset(node) > editor.offset(normal[0]) and editor.destroys_recipient(node)
           for node, *_ in editor.actual_entries):
        editor.fail("potion completion destroys its notification recipient")
    # Normal consumption is observed after the selected remaining application
    # work, not after a stock-only tail. A return skips the function-end call.
    positions = [(node, True) for node in forgotten
                 if editor.offset(node) < editor.offset(normal[0])]
    positions.extend((node, False) for node, *_ in editor.actual_entries
                     if node.head == ("return", ";")
                     and editor.offset(node) > editor.offset(normal[0]))
    if editor.body[-1].head != ("return", ";"):
        positions.append((editor.body[-1], True))
    return tuple(positions)


def require_callback(item: SemanticItem, symbol: str, types: Sequence[str],
                     boolean: bool = False) -> None:
    args = r"\s*,\s*".join(kind + r"\s+[A-Za-z_][A-Za-z0-9_]*" for kind in types)
    returns = r"\s+is\s+boolean" if boolean else ""
    pattern = (r"\s*function\s+" + re.escape(symbol) + r"\s*\(\s*" + args
               + r"\s*\)" + returns + r"\s*(?:declare|begin)\b")
    if not re.match(pattern, _mask_non_code(item.text), re.IGNORECASE):
        raise ValueError(f"shared callback {symbol!r} requires ({', '.join(types)})"
                         + (" is boolean" if boolean else " with no return value"))


def _healing_consumption_boundary(editor, source):
    """Accept an inline debit or its literal extraction into one void helper.

    The helper must be the sole statement in the original consumption branch,
    take the same agent, and finish straight-line work with exactly that debit.
    Returning from it is then the same notification boundary. Never rewrite a
    shared helper, observe its unrelated callers, or infer arbitrary call graphs.
    """
    instruction = '$AdjustAttribute(ThisAgent, #ATTRIB_NumHealingPotions, -1);'
    head = _tokens(instruction)
    references = [entry for entry in editor.stock_entries if entry[0].head == head]
    if len(references) != 1:
        editor.fail('stock healing consumption boundary is missing or ambiguous')
    reference = references[0]
    direct = [entry for entry in editor.actual_entries
              if entry[0].head == head and entry[1] == reference[1]]
    if direct:
        return editor.anchor(instruction)
    candidates = [node for node, path, siblings, _ in editor.actual_entries
                  if path == reference[1] and len(siblings) == 1
                  and editor.call_arguments(node) == (('thisagent',),)]
    if len(candidates) != 1:
        editor.fail('healing consumption requires the original debit or one direct helper '
                    'in the original potion branch')
    call = candidates[0]
    name = call.head[0][1:]
    if name in editor.locals:
        editor.fail(f'healing helper {name} is a local binding, not a direct source call')
    helper = source(name)
    if helper is None:
        editor.fail(f'healing helper {name} has no verifiable selected source')
    parser = _SourceParser(helper.text)
    signature, locals_, body = parser.function()
    if (len(signature) != 6 or signature[:4] != ('function', name, '(', 'agent')
            or signature[-1] != ')' or signature[4] in locals_):
        editor.fail(f'healing helper {name} must take one agent and return no value')
    actor = signature[4]
    if body and body[-1].head == ('return', ';'):
        body = body[:-1]
    debit = _tokens(f'$AdjustAttribute({actor}, #ATTRIB_NumHealingPotions, -1);')
    if (not body or body[-1].head != debit
            or any(node.kind != 'statement' or node.head[:1] == ('return',) for node in body)):
        editor.fail(f'healing helper {name} must finish straight-line work with the potion debit')
    # Refuse a second explicit debit, even with a different amount/recipient.
    adjustments = [node for node in body if node.head[:1] == ('$adjustattribute',)
                   and editor.call_arguments(node)[1:2] == (('#attrib_numhealingpotions',),)]
    if len(adjustments) != 1:
        editor.fail(f'healing helper {name} has ambiguous potion consumption')
    for node in body:
        tokens = node.head
        for index, token in enumerate(tokens):
            if token.startswith('$') and tokens[index+1:index+2] != ('(',):
                editor.fail(f'healing helper {name} contains indirect function dispatch')
            if token.startswith('$') and (token[1:] == name or token[1:] in locals_):
                editor.fail(f'healing helper {name} contains recursive or locally bound dispatch')
            if token in ('=', '+=', '-=', '*=', '/=', '++', '--'):
                lhs = tokens[:index] if index else tokens[index+1:-1]
                if _unparen(lhs) == (actor,):
                    editor.fail(f'healing helper {name} reassigns its recipient')
        if node.head[:1] in (('$deletegamepiece',), ('$henchman_dead',)):
            if editor.call_arguments(node)[:1] == ((actor,),):
                editor.fail(f'healing helper {name} destroys its recipient')
    return call


def add_gameplay_event_observers(
    result: SemanticMergeResult,
    subscribers: Mapping[str, Sequence[str]],
    stock: Mapping[str, SemanticItem],
    *, potion_aliases=None, source_loader=None,
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

    boundaries = {}
    def boundary(name):
        if name not in boundaries:
            reference = stock.get(name)
            if reference is None:
                raise ValueError(f'{name}: installed stock source is required for event composition')
            boundaries[name] = EventBoundary(functions.get(name, reference), reference)
        return boundaries[name]

    def save_boundary(editor):
        save(editor.current, editor.text())

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
         "exp_given / new_exp_div"),
        ("exploration-experience-awarded", "travel_to_exp", "MM_Event_ExploreXP",
         "#explore_exp"),
    ):
        if event not in requested:
            continue
        editor = boundary(name)
        instruction = f'$give_exp(thisagent, {argument});'
        award = editor.anchor(instruction)
        # Replace only the audited recipient call, inside its original branch.
        # The argument is evaluated once, before give_exp can change a level.
        # Familiar awards and all unrelated give_exp callers stay unobserved.
        editor.edit(award, lambda text: re.sub(r"\$give_exp\b", "$" + wrapper, text,
                                              count=1, flags=re.IGNORECASE))
        save_boundary(editor)
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
        def healing_source(name):
            # Authored/resolved functions win; missing helpers come through the
            # same verified, dataset-scoped native loader as other observers.
            return functions.get(name) or (source_loader(name) if source_loader else stock.get(name))
        for name in (*EVENT_FUNCTIONS["potion-consumed"], *(potion_aliases or {})):
            identity = (potion_aliases or {}).get(name, "healing_potion" if name.startswith("heal_self") else name[:-7])
            notify = calls("potion-consumed", f'ThisAgent, "{identity}"')
            if name.startswith("heal_self"):
                editor = boundary(name)
                consumed = _healing_consumption_boundary(editor, healing_source)
                editor.insert(consumed, '\n' + notify, after=True)
                save_boundary(editor)
                continue
            editor = boundary(name)
            for node, after in _potion_consumption_boundaries(editor):
                editor.insert(node, '\n' + notify + '\n', after=after)
            save_boundary(editor)

    payout_roots = {}
    if "reward-flag-paid" in requested or "attack-flag-completed" in requested:
        for name, original, private in (
            ("explore_flag_poll", "dropgoldinradius_sameplayer", "MM_Event_ExploreGold"),
            ("attack_flag_poll", "dropgoldinradius", "MM_Event_AttackGold"),
            ("attack_flag_death_callback", "dropgoldinradius", "MM_Event_DeathGold"),
        ):
            if name == 'explore_flag_poll' and 'reward-flag-paid' not in requested:
                continue
            editor = boundary(name)
            payout = editor.anchor(f'${original}(ThisAgent, $GetAttribute(ThisAgent, #ATTRIB_RewardCost));',
                                   callee_change=True) if 'reward-flag-paid' in requested else None
            completion = '$playsound(ThisAgent, "completed_reward", "begin");'
            if 'reward-flag-paid' in requested:
                callee = payout.head[0][1:]
                # A tiny private entry captures the FLAG, not a later target
                # passed by the selected mod's distribution helpers.
                generated(f'''function {private}(agent Flag, integer Amount)
declare
begin
    ${callee}(Flag, Amount);
end
''')
                payout_roots[private] = callee
                editor.edit(payout, lambda text, private=private: re.sub(
                    r'\$[A-Za-z_][A-Za-z0-9_]*', '$' + private, text, count=1))
            if name != 'explore_flag_poll' and 'attack-flag-completed' in requested:
                completed = editor.anchor(completion)
                committed = editor.anchor('ThisAgent\'s "gavereward" = TRUE;')
                editor.binding('target = $AgentNumber($GetAttribute(ThisAgent, #ATTRIB_TargetID));', completed)
                editor.ordered(completed, committed)
                editor.no_exit_between(completed, committed)
                if name == 'attack_flag_poll':
                    editor.guard_before('if ($isvalidgamepiece(thisagent) == FALSE)', completed)
                editor.insert(completed, calls('attack-flag-completed', 'ThisAgent, target') + '\n')
            save_boundary(editor)

    if payout_roots:
        from .source_context import SourceContextDispatch, compose as carry_source
        adapter = 'MM_Event_RewardPaid'
        generated(f'''function {adapter}(agent Flag, agent Recipient, integer Amount)
declare
begin
    $give_gold(Recipient, Amount);
''' + calls('reward-flag-paid', 'Flag, Recipient, Amount') + '\nend\n')
        def payout_source(name):
            # The complete selected function set wins; the loader supplies only
            # missing proven native helpers. Never substitute stock for a mod.
            key = (DefinitionKind.FUNCTION, name.casefold())
            return items.get(key) or (source_loader(name) if source_loader else stock.get(name))
        routed = carry_source(SemanticMergeResult(tuple(items.values()), ()),
            (SourceContextDispatch('reward_payment', 'give_gold', ('agent', 'integer'), adapter),),
            tuple(payout_roots), payout_source, namespace='MM_EG', strict=True)
        items = {item.key: item for item in routed.items}

    if "caravan-delivered" in requested:
        editor = boundary('caravan_go_trade')
        instruction = '$henchman_dead(ThisAgent, ThisAgent);'
        delivered = editor.anchor(instruction)
        transfer = editor.anchor('$Transfer_Gold(ThisAgent, Target, $GetAttribute(ThisAgent, #ATTRIB_Gold));')
        amount = editor.anchor('$SetAttribute(ThisAgent, #ATTRIB_Gold, Gold_To_Give);')
        editor.binding('Target = ThisAgent\'s "Target";', delivered)
        editor.ordered(amount, transfer, delivered)
        editor.stable('Gold_To_Give', amount, delivered)
        editor.stable('ThisAgent', transfer, delivered)
        for node, *_ in editor.actual_entries:
            if (editor.offset(amount) < editor.offset(node) < editor.offset(transfer)
                    and node.head[:1] in (('$setattribute',), ('$adjustattribute',))
                    and editor.call_arguments(node)[:2] == (('thisagent',), ('#attrib_gold',))):
                editor.fail('notification amount no longer matches the transferred gold')
        editor.no_exit_between(transfer, delivered)
        editor.insert(delivered, calls('caravan-delivered', 'ThisAgent, Target, Gold_To_Give') + '\n')
        save_boundary(editor)

    if "tournament-completed" in requested:
        # Only replace the timed continuation, never Exit_Fair's selected
        # gameplay. Ejection continues to call Exit_Fair without notification.
        exit_item = functions.get('exit_fair', stock.get('exit_fair'))
        if exit_item is None:
            raise ValueError('Exit_Fair: selected continuation is missing')
        require_callback(exit_item, 'Exit_Fair', ('agent',))
        editor = boundary('enter_tourney')
        continuation = editor.anchor('ThisAgent\'s "ActiveScript" = $Exit_Fair;')
        participant = editor.anchor('$SetAttribute(ThisAgent, #ATTRIB_ContestantInFair, 1);')
        timing = editor.anchor('$SetThreadInterval(ThisAgent\'s "ActiveScript", #compete_at_fair_duration);')
        editor.ordered(participant, timing, continuation)
        editor.no_exit_between(participant, continuation)
        editor.edit(continuation, lambda text: re.sub(r'\$Exit_Fair\b', '$MM_Event_FairFinished', text, flags=re.IGNORECASE))
        save_boundary(editor)
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
    if "source-terrain-revealed" in requested:
        from .exploration_events import service_source
        generated(service_source(requested["source-terrain-revealed"]))
    return SemanticMergeResult(tuple(items.values()), result.conflicts)
