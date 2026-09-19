"""Approved owner-persistent research extension over stock AP99 orders.

This module contains author data and deterministic identities, not engine
addresses. Native bindings and generated GPL are supplied by the Manager.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
import uuid


KINGDOM_RESEARCH_TYPE = "manager.kingdom-research.v1"
MAX_KINGDOM_RESEARCH = 32
MAX_INTEGER = 0x7FFFFFFF
STOCK_TEMPLATES = frozenset((
    *range(0x1388, 0x138E), 0x1392, 0x139C, 0x139D,
    *range(0x13A6, 0x13AC), *range(0x13B0, 0x13B4), 0x13BA,
    *range(0x13C5, 0x13CB),
))


@dataclass(frozen=True)
class KingdomResearch:
    feature_key: str
    parent_building: str
    action_control_id: int
    descriptor_template_control_id: int
    required_level: int
    price: int
    gold_bonus_percent: int
    experience_bonus_percent: int
    progress_control_id: int
    active_display_control_id: int
    completion_text: str
    active_effector: str = ""

    @property
    def price_control_id(self):
        return self.action_control_id + 1000

    @property
    def icon_control_id(self):
        return self.action_control_id + 500


@dataclass(frozen=True)
class KingdomResearchRegistration:
    """Resolved, manager-owned record; never accepted directly from packages."""
    identity: str
    building_family: int
    action_control_id: int
    descriptor_template_control_id: int
    completion_attribute: int
    required_level: int
    price: int
    gold_bonus_percent: int
    experience_bonus_percent: int
    progress_control_id: int
    active_display_control_id: int
    completion_text: str
    active_effector: str = ""

    @property
    def callback_symbol(self):
        return "MM_KR_" + self.identity


def _integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"kingdom research {name} must be {minimum}..{maximum}")
    return value


def parse_kingdom_research(value) -> KingdomResearch:
    fields = set(KingdomResearch.__dataclass_fields__) | {"type"}
    required = fields - {"active_effector"}
    if not required <= set(value) or set(value) - fields or value.get("type") != KINGDOM_RESEARCH_TYPE:
        raise ValueError("kingdom research requires " + ", ".join(sorted(required)) +
                         "; only active_effector is optional")
    key = value["feature_key"]
    parent = value["parent_building"]
    if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", key):
        raise ValueError("kingdom research feature_key must be a stable lowercase key")
    if not isinstance(parent, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", parent):
        raise ValueError("kingdom research parent_building must be a Description name")
    action = _integer(value["action_control_id"], "action_control_id", 0x22CF, MAX_INTEGER-1000)
    template = _integer(value["descriptor_template_control_id"], "descriptor_template_control_id", 1, MAX_INTEGER)
    if template not in STOCK_TEMPLATES:
        raise ValueError("kingdom research requires an audited AP99 descriptor template")
    _integer(value["required_level"], "required_level", 1, 3)
    _integer(value["price"], "price", 1, 1000000)
    for name in ("gold_bonus_percent", "experience_bonus_percent"):
        _integer(value[name], name, 0, 100)
    if not (value["gold_bonus_percent"] or value["experience_bonus_percent"]):
        raise ValueError("kingdom research must declare at least one nonzero reward bonus")
    controls = [action, action+500, action+1000]
    for name in ("progress_control_id", "active_display_control_id"):
        controls.append(_integer(value[name], name, 0x22CF, MAX_INTEGER))
    if len(set(controls)) != len(controls):
        raise ValueError("kingdom research controls must be distinct")
    text = value["completion_text"]
    if not isinstance(text, str) or "\0" in text:
        raise ValueError("kingdom research completion_text must be non-NUL text")
    if not 1 <= len(text.encode("cp1252")) <= 96:
        raise ValueError("kingdom research completion_text must be 1..96 Windows-1252 bytes")
    effector = value.get("active_effector", "")
    if not isinstance(effector, str) or (effector and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", effector)):
        raise ValueError("kingdom research active_effector must be a private Description name")
    return KingdomResearch(**{key: value[key] for key in required-{ "type" }},
                           active_effector=effector)


def kingdom_research_mapping(feature: KingdomResearch) -> dict:
    result = dict(type=KINGDOM_RESEARCH_TYPE, **asdict(feature))
    if not feature.active_effector:
        result.pop("active_effector")
    parse_kingdom_research(result)
    return result


def registration(mod_id: str, feature: KingdomResearch, family: str) -> KingdomResearchRegistration:
    kingdom_research_mapping(feature)
    if not isinstance(family, str) or not re.fullmatch(r"[!-~]{3}", family):
        raise ValueError("kingdom research family must be a stock-shaped three-byte building prefix")
    digest = hashlib.sha256(uuid.UUID(mod_id).bytes + b"\0" + feature.feature_key.encode("ascii")).digest()
    return KingdomResearchRegistration(
        digest[:16].hex(), int.from_bytes(family.encode("ascii"), "little"),
        feature.action_control_id, feature.descriptor_template_control_id,
        0xD0000000 | (int.from_bytes(digest[16:20], "little") & 0x0FFFFFFF),
        feature.required_level, feature.price, feature.gold_bonus_percent,
        feature.experience_bonus_percent, feature.progress_control_id,
        feature.active_display_control_id, feature.completion_text, feature.active_effector,
    )


def validate_registration(record: KingdomResearchRegistration) -> None:
    if not isinstance(record.identity, str) or not re.fullmatch(r"[0-9a-f]{32}", record.identity):
        raise ValueError("invalid kingdom research identity")
    _integer(record.building_family, "building_family", 1, 0xFFFFFF)
    family = record.building_family.to_bytes(3, "little")
    if any(value < 0x21 or value > 0x7E for value in family):
        raise ValueError("invalid kingdom research building family")
    _integer(record.completion_attribute, "completion_attribute", 0xD0000000, 0xDFFFFFFF)
    parse_kingdom_research(dict(
        type=KINGDOM_RESEARCH_TYPE, feature_key="resolved", parent_building="Resolved",
        **{name: getattr(record, name) for name in KingdomResearch.__dataclass_fields__
           if name not in {"feature_key", "parent_building"}},
    ))


def award_with_carry(base: int, percent: int, carry: int) -> tuple[int, int]:
    """Integer reference for the generated GPL's post-stock-divisor bonus.

    Base awards and the stock divisor's own rounding never change. Only the
    percentage bonus accumulates fractions, separately for each hero/research
    and currency. Overflow saturates rather than wrapping a positive award.
    """
    _integer(base, "base award", 0, MAX_INTEGER)
    _integer(percent, "percent", 0, 100)
    _integer(carry, "carry", 0, 99)
    if base == 0 or percent == 0:
        return base, carry
    fraction = (base % 100) * percent + carry
    bonus = (base // 100) * percent + fraction // 100
    return min(MAX_INTEGER, base + bonus), fraction % 100
