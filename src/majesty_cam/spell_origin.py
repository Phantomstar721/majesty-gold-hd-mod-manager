"""Opt-in saved hero identity for native CreateSpellUnit descendants."""
from dataclasses import dataclass, asdict
import re

FEATURE_TYPE = "stock.spell-origin.v1"
CAPABILITY = "manager.spell-origin.v1"


@dataclass(frozen=True)
class SpellOrigin:
    feature_key: str
    type: str = FEATURE_TYPE


def parse_feature(value):
    if (set(value) != {"type", "feature_key"} or value.get("type") != FEATURE_TYPE
            or not isinstance(value.get("feature_key"), str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", value["feature_key"])):
        raise ValueError("spell origin requires type and a bounded feature_key")
    return SpellOrigin(value["feature_key"])


def feature_mapping(feature):
    value = asdict(feature)
    parse_feature(value)
    return value


def selected(inventories):
    return any(isinstance(f, SpellOrigin) for inventory in inventories
               for f in getattr(getattr(getattr(inventory.selected, "package", None),
                                       "definition", None), "runtime_features", ()))


SOURCE = '''function MM_OriginalCaster(agent Subject) is agent
declare
    agent Caster;
begin
    if ($IsValidGamePiece(Subject) == False) return $nullagent();
    if ($HasAttribute("MM_SpellOrigin_v1", Subject))
        begin
            Caster = Subject's "MM_SpellOrigin_v1";
            if ($IsValidGamePiece(Caster)) return Caster;
            return $nullagent();
        end
    if ($HasAttribute("subtype", Subject))
        if (Subject's "subtype" == "hero") return Subject;
    return $nullagent();
end

function MM_SO_Record(agent Spell, agent Source) is integer
declare
    agent Caster;
begin
    if ($IsValidGamePiece(Spell) == False) return 0;
    Caster = $MM_OriginalCaster(Source);
    if ($HasAttribute("MM_SpellOrigin_v1", Spell)) return 0;
    $AddAttribute(Spell, "MM_SpellOrigin_v1", "agentref", Caster);
    if ($HasAttribute("MM_SpellOrigin_v1", Spell) == False) return 0;
    if (Spell's "MM_SpellOrigin_v1" != Caster) return 0;
    return 1;
end
'''


def compose_service(result, enabled):
    from .gpl import parse_gpl, SemanticMergeResult
    service = parse_gpl(SOURCE)
    owned = {i.normalized_name for i in service.items}
    if any(i.normalized_name in owned for i in result.items):
        raise ValueError("package defines a reserved spell-origin service function")
    if not enabled:
        return result
    return SemanticMergeResult((*result.items, *service.items), result.conflicts)


def validate_service(functions, enabled, counts):
    from .gpl import parse_gpl
    from .gameplay_events import stock_tokens
    expected = parse_gpl(SOURCE).items
    for item in expected:
        name = item.normalized_name
        if not enabled:
            if name in functions:
                raise ValueError("spell-origin service present without its native capability")
        elif counts.get(name) != 1 or stock_tokens(functions.get(name, "")) != stock_tokens(item.text):
            raise ValueError(f"spell-origin service is missing or changed: {item.name}")
