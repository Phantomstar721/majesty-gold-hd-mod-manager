"""Building-employment admission, queries and stock-derived private lifecycle."""
from __future__ import annotations
from dataclasses import dataclass, replace
import re
from .stock_controller_features import StockMx05LiveAgentListPanel

FEATURE_TYPE = "stock.building-employment.v1"
TRAVEL_FUNCTIONS = ("use_building", "travel_to", "has_arrived", "gettargetrange")
AUTHOR_FIELDS = {"type", "feature_key", "api_prefix", "parent_building", "source_dialog_id",
                 "open_command_id", "gated_control_ids", "hero_titles", "minimum_level",
                 "eligibility_callback_symbol", "cleanup_callback_symbol", "visitor_callback_symbol"}


@dataclass(frozen=True)
class BuildingEmployment(StockMx05LiveAgentListPanel):
    feature_key: str = ""
    api_prefix: str = ""
    gated_control_ids: tuple[int, ...] = ()
    hero_titles: tuple[str, ...] = ()
    minimum_level: int = 1
    eligibility_callback_symbol: str = ""
    cleanup_callback_symbol: str = ""
    visitor_callback_symbol: str = ""
    travel_text: str | None = None
    travel_text_id: int = 0
    type: str = FEATURE_TYPE

    @property
    def admission_callback_symbol(self):
        return "MM_" + self.api_prefix + "_Admit"


def parse_feature(value):
    fields = AUTHOR_FIELDS
    if not isinstance(value, dict) or set(value) - {"travel_text"} != fields or value.get("type") != FEATURE_TYPE:
        raise ValueError("building employment requires the complete v1 declaration")
    if "travel_text" in value:
        text = value["travel_text"]
        if not isinstance(text, str) or not text or "\x00" in text:
            raise ValueError("employment travel_text must be nonempty text")
        try:
            encoded = text.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ValueError("employment travel_text must be Windows-1252") from exc
        if len(encoded) > 96:
            raise ValueError("employment travel_text is limited to 96 bytes")
    for key in ("feature_key", "api_prefix", "parent_building",
                "eligibility_callback_symbol", "cleanup_callback_symbol", "visitor_callback_symbol"):
        pattern = r"[A-Za-z][A-Za-z0-9_.-]{0,63}" if key == "feature_key" else r"[A-Za-z_][A-Za-z0-9_]{0,47}"
        if not isinstance(value[key], str) or not re.fullmatch(pattern, value[key]):
            raise ValueError("invalid building employment " + key)
        if value[key].lower().startswith("mm_"):
            raise ValueError("building employment author symbols must not use MM_ names")
    dialog = value["source_dialog_id"]
    if len(value["api_prefix"]) > 32:
        raise ValueError("employment api_prefix is limited to 32 characters")
    if not isinstance(dialog, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", dialog):
        raise ValueError("employment source_dialog_id must be a private FourCC")
    if dialog.upper() == "MX05":
        raise ValueError("employment selector must not replace stock MX05")
    commands = value["gated_control_ids"]
    if not isinstance(commands, (list, tuple)) or not 1 <= len(commands) <= 16:
        raise ValueError("employment requires one through sixteen gated primary controls")
    all_commands = (value["open_command_id"], *commands)
    if any(type(c) is not int or not 1 <= c <= 65535 for c in all_commands):
        raise ValueError("employment controls must be positive uint16 identifiers")
    # Stock Basic upgrades, close/back and list controls are not employment gates.
    if {0x1F47, 0x1F4D, 0x1F40, 0x1F41, 0x1388, 0x138B} & set(all_commands):
        raise ValueError("employment cannot gate stock upgrade/navigation controls")
    if len(set(all_commands)) != len(all_commands):
        raise ValueError("employment Hire and gated controls must be distinct")
    titles = value["hero_titles"]
    if not isinstance(titles, (list, tuple)) or not 1 <= len(titles) <= 32:
        raise ValueError("employment requires one through thirty-two hero titles")
    if any(not isinstance(t, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", t) for t in titles):
        raise ValueError("invalid employment hero title")
    if len({t.casefold() for t in titles}) != len(titles):
        raise ValueError("duplicate employment hero title")
    if type(value["minimum_level"]) is not int or not 1 <= value["minimum_level"] <= 100:
        raise ValueError("invalid employment minimum_level")
    p = "MM_" + value["api_prefix"]
    return BuildingEmployment(**{**value, "gated_control_ids": tuple(commands), "hero_titles": tuple(titles)},
        panel_key=value['feature_key'], row_count_callback_symbol=p+'_RowCount',
        row_agent_id_callback_symbol=p+'_RowAgentId', revision_callback_symbol=p+'_Revision',
        row_title_text=None, row_text=None, row_value_callback_symbol=None,
        row_value_suffix_text=None, action_cost_callback_symbol=p+'_Cost',
        action_callback_symbol=p+'_Action', action_agent_scope='parent-and-selected-row')


def feature_mapping(feature):
    result = {key: getattr(feature, key) for key in AUTHOR_FIELDS}
    result["gated_control_ids"] = list(feature.gated_control_ids)
    result["hero_titles"] = list(feature.hero_titles)
    if feature.travel_text is not None:
        result["travel_text"] = feature.travel_text
    parse_feature(result)
    return result


def validate_owner_callbacks(feature, sources):
    """Validate current owner source, not package-byte identity or pinned hashes."""
    from .gpl import DefinitionKind
    from .spell_policy import signature
    expected = {
        feature.eligibility_callback_symbol: (("agent", "agent"), "boolean"),
        feature.cleanup_callback_symbol: (("agent", "agent"), ""),
        feature.visitor_callback_symbol: (("agent",), ""),
    }
    if len({name.casefold() for name in expected}) != 3:
        raise ValueError("employment callbacks must have distinct identities")
    for name, shape in expected.items():
        definitions = [item for source in sources for item in source.items
                       if item.kind is DefinitionKind.FUNCTION and item.normalized_name == name.casefold()]
        if len(definitions) != 1:
            raise ValueError("employment callback missing, ambiguous or wrong signature: " + name)
        signature(definitions[0], *shape)


def selected(inventories):
    return tuple(resolve_travel_text(feature, inventory.selected.package.mod_id) for inventory in inventories
                 for feature in getattr(getattr(getattr(inventory.selected, "package", None),
                                                 "definition", None), "runtime_features", ())
                 if isinstance(feature, BuildingEmployment))


def resolve_travel_text(feature, mod_id):
    from .intent_text import allocate_private_literal_text_id
    return replace(feature, travel_text_id=allocate_private_literal_text_id(
        mod_id, FEATURE_TYPE, feature.feature_key + ":travel") if feature.travel_text else 0)


def compose_service(result, features, stock_function_loader):
    """Add private functions using the destination dataset, without replacing stock.

    Production admission separately checks owner resources and callback contracts.
    """
    from .gpl import DefinitionKind, SemanticMergeResult, parse_gpl
    features = tuple(features)
    if not features:
        return result
    if stock_function_loader is None:
        raise ValueError("building employment requires destination stock travel sources")
    ancestors = stock_function_loader(TRAVEL_FUNCTIONS)
    stock = []
    for name in TRAVEL_FUNCTIONS:
        item = ancestors.get((DefinitionKind.FUNCTION, name))
        if item is None:
            raise ValueError("building employment stock travel source is missing: " + name)
        stock.append(item.text)
    stock_text = '\n'.join(stock)
    items = list(result.items)
    names = {item.normalized_name for item in items}
    prefixes, buildings, keys = set(), set(), set()
    sources = (parse_gpl('\n'.join(item.text for item in items)),)
    for feature in sorted(features, key=lambda f: f.feature_key.casefold()):
        feature_mapping(feature)
        for value, claimed, label in ((feature.api_prefix, prefixes, "API prefix"),
                                      (feature.parent_building, buildings, "building"),
                                      (feature.feature_key, keys, "feature key")):
            if value.casefold() in claimed:
                raise ValueError("building employment has more than one owner for " + label + ": " + value)
            claimed.add(value.casefold())
        validate_owner_callbacks(feature, sources)
        for item in parse_gpl(lifecycle_source(feature, stock_text)).items:
            if item.normalized_name in names:
                raise ValueError("generated employment function collides with source: " + item.name)
            names.add(item.normalized_name)
            items.append(item)
    return SemanticMergeResult(tuple(items), result.conflicts)


def validate_panel_resources(feature, game_path, parent_smnu, child_smnu, child_strt):
    """Reuse the stock MX05 resource contract without composing a profile."""
    from .compose import (_validate_mx05_live_agent_list_panel,
                          _split_smnu_records, _smnu_record_index)
    feature_mapping(feature)
    _validate_mx05_live_agent_list_panel(game_path, child_smnu, child_strt,
                                       owner=feature.feature_key, label=feature.source_dialog_id)
    records = _split_smnu_records(parent_smnu, owner=feature.feature_key, label="employment parent")
    for control in (feature.open_command_id, *feature.gated_control_ids):
        _smnu_record_index(records, control, owner=feature.feature_key, label="employment parent")


def query_source(feature):
    """Pure eligibility/state queries. No state initialization from presentation.

    ListObjects mirrors stock Building_Births, including heroes inside buildings.
    Both kingdom identity and package restrictions are checked on each row. The
    native list still resolves returned GPL IDs; these are not packet handles.
    """
    feature_mapping(feature)
    p = "MM_" + feature.api_prefix
    titles = " || ".join(f'(Hero\'s "Title" == "{t}")' for t in feature.hero_titles)
    return f'''function {p}_Unlocked(agent Building) is integer
declare
begin
    if ($IsValidGamePiece(Building) == False) return 0;
    if ($HasAttribute("{p}_UnlockedState", Building) == False) return 0;
    if (Building's "{p}_UnlockedState") return 1;
    return 0;
end

function {p}_Eligible(agent Hero, agent Building) is boolean
declare
begin
    if ($IsValidGamePiece(Building) == False) return False;
    if ($IsDead(Building)) return False;
    if (Building's "Title" != "{feature.parent_building}") return False;
    if ($GetAttribute(Building, #ATTRIB_FirstStageBuilt) != 1) return False;
    if (${p}_Unlocked(Building) != 0) return False;
    if ($IsValidGamePiece(Hero) == False) return False;
    if ($IsDead(Hero)) return False;
    if ($GetAttribute(Hero, #ATTRIB_HP) <= 0) return False;
    if (Hero's "Type" != "hero") return False;
    if (({titles}) == False) return False;
    if ($GetUnitPlayerNumber(Hero) != $GetUnitPlayerNumber(Building)) return False;
    if ($GetAttribute(Hero, #ATTRIB_ExperienceLevel) < {feature.minimum_level}) return False;
    return ${feature.eligibility_callback_symbol}(Hero, Building);
end

function {p}_Candidates(agent Building) is list
declare
    list Heroes, Candidates;
    agent Hero;
begin
    if ($IsValidGamePiece(Building) == False) return Candidates;
    if ($IsDead(Building)) return Candidates;
    $ListObjects(Building, "Hero", -1, Heroes, #MyPlayer, #insideOtherUnits);
    foreach Hero in Heroes do
        if (${p}_Eligible(Hero, Building)) Candidates << Hero;
    return Candidates;
end

function {p}_RowCount(agent Building) is integer
declare
    list Heroes;
    integer Count;
begin
    Heroes = ${p}_Candidates(Building);
    Count = $ListSize(Heroes);
    if (Count > 64) return 64;
    return Count;
end

function {p}_RowAgentId(agent Building, integer Row) is integer
declare
    list Heroes;
    agent Hero;
begin
    if (Row < 1 || Row > 64) return 0;
    Heroes = ${p}_Candidates(Building);
    if (Row > $ListSize(Heroes)) return 0;
    Hero = $ListMember(Heroes, Row);
    return $GetAttribute(Hero, #ATTRIB_AgentID);
end

function {p}_Cost(agent Hero) is integer
declare
begin
    return 0;
end

function {p}_Revision(agent Building) is integer
declare
    list Heroes;
    agent Hero;
    integer Revision, Row;
begin
    Revision = ${p}_Unlocked(Building);
    Heroes = ${p}_Candidates(Building);
    Row = 0;
    foreach Hero in Heroes do
        begin
            Row = Row + 1;
            if (Row > 64) return Revision;
            // A display-cache hint only. Selection always checks eligibility.
            // Bound each term before multiplication to avoid signed overflow.
            Revision = ((Revision * 31) + ($GetAttribute(Hero, #ATTRIB_AgentID) % 1000003)) % 60000001;
        end
    return Revision;
end
'''


def travel_source(feature, stock_use_building):
    """Privatize the destination's literal stock travel/entry continuation.

    No task-name marker authorizes completion. Reset_Tasks discards the private
    ActiveScript/BackScript, so an unrelated future shop visit cannot consume.
    The public use_building and the building's ordinary Visited_Script stay intact.
    """
    from .gpl import DefinitionKind, parse_gpl
    from .spell_policy import signature
    feature_mapping(feature)
    parsed = parse_gpl(stock_use_building)
    names = {"use_building": "Travel", "travel_to": "TravelTo",
             "has_arrived": "HasArrived", "gettargetrange": "TargetRange"}
    originals = [parsed.require(DefinitionKind.FUNCTION, name) for name in names]
    for original in originals:
        signature(original, ("agent", "boolean") if original.normalized_name == "has_arrived"
                  else ("agent",), "boolean" if original.normalized_name == "has_arrived"
                  else "integer" if original.normalized_name == "gettargetrange" else "")
    p = "MM_" + feature.api_prefix
    text = '\n'.join(original.text for original in originals)
    for name, suffix in names.items():
        text = re.sub(r'\bfunction\s+' + name + r'\b', 'function ' + p + '_' + suffix, text, flags=re.I)
        text = re.sub(r'\$' + name + r'\b', lambda _: '$' + p + '_' + suffix, text, flags=re.I)
    text, count = re.subn(r'''target's\s+"visited_script"''', lambda _: '$' + p + '_Arrive', text, flags=re.I)
    if count != 1:
        raise ValueError("employment stock visited_script boundary is missing or ambiguous")
    return text


def lifecycle_source(feature, stock_use_building):
    """Emit private travel, confirmed-entry completion and command admission."""
    p = "MM_" + feature.api_prefix
    gates = " || ".join(f'Command == {c}' for c in feature.gated_control_ids)
    if feature.travel_text and not feature.travel_text_id:
        raise ValueError("employment travel text must be resolved before generation")
    intent = f'$SpecifyIntent(Hero, {feature.travel_text_id});' if feature.travel_text_id else ''
    return query_source(feature) + '\n' + travel_source(feature, stock_use_building) + f'''

function {p}_Admit(agent Building, integer Command) is integer
declare
begin
    // Unrelated commands (including upgrade) keep their stock admission.
    if ((Command != {feature.open_command_id}) && (({gates}) == False)) return 1;
    if ($IsValidGamePiece(Building) == False) return 0;
    if ($IsDead(Building)) return 0;
    if (Building's "Title" != "{feature.parent_building}") return 0;
    if ($GetAttribute(Building, #ATTRIB_FirstStageBuilt) != 1) return 0;
    if (Command == {feature.open_command_id})
        begin
            if (${p}_Unlocked(Building) == 0) return 1;
            return 0;
        end
    return ${p}_Unlocked(Building);
end

function {p}_Select(agent Building, agent Hero) is integer
declare
    agent Previous;
begin
    if (${p}_Eligible(Hero, Building) == False) return 0;
    // Exit the actual current building before replacing Target, as stock
    // visitor transitions require. Never interpret the new target as the old.
    if ($InsideBuilding(Hero))
        begin
            Previous = Hero's "Target";
            if ($IsValidGamePiece(Previous) == False) return 0;
            if ($IsDead(Previous)) return 0;
            if ($AgentInList(Hero, Previous's "Occupants") == False) return 0;
            $Exit_Building(Hero, Previous);
        end
    $StopMoving(Hero);
    $Reset_Tasks(Hero);
    Hero's "Target" = Building;
    Hero's "TaskName" = "";
    Hero's "ActiveScript" = ${p}_Travel;
    Hero's "BackScript" = ${p}_Travel;
    {intent}
    return 1;
end

function {p}_Action(agent Building, agent Hero) is boolean
declare
begin
    return (${p}_Select(Building, Hero) == 1);
end

function {p}_Arrive(agent Hero)
declare
    agent Building, Home;
begin
    if ($IsValidGamePiece(Hero) == False) return;
    if ($IsDead(Hero)) return;
    // A stale label, shopper callback or canceled order cannot complete a hire.
    if (Hero's "ActiveScript" != ${p}_Arrive) return;
    if (Hero's "BackScript" != ${p}_Travel) return;
    Building = Hero's "Target";
    if ($IsValidGamePiece(Building) == False)
        begin
            $Reset_Tasks(Hero);
            return;
        end
    if ($IsDead(Building))
        begin
            $Reset_Tasks(Hero);
            return;
        end
    if ($InsideBuilding(Hero) == False)
        begin
            $Reset_Tasks(Hero);
            return;
        end
    if ($AgentInList(Hero, Building's "Occupants") == False) return;
    if (${p}_Eligible(Hero, Building) == False)
        begin
            $Exit_Building(Hero, Building);
            return;
        end
    // Owner callback retires its effects/claims, never a death/gravestone path.
    ${feature.cleanup_callback_symbol}(Hero, Building);
    Home = Hero's "Home";
    if ($IsValidGamePiece(Home))
        if ($IsDead(Home) == False)
            if ($HasAttribute("Members", Home))
                if ($AgentInList(Hero, Home's "Members")) Home's "Members" -= Hero;
    $CancelGuildMembership(Hero);
    $Hero_Drop_Quest_Items(Hero);
    if ($HasAttribute("{p}_UnlockedState", Building) == False)
        $AddAttribute(Building, "{p}_UnlockedState", "boolean", False);
    Building's "{p}_UnlockedState" = True;
    // Publish saved state before the stock relation-change UI notification.
    Building's "Occupants" -= Hero;
    Hero's "Type" = "Waiting_to_die";
    $KillThread(Hero's "ActiveScript");
    $DeleteGamePiece(Hero);
end
'''
