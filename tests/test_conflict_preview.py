from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from majesty_cam.manager.build import standard_content_conflicts, standard_conflict_pair_key
from majesty_cam.manager.catalog import Catalog, CatalogEntry, CatalogKind, CatalogSource
from majesty_cam.manager.conflict_preview import preview_standard_choice, rule_explanation, rule_label


def entry(number, name, definitions, **kwargs):
    identity = f"00000000-0000-4000-8000-{number:012d}"
    return CatalogEntry(identity, identity, name, CatalogKind.STANDARD, CatalogSource.LOCAL_MODS,
                        Path(name), Path(name) / "mod.mmxml", False, False,
                        content_definitions=tuple(definitions.items()), **kwargs)


def catalog_for(*entries):
    return Catalog(tuple(replace(item, unresolved_overlap_ids=tuple(
        other.content_id for other in entries if other != item
        and item.content_id not in other.load_after_ids and other.content_id not in item.load_after_ids
        and any(key in dict(other.content_definitions) and dict(other.content_definitions)[key] != value
                for key, value in item.content_definitions)
    )) for item in entries))


class ConflictPreviewTests(unittest.TestCase):
    def setUp(self):
        self.a = entry(1, "Attribute Rules", {"function:damage": "a", "function:willpower": "a",
                         "function:gettoavoid": "a", "function:potion_check": "only-a",
                         "function:gettohit": "only-a", "function:spellhit": "only-a"})
        self.b = entry(2, "Combat Rules", {"function:damage": "b", "function:willpower": "b",
                         "function:gettoavoid": "b", "function:private_callback": "only-b"})

    def preview(self, *entries, winners=None, selections=None, winner=None):
        catalog = catalog_for(*entries)
        selections = selections or {item.content_id: True for item in entries}
        conflict = next(item for item in standard_content_conflicts(catalog, selections)
                        if {item.left_id, item.right_id} == {self.a.content_id, self.b.content_id})
        return preview_standard_choice(catalog, selections, [item.content_id for item in entries],
                                       winners or {}, conflict, winner or self.b.content_id)

    def test_preview_shows_winner_and_remaining_rules_without_io_or_mutation(self):
        winners = {"unused": "unchanged"}
        with patch.object(Path, "read_bytes", side_effect=AssertionError("preview reread files")), \
                patch.object(Path, "stat", side_effect=AssertionError("preview rescanned files")), \
                patch("subprocess.run", side_effect=AssertionError("preview spawned a process")):
            preview = self.preview(self.a, self.b, winners=winners)
        self.assertIn("Attack avoidance — Combat Rules", preview.summary)
        self.assertIn("Still loaded from Attribute Rules:", preview.summary)
        self.assertIn("Potion use", preview.summary)
        self.assertIn("Attack accuracy", preview.summary)
        self.assertIn("function:damage", preview.technical)
        self.assertNotIn("function:damage", preview.summary)
        self.assertEqual(winners, {"unused": "unchanged"})
        self.assertIn("Original and expansion quests", preview.summary)

    def test_unresolved_third_mod_is_not_presented_as_a_final_winner(self):
        third = entry(3, "Third Rules", {"function:damage": "c"})
        preview = self.preview(self.a, self.b, third)
        self.assertIn("Attack damage — another conflict choice is still needed", preview.summary)
        self.assertIn("Third Rules", preview.summary)
        self.assertIn("provisional", preview.technical)

    def test_third_mods_saved_choices_determine_actual_final_provider(self):
        third = entry(3, "Third Rules", {"function:damage": "c"})
        winners = {standard_conflict_pair_key(item.content_id, third.content_id): third.content_id
                   for item in (self.a, self.b)}
        preview = self.preview(self.a, self.b, third, winners=winners)
        self.assertIn("Attack damage — Third Rules", preview.summary)
        self.assertIn("Attack avoidance — Combat Rules", preview.summary)
        self.assertNotIn("still needed", preview.summary)

    def test_explicit_load_order_and_unselected_mods_are_respected(self):
        third = entry(3, "Required Patch", {"function:damage": "c"},
                      load_after_ids=(self.a.content_id, self.b.content_id))
        preview = self.preview(self.a, self.b, third)
        self.assertIn("Attack damage — Required Patch", preview.summary)
        preview = self.preview(self.a, self.b, third,
                               selections={self.a.content_id: True, self.b.content_id: True})
        self.assertIn("Attack damage — Combat Rules", preview.summary)
        self.assertNotIn("Required Patch", preview.technical)

    def test_native_quest_scopes_are_previewed_separately(self):
        expansion = replace(self.b, dataset_base="majestyexpansion")
        original = entry(3, "Original Patch", {"function:damage": "c"}, dataset_base="majesty")
        preview = self.preview(self.a, expansion, original)
        self.assertIn("Original quests", preview.summary)
        self.assertIn("Combat Rules does not apply here", preview.summary)
        self.assertIn("Expansion quests", preview.summary)
        self.assertIn("Attack damage — Combat Rules", preview.summary)
        self.assertNotIn("another conflict choice is still needed", preview.summary)

    def test_invalid_cycle_never_claims_a_valid_final_result(self):
        third = entry(3, "Third Rules", {"function:damage": "c"})
        winners = {standard_conflict_pair_key(self.a.content_id, third.content_id): self.a.content_id,
                   standard_conflict_pair_key(self.b.content_id, third.content_id): third.content_id}
        preview = self.preview(self.a, self.b, third, winners=winners)
        self.assertIn("no valid final order", preview.summary)
        self.assertNotIn("Attack damage —", preview.summary)

    def test_literal_values_are_reported_without_inventing_units_or_effects(self):
        first = replace(self.a, content_definitions=(("expression:#shared_value", "a"),),
                        content_values=(("expression:#shared_value", "8"),))
        second = replace(self.b, content_definitions=(("expression:#shared_value", "b"),),
                         content_values=(("expression:#shared_value", "10"),))
        preview = self.preview(first, second)
        self.assertIn("Attribute Rules = 8; Combat Rules = 10", preview.summary)
        self.assertNotIn("gold", preview.summary)
        self.assertIn("declared value 10", preview.technical)

    def test_private_unknown_and_compiled_only_rules_are_not_given_guessed_effects(self):
        first = replace(self.a, content_definitions=(("function:mystery", "a"),))
        second = replace(self.b, content_definitions=(("function:mystery", "b"),))
        opaque = entry(3, "Compiled Only", {})
        preview = self.preview(first, second, opaque)
        self.assertIn("effect not interpreted", preview.summary)
        self.assertIn("overrides cannot be predicted", preview.summary)
        self.assertIn("function:mystery", preview.technical)

    def test_known_gameplay_roles_have_honest_nontechnical_explanations(self):
        known = {
            "random_hero_type": ("Random hero arrivals", "Embassy/outpost"),
            "spell_extra_value": ("Confidence in battle", "not the damage"),
            "guild_title": ("Finding a home guild", "hero's home"),
            "getattackrange": ("Attack distance", "weapon or spell range"),
            "build_horde": ("Undead followers", "skeleton followers"),
            "hero_drop_quest_items": ("Items dropped on death", "carried items"),
            "building_death": ("Building destruction", "occupants"),
            "lair_death": ("Destroyed lairs", "Monsters and loot"),
            "vortex_active": ("Vortex spell effects", "nearby enemies"),
        }
        for name, (label, meaning) in known.items():
            with self.subTest(name=name):
                self.assertEqual(rule_label("function:" + name), label)
                self.assertIn(meaning, rule_explanation("function:" + name))
                self.assertEqual(rule_explanation("function:" + name.upper()),
                                 rule_explanation("function:" + name))
                self.assertNotIn(name, rule_explanation("function:" + name))
        self.assertEqual(rule_explanation("description:guild_title"), "")
        self.assertIn("cannot reliably describe", rule_explanation("function:custom_rule"))

    def test_standard_preview_reuses_gameplay_explanations_without_predicting_mod_results(self):
        keys = ("function:random_hero_type", "function:spell_extra_value", "function:guild_title")
        first = replace(self.a, content_definitions=tuple((key, "a") for key in keys))
        second = replace(self.b, content_definitions=tuple((key, "b") for key in keys))
        with patch.object(Path, "read_bytes", side_effect=AssertionError("preview reread files")), \
                patch.object(Path, "stat", side_effect=AssertionError("preview rescanned files")):
            preview = self.preview(first, second)
        for key in keys:
            self.assertIn(rule_explanation(key), preview.summary)
            self.assertIn(rule_label(key) + " — Combat Rules", preview.summary)
        self.assertNotIn("Guild naming", preview.summary)
        self.assertNotIn("spell_extra_value", preview.summary)


if __name__ == "__main__":
    unittest.main()
