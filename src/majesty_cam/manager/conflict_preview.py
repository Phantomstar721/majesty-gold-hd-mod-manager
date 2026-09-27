"""Read-only Standard load-order previews from the existing scan snapshot.

Labels describe the routines affected, not inferred gameplay formulas. Native
last-definition-wins ordering remains owned by build.py; nothing compiles,
reads package files, or changes the selection while a choice is previewed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

from .build import (
    StandardContentConflict, _order_standard_ids, _standard_order_has_cycle,
    standard_content_conflicts,
)
from .catalog import Catalog
from .profile import normalize_guid


# A shared vocabulary for game routines, never a package-specific exception.
_RULE_LABELS = {
    "damage": "Attack damage", "spelldamage": "Spell damage",
    "willpower": "Willpower calculation", "gettoavoid": "Attack avoidance",
    "gettohit": "Attack accuracy", "spellhit": "Spell hit and resistance checks",
    "spell_attack": "Spell attacks", "make_attack": "Attack handling",
    "getmaxhealpotions": "Potion capacity", "potion_check": "Potion use",
    "purchase_potions": "Potion purchasing", "heal_self": "Self-healing",
    "purchase_equipment": "Equipment purchasing", "reset_tasks": "Hero task resets",
    "unit_call_deathscript": "Death handling", "gravestone": "Hero deaths",
    "monster_gravestone": "Monster deaths", "attacklogic": "Attack decisions",
    "attack_object": "Attack decisions",
    "travel_to_safe": "Retreat decisions", "trytravelspell": "Travel spells",
    "guild_title": "Finding a home guild", "collect_object": "Item collection",
    "shapeshift_potion_effect": "Shapeshifting", "dropgoldinradius": "Dropped gold",
    "random_hero_type": "Random hero arrivals", "spell_extra_value": "Confidence in battle",
    "getattackrange": "Attack distance", "build_horde": "Undead followers",
    "hero_drop_quest_items": "Items dropped on death", "building_death": "Building destruction",
    "lair_death": "Destroyed lairs", "vortex_active": "Vortex spell effects",
}


# These explain stock responsibilities, not differences inferred from mod code.
# Sources: OriginalQuests/GPLMx Embassy and Special_Events (random heroes),
# Mausoleum and mx_Inn_Visited (home guilds), mx_target_eval (confidence),
# mx_Travel_to (range), mx_Build_Horde (followers), mx_Hero_Deaths,
# mx_Building_Deaths and mx_Spells. Original GPL equivalents agree where present.
_RULE_EXPLANATIONS = {
    "random_hero_type": "Which hero types can arrive through Embassy/outpost recruitment and certain random events.",
    "spell_extra_value": "How available spells count toward a hero's decision to fight or flee, not the damage those spells deal.",
    "guild_title": "Which guild buildings can serve as a hero's home.",
    "getattackrange": "How close a unit moves before attacking, based on its weapon or spell range.",
    "build_horde": "Decisions about controlling nearby undead or summoning skeleton followers.",
    "hero_drop_quest_items": "Which carried items are dropped when a hero dies.",
    "building_death": "What happens to occupants and building remains when a building is destroyed.",
    "lair_death": "Monsters and loot released when a lair is destroyed.",
    "vortex_active": "How the Vortex spell affects nearby enemies.",
}


def rule_label(key: str) -> str:
    kind, _, name = key.casefold().partition(":")
    if kind == "function":
        if name in _RULE_LABELS:
            return _RULE_LABELS[name]
        if name.endswith("_tree"):
            return "Unit decision-making"
        return "Other script behavior (effect not interpreted)"
    return {
        "expression": "Shared script settings", "dat_block": "Unit and game data",
        "description": "Displayed descriptions", "prototype": "Script declarations",
    }.get(kind, "Other game content")


def rule_explanation(key: str) -> str:
    """Describe a verified stock role without pretending to interpret a mod."""
    kind, _, name = key.casefold().partition(":")
    if kind == "function":
        if name in _RULE_EXPLANATIONS:
            return _RULE_EXPLANATIONS[name]
        if name not in _RULE_LABELS and not name.endswith("_tree"):
            return "The Manager cannot reliably describe the gameplay effect of these changes."
    return ""


@dataclass(frozen=True)
class ConflictPreview:
    summary: str
    technical: str


def preview_standard_choice(
    catalog: Catalog, selections: Mapping[str, bool], order: Sequence[str],
    winners: Mapping[str, str], conflict: StandardContentConflict, winner: str,
) -> ConflictPreview:
    """Preview both native quest scopes, including third-party overrides."""
    if winner not in (conflict.left_id, conflict.right_id):
        raise ValueError("winner must belong to the previewed conflict")
    selected = {normalize_guid(key) for key, enabled in selections.items() if enabled}
    entries = {entry.content_id: entry for entry in catalog.standard
               if entry.content_id in selected and entry.selectable}
    choices = dict(winners)
    choices[conflict.pair_key] = winner
    if not {conflict.left_id, conflict.right_id} <= entries.keys():
        return ConflictPreview("Both mods must be selected to preview this choice.", "")
    if _standard_order_has_cycle(entries, set(entries), choices):
        return ConflictPreview(
            "This choice conflicts with other load-order choices or required ordering.\n\n"
            "There is no valid final order yet. Change another choice before preparing. "
            "You can save this choice and continue reviewing the remaining conflicts.",
            "No final provider can be calculated for a cyclic load order.",
        )
    ordered = _order_standard_ids(tuple(entries.values()),
                                 {normalize_guid(key): i for i, key in enumerate(order)}, choices)
    definitions = {key: dict(entry.content_definitions) for key, entry in entries.items()}
    values = {key: dict(entry.content_values) for key, entry in entries.items()}
    unresolved = tuple(item for item in standard_content_conflicts(catalog, selections)
                       if choices.get(item.pair_key) not in (item.left_id, item.right_id))
    pair = (conflict.left_id, conflict.right_id)
    technical = []
    sections = []
    for base, heading in (("majesty", "Original quests"), ("majestyexpansion", "Expansion quests")):
        active = [key for key in ordered if entries[key].dataset_base in ("any", base)]
        providers = defaultdict(list)
        for key in active:
            for change in definitions[key]:
                providers[change].append(key)
        technical.append(heading + " — Standard load order:\n" + "\n".join(
            f"{i + 1}. {entries[key].display_name}" for i, key in enumerate(active)))
        if not all(key in active for key in pair):
            absent = ", ".join(entries[key].display_name for key in pair if key not in active)
            sections.append(f"{absent} does not apply here. Choosing between these two mods has no effect here.")
            continue

        pending = [item for item in unresolved if item.left_id in active and item.right_id in active]
        pending_keys = {key for item in pending for key in item.change_keys}
        groups = defaultdict(set)
        explanations = defaultdict(set)
        for change in conflict.change_keys:
            owners = providers.get(change, [])
            if not owners:
                continue
            final = owners[-1]
            label = rule_label(change)
            explanation = rule_explanation(change)
            if explanation:
                explanations[label].add(explanation)
            if change in pending_keys:
                groups[label].add("another conflict choice is still needed")
            else:
                groups[label].add(entries[final].display_name)
            technical.append(f"\n{change}\n" + "\n".join(
                f"  {entries[key].display_name}: {definitions[key][change]}"
                + (f"; declared value {values[key][change]}" if change in values[key] else "")
                for key in owners
            ) + f"\n  Last provider in this order: {entries[final].display_name}"
              + (" (provisional; unresolved choice)" if change in pending_keys else ""))

        lines = ["Shared behavior after this choice:"]
        for label, names in sorted(groups.items()):
            lines.append(f"• {label} — {' / '.join(sorted(names))}")
            lines.extend("  " + description for description in sorted(explanations[label]))
        for change in conflict.change_keys:
            literal_owners = [key for key in providers.get(change, []) if change in values[key]]
            if len(literal_owners) > 1:
                lines.append(f"• Declared setting {change.split(':', 1)[1]}: " + "; ".join(
                    f"{entries[key].display_name} = {values[key][change]}" for key in literal_owners))

        loser = pair[1] if winner == pair[0] else pair[0]
        retained = sorted(key for key in definitions[loser] if key not in conflict.change_keys
                          and providers[key][-1] == loser)
        if retained:
            labels = sorted({rule_label(key) for key in retained})
            lines.extend(("", f"Still loaded from {entries[loser].display_name}:"))
            lines.extend(f"• {label}" for label in labels)
            lines.append("This keeps rules from both mods; choosing a winner does not disable the other mod.")
            technical.append(f"\nStill loaded from {entries[loser].display_name}:\n" + "\n".join(retained))
            if pending_keys.intersection(retained):
                lines.append("Some of these remaining rules also have unresolved choices.")
        else:
            lines.extend(("", "The other mod stays enabled. No additional source-visible rules from it "
                          "remain last in this order."))
        related_pending = [item for item in pending if set(item.change_keys).intersection(conflict.change_keys)]
        if related_pending:
            lines.extend(("", "Still to decide:"))
            lines.extend(f"• {item.left_name} / {item.right_name}" for item in related_pending)
        sections.append("\n".join(lines))

    if sections[0] == sections[1]:
        summary = "Original and expansion quests\n\n" + sections[0]
    else:
        summary = "Original quests\n\n" + sections[0] + "\n\nExpansion quests\n\n" + sections[1]
    if any(not entry.content_definitions or entry.dataset_base not in ("any", "majesty", "majestyexpansion")
           for entry in entries.values()):
        summary += "\n\nSome selected content has no readable rules or a recognized quest scope; its overrides cannot be predicted."
    summary += ("\n\nBased on readable Standard-mod rules. Labels identify affected routines, not their exact "
                "gameplay formulas. Hidden compiled changes and later Prepare adjustments are not predicted.")
    return ConflictPreview(summary, "\n\n".join(technical))
