"""Saved GPL state and guarded stock award insertions for kingdom research."""
from __future__ import annotations

from dataclasses import replace
import re

from .gpl import DefinitionKind, SemanticMergeResult, _mask_non_code, parse_gpl
from .kingdom_research import validate_registration


_COMMON = '''
function MM_KR_Live(agent Unit) is boolean
declare
begin
    if ($IsValidGamePiece(Unit) == False) return False;
    return ($IsDead(Unit) == False);
end

function MM_KR_HasPlayer(list Players, integer Player) is boolean
declare
    integer Index;
begin
    Index = 1;
    while (Index <= $ListSize(Players)) do
        begin
            if ($ListMember(Players, Index) == Player) return True;
            Index += 1;
        end
    return False;
end

'''


def feature_source(record, parent_building):
    validate_registration(record)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", parent_building) is None:
        raise ValueError("invalid kingdom research parent name")
    key = record.callback_symbol
    visual = visual_source(record, parent_building) if record.active_effector else ""
    remember_player = "CompletedPlayer = PendingPlayer;" if visual else ""
    completed_visuals = (f"if ((Operation == 2) && Matched) ${key}_Visuals(Building, CompletedPlayer);"
                         if visual else "")
    # Each saved list has a fixed, documented shape. No timers, unit pointers,
    # effects or process-local ledgers own completion, reservations or carry.
    return f'''
function {key}_Root() is agent
declare
    agent Root;
begin
    Root = $RetrieveAgent("GplAIRoot");
    if ($HasAttribute("{key}_done", Root) == False)
        begin
            $AddAttribute(Root, "{key}_done", "list");
            $AddAttribute(Root, "{key}_pending", "list");
            $AddAttribute(Root, "{key}_available", "list");
        end
    return Root;
end

function {key}_Building(agent Building) is boolean
declare
begin
    if ($MM_KR_Live(Building) == False) return False;
    // Native family/readiness evidence prevents another unit with a matching
    // script title from qualifying, including a borrowed positive-cache entry.
    return ($MM_KR_Eligible(Building, {record.action_control_id}) == 1);
end

// Operation: 0 status, 1 reserve before stock debit, 2 stock completion,
// 3 failed submission/cancellation. Status: 0 available, 1 done, 2 busy,
// 3 invalid. Pending records are (paying player, borrowed building agent).
{visual}
function {key}(agent Building, integer Operation) is integer
declare
    agent Root, PendingBuilding;
    list Pending, Kept, Completed;
    integer Index, Player, PendingPlayer{', CompletedPlayer' if visual else ''};
    boolean Busy, Matched;
begin
    if ($IsValidGamePiece(Building) == False) return 3;
    Root = ${key}_Root();
    Player = $GetUnitPlayerNumber(Building);
    Pending = Root's "{key}_pending";
    Completed = Root's "{key}_done";
    Index = 1;
    Busy = False;
    Matched = False;
    while (Index <= $ListSize(Pending)) do
        begin
            PendingPlayer = $ListMember(Pending, Index);
            PendingBuilding = $ListMember(Pending, Index + 1);
            if ((PendingBuilding == Building) && ((Operation == 2) || (Operation == 3)))
                begin
                    Matched = True;
                    {remember_player}
                    if (Operation == 2)
                        if ($MM_KR_HasPlayer(Completed, PendingPlayer) == False)
                            Completed << PendingPlayer;
                end
            else
                if ($MM_KR_Live(PendingBuilding))
                    if ($MM_KR_Order(PendingBuilding, {record.action_control_id}) == 1)
                        begin
                            Kept << PendingPlayer;
                            Kept << PendingBuilding;
                            if (PendingPlayer == Player) Busy = True;
                        end
            Index += 2;
        end
    Root's "{key}_pending" = Kept;
    Root's "{key}_done" = Completed;
    {completed_visuals}
    if ((Operation == 2) || (Operation == 3))
        begin
            if (Matched) return 1;
            return 3;
        end
    if ($MM_KR_HasPlayer(Completed, Player)) return 1;
    if (Busy) return 2;
    if (${key}_Building(Building) == False) return 3;
    if (Operation == 1)
        begin
            Kept << Player;
            Kept << Building;
            Root's "{key}_pending" = Kept;
        end
    return 0;
end

// Positive cache only. Every award revalidates the borrowed building. A miss
// uses the stock owner/title-filtered query and caches only a qualifying result.
function {key}_Active(agent Hero) is boolean
declare
    agent Root, Building, Found;
    list Completed, Available, Kept, Candidates;
    integer Player, Index, CachedPlayer;
begin
    if ($MM_KR_Live(Hero) == False) return False;
    if (Hero's "subtype" != "Hero") return False;
    Root = ${key}_Root();
    Player = $GetUnitPlayerNumber(Hero);
    Completed = Root's "{key}_done";
    if ($MM_KR_HasPlayer(Completed, Player) == False) return False;
    Available = Root's "{key}_available";
    Index = 1;
    while (Index <= $ListSize(Available)) do
        begin
            CachedPlayer = $ListMember(Available, Index);
            Building = $ListMember(Available, Index + 1);
            if (CachedPlayer == Player)
                begin
                    if (${key}_Building(Building))
                        if ($GetUnitPlayerNumber(Building) == Player) return True;
                end
            else
                begin
                    Kept << CachedPlayer;
                    Kept << Building;
                end
            Index += 2;
        end
    $ListObjects(Hero, "Building", -1, Candidates, #CheckTitles,
        "{parent_building}", #MyPlayer, #NoHiddenMap, #ATTRIB_FirstStageBuilt, 1);
    Index = 1;
    Found = $NullAgent();
    while (Index <= $ListSize(Candidates)) do
        begin
            Building = $ListMember(Candidates, Index);
            if (${key}_Building(Building))
                if ($GetUnitPlayerNumber(Building) == Player)
                    begin
                        Found = Building;
                        Index = $ListSize(Candidates);
                    end
            Index += 1;
        end
    if (Found != $NullAgent())
        begin
            Kept << Player;
            Kept << Found;
        end
    Root's "{key}_available" = Kept;
    return (Found != $NullAgent());
end

function {key}_Bonus(agent Hero, integer Base, integer Currency) is integer
declare
    integer Percent, Carry, Bonus;
begin
    if (Currency == 0) Percent = {record.gold_bonus_percent};
    else Percent = {record.experience_bonus_percent};
    if (Percent == 0) return 0;
    if (${key}_Active(Hero) == False) return 0;
    if ($HasAttribute("{key}_gold", Hero) == False)
        begin
            $AddAttribute(Hero, "{key}_gold", "integer", 0);
            $AddAttribute(Hero, "{key}_xp", "integer", 0);
        end
    if (Currency == 0) Carry = Hero's "{key}_gold";
    else Carry = Hero's "{key}_xp";
    // Native integer storage avoids GPL's lossy fixed-point binary operators.
    Bonus = $MM_KR_AwardBonus(Base, Percent, Carry);
    if (Currency == 0) Hero's "{key}_gold" = Carry;
    else Hero's "{key}_xp" = Carry;
    return Bonus;
end
'''


def visual_source(record, parent_building):
    key = record.callback_symbol
    return f'''
// Idempotent stock effector ownership: the saved purchase is authoritative,
// never the presence of its cosmetic overlay. Native lifecycle events call
// this only after the original building operation has completed.
function {key}_Visual(agent Building) is integer
declare
    agent Root;
    boolean Active, Present;
begin
    if ($MM_KR_Live(Building) == False) return 0;
    Root = ${key}_Root();
    Active = False;
    if (${key}_Building(Building))
        Active = $MM_KR_HasPlayer(Root's "{key}_done", $GetUnitPlayerNumber(Building));
    Present = $CheckEffector(Building, "{record.active_effector}");
    if (Active)
        begin
            if (Present == False)
                $CreateEffector(Building, "{record.active_effector}", 1, "Infinite");
        end
    else
        if (Present) $DeleteEffector(Building, "{record.active_effector}");
    return 1;
end

// One purchase-completion query, not a watcher. The original payer may differ
// from the completing building's current owner, so filter that saved player.
function {key}_Visuals(agent Origin, integer Player)
declare
    list Buildings;
    agent Building;
    integer Index;
begin
    // Stock ListObjects deliberately excludes its origin. Reconcile the
    // researching building explicitly, then use the native query for others.
    if ($GetUnitPlayerNumber(Origin) == Player) ${key}_Visual(Origin);
    $ListObjects(Origin, "Building", -1, Buildings, #CheckTitles,
        "{parent_building}", #NoHiddenMap, #ATTRIB_FirstStageBuilt, 1);
    Index = 1;
    while (Index <= $ListSize(Buildings)) do
        begin
            Building = $ListMember(Buildings, Index);
            if ($GetUnitPlayerNumber(Building) == Player) ${key}_Visual(Building);
            Index += 1;
        end
end
'''


def service_source(bindings):
    """Bindings are (resolved record, validated source building name)."""
    bindings = tuple(sorted(bindings, key=lambda item: item[0].identity))
    if not bindings:
        return ""
    identities = [record.identity for record, _ in bindings]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate kingdom research service identity")
    parts = [_COMMON]
    parts.extend(feature_source(record, parent) for record, parent in bindings)
    for name, currency in (("Gold", 0), ("XP", 1)):
        calls = "\n".join(
            f"    Result = $MM_KR_CapAdd(Result, ${record.callback_symbol}_Bonus(Hero, Base, {currency}));"
            for record, _ in bindings
        )
        parts.append(f'''
function MM_KR_{name}(agent Hero, integer Base) is integer
declare
    integer Result;
begin
    Result = Base;
{calls}
    return Result;
end
''')
    return "\n".join(parts)


def _insert_award(item, gold):
    code = _mask_non_code(item.text)
    name, argument = ("give_gold", "amount") if gold else ("give_exp", "new_exp")
    if not re.match(r'\s*function\s+' + name + r'\s*\(\s*agent\s+thisagent\s*,\s*integer\s+' + argument + r'\s*\)', code, re.I):
        raise ValueError(f"{name} changed its stock recipient/award signature")
    if re.search(r"\bmm_kr_", code, re.I):
        raise ValueError("stock award already contains a kingdom research insertion")
    if gold:
        # Require the original positive branch and its exact first side effect.
        anchor = re.compile(r'\bif\s*\(\s*amount\s*>\s*0\s*\)\s*begin\s*', re.I)
        matches = list(anchor.finditer(code))
        if len(matches) != 1:
            raise ValueError("give_gold no longer has one stock positive-award branch")
        offset = matches[0].end()
        # _mask_non_code preserves offsets but replaces strings/comments.
        tail = item.text[offset:]
        if not re.match(r'\$createeffector\s*\(\s*thisagent\s*,\s*"got_gold"\s*,\s*0\s*,\s*amount\s*\)', tail, re.I):
            raise ValueError("give_gold changed the stock display-before-credit boundary")
        insertion = "Amount = $MM_KR_Gold(ThisAgent, Amount);\n\t\t\t"
    else:
        anchor = re.compile(r'\bnew_exp\s*=\s*new_exp\s*/\s*exp_level\s*;', re.I)
        matches = list(anchor.finditer(code))
        if len(matches) != 1:
            raise ValueError("give_exp no longer has one stock level-divisor boundary")
        offset = matches[0].end()
        insertion = "\n\tnew_exp = $MM_KR_XP(ThisAgent, new_exp);"
    return replace(item, text=item.text[:offset]+insertion+item.text[offset:],
                   source_name="<manager kingdom research award>", span=None)


def compose_service(result, bindings, stock_awards):
    """Preserve all stock payout/divisor/callback ordering; add no other hooks."""
    source = service_source(bindings)
    if not source:
        return result
    parsed = parse_gpl(source, source_name="<manager kingdom research service>")
    exports = {item.key for item in parsed.items}
    if exports & {item.key for item in result.items} or any(
            item.normalized_name.startswith("mm_kr_") for item in result.items):
        raise ValueError("package collides with reserved kingdom research service symbols")
    items = list(result.items)
    for name, gold in (("give_gold", True), ("give_exp", False)):
        stock = stock_awards.get(name)
        if stock is None or stock.kind is not DefinitionKind.FUNCTION:
            raise ValueError(f"kingdom research requires installed stock {name}")
        matches = [index for index, item in enumerate(items) if item.key == stock.key]
        if len(matches) > 1:
            raise ValueError(f"multiple resolved {name} definitions")
        index = matches[0] if matches else len(items)
        updated = _insert_award(items[index] if matches else stock, gold)
        if matches:
            items[index] = updated
        else:
            items.append(updated)
    return SemanticMergeResult((*items, *parsed.items), result.conflicts)
