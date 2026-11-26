from __future__ import annotations

import json
import struct
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from majesty_cam.compose import SelectedMod, _generated_mod_id, profile_mod_id
from majesty_cam.manager import saves
from majesty_cam.manager.saves import (
    ContentOverlap, KnownBuild, MembershipProof, ModRef, SaveFormatError, SaveState,
    SaveUpdateError, UpdateTarget, load_prepared_builds, plan_save_update, plan_save_updates,
    profile_part_ids, read_mod_list, read_save_head, record_prepared_build, report_overlaps,
    rewrite_mod_list, write_updated_copy,
)
from majesty_cam.scoped_output import scoped_mod_id

SLUG = "manager-merged"
NAME = "Majesty Mod Manager: Merged Profile"


def gid(number: int) -> str:
    return str(uuid.UUID(int=number)).upper()


def norm(value: str) -> str:
    return str(uuid.UUID(value.strip("{}"))).upper()


def make_save(records, *, save_name="Morning", quest="A Quest", revision=11, body=b"MAP 8" + b"\x00" * 64):
    entries = b"".join(uuid.UUID(mod_id).bytes_le + name.encode("cp1252") + b"\0" for mod_id, name in records)
    payload = (save_name.encode("cp1252") + b"\0" + quest.encode("cp1252") + b"\0" + b"\x07\x00\x00\x00"
               + b"Rel@" + bytes(16) + struct.pack("<I", len(records)) + entries)
    head = b"VERS" + struct.pack("<I", 4) + b"\x01\x00\x00\x00" + b"Template\0"
    return head + b"SVGD" + struct.pack("<III", len(payload), revision, 0) + payload + body


# Merge members A, B, C and Standard mods S1, S2 (S2 needs expansion rules).
A, B, C = gid(0xA), gid(0xB), gid(0xC)
S1, S2, S3 = gid(0x51), gid(0x52), gid(0x53)


def parts_for(members):
    main = norm(profile_mod_id(members, SLUG))
    return {
        "Any": ModRef(main, NAME),
        "Majesty": ModRef(norm(scoped_mod_id(main, "Majesty")), NAME + " (Majesty scripts)"),
        "MajestyExpansion": ModRef(norm(scoped_mod_id(main, "MajestyExpansion")),
                                   NAME + " (MajestyExpansion scripts)"),
    }


def make_target(members=(A, B, C), standard=(S1, S2), *, parts=None, known=None, overlaps=(),
                unit_types=None, stock=None, installed_extra=()):
    names = {A: "Alpha", B: "Beta", C: "Gamma", S1: "Standard One", S2: "Standard Two", S3: "Standard Three"}
    installed = {mod_id: names[mod_id] for mod_id in (*members, *standard, *installed_extra)}
    return UpdateTarget(
        standard=tuple(ModRef(m, names[m]) for m in standard),
        profile_parts=parts if parts is not None else parts_for(members),
        members=tuple(ModRef(m, names[m]) for m in members),
        profile_slug=SLUG,
        installed=installed,
        datasets={S1: "any", S2: "majestyexpansion", S3: "any"},
        unit_types=unit_types or {},
        known_builds=known or {},
        overlaps=tuple(overlaps),
        stock_unit_types=stock,
    )


def save_records(members, standard=(S1, S2), scope="MajestyExpansion"):
    parts = parts_for(members)
    names = {S1: "Standard One", S2: "Standard Two", S3: "Standard Three", B: "Beta"}
    rows = [(m, names[m]) for m in standard]
    rows.append((parts["Any"].mod_id, NAME))
    if scope:
        rows.append((parts[scope].mod_id, parts[scope].name))
    return rows


def plan_for(records, target, name="Morning.GMP"):
    data = make_save(records)
    return plan_save_update(Path(name), read_mod_list(data), target), data


class SaveModListFormatTests(unittest.TestCase):
    def test_reads_records_names_and_titles(self):
        data = make_save([(S1, "Standard One"), (A, "Alpha")], save_name="Day 12", quest="The Siege")
        mod_list = read_mod_list(data)
        self.assertEqual(mod_list.mod_ids, (S1, A))
        self.assertEqual([r.name for r in mod_list.records], ["Standard One", "Alpha"])
        self.assertEqual((mod_list.save_name, mod_list.quest_name), ("Day 12", "The Siege"))
        self.assertEqual(mod_list.list_end, data.index(b"MAP 8"))

    def test_identity_rewrite_is_byte_identical(self):
        data = make_save([(S1, "Standard One"), (A, "Alpha")])
        mod_list = read_mod_list(data)
        self.assertEqual(rewrite_mod_list(data, mod_list, [(r.mod_id, r.name_bytes) for r in mod_list.records]), data)

    def test_rewrite_changes_only_the_list_and_its_length(self):
        data = make_save([(S1, "Standard One"), (A, "Alpha")])
        before = read_mod_list(data)
        result = rewrite_mod_list(data, before, [(S1, b"Standard One"), (S2, b"Standard Two"), (B, b"Beta")])
        after = read_mod_list(result)
        self.assertEqual(after.mod_ids, (S1, S2, B))
        self.assertEqual(result[:before.descriptor + 4], data[:before.descriptor + 4])
        self.assertEqual(result[after.list_end:], data[before.list_end:])
        self.assertEqual(after.length - before.length, len(result) - len(data))

    def test_rejects_listless_and_malformed_descriptors(self):
        listless = b"SVGD" + struct.pack("<III", 8, 10, 0) + b"Name\0" + b"Rel@"[:3]
        with self.assertRaises(SaveFormatError):
            read_mod_list(listless + b"MAP 8")
        payload = b"Name\0Quest\0Rel@"
        with self.assertRaisesRegex(SaveFormatError, "without mods"):
            read_mod_list(b"SVGD" + struct.pack("<III", len(payload), 10, 0) + payload + b"MAP 8")
        data = bytearray(make_save([(S1, "Standard One")]))
        start = data.index(b"SVGD")
        struct.pack_into("<I", data, start + 4, struct.unpack_from("<I", data, start + 4)[0] + 1)
        with self.assertRaisesRegex(SaveFormatError, "does not end"):
            read_mod_list(bytes(data))
        with self.assertRaisesRegex(SaveFormatError, "revision"):
            read_mod_list(make_save([(S1, "x")], revision=12))
        with self.assertRaises(SaveFormatError):
            read_mod_list(b"no descriptor here")

    def test_marker_inside_the_save_name_is_not_mistaken_for_the_list(self):
        data = make_save([(S1, "Standard One")], save_name="Rel@ Rel@ tricky")
        self.assertEqual(read_mod_list(data).mod_ids, (S1,))

    def test_rewrite_refuses_duplicates_nul_and_too_many(self):
        data = make_save([(S1, "x")])
        mod_list = read_mod_list(data)
        with self.assertRaisesRegex(SaveFormatError, "twice"):
            rewrite_mod_list(data, mod_list, [(S1, b"a"), (S1.lower(), b"b")])
        with self.assertRaisesRegex(SaveFormatError, "NUL"):
            rewrite_mod_list(data, mod_list, [(S1, b"a\0b")])
        with self.assertRaisesRegex(SaveFormatError, "at most"):
            rewrite_mod_list(data, mod_list, [(gid(1000 + n), b"m") for n in range(65)])

    def test_head_read_matches_full_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Big.GMP"
            data = make_save([(S1, "Standard One")], body=b"MAP 8" + b"\x01" * (1 << 19))
            path.write_bytes(data)
            self.assertEqual(read_save_head(path).mod_ids, read_mod_list(data).mod_ids)


class ProfileIdentityTests(unittest.TestCase):
    def test_profile_mod_id_is_the_generated_id(self):
        selected = tuple(SelectedMod(str(n), SimpleNamespace(mod_id="{" + m + "}")) for n, m in enumerate((A, B)))
        self.assertEqual(_generated_mod_id(selected, SLUG), profile_mod_id((A, B), SLUG))

    def test_part_ids_follow_the_scoped_ids(self):
        parts = parts_for((A,))
        found = profile_part_ids(parts["Any"].mod_id, [parts["Majesty"].mod_id])
        self.assertEqual(found, {"Any": parts["Any"].mod_id, "Majesty": parts["Majesty"].mod_id})

    def test_proof_finds_subsets_in_current_order_only(self):
        target = make_target()
        proof = MembershipProof(target)
        self.assertTrue(proof.enabled)
        self.assertEqual(proof.members_of(parts_for((A, C))["Any"].mod_id), (A, C))
        self.assertEqual(proof.members_of(parts_for(())["Any"].mod_id), ())
        self.assertIsNone(proof.members_of(parts_for((C, A))["Any"].mod_id))
        self.assertIsNone(proof.members_of(gid(0xDEAD)))

    def test_history_resolves_what_recomputation_cannot(self):
        old = parts_for((C, A))["Any"].mod_id
        known = {old: KnownBuild(old, (ModRef(C, "Gamma"), ModRef(A, "Alpha")), {"Any": old})}
        self.assertEqual(MembershipProof(make_target(known=known)).members_of(old), (C, A))

    def test_proof_is_off_when_the_formula_does_not_reproduce_the_current_id(self):
        target = make_target(parts={"Any": ModRef(gid(0xBAD), NAME)})
        proof = MembershipProof(target)
        self.assertFalse(proof.enabled)
        self.assertIsNone(proof.members_of(parts_for((A,))["Any"].mod_id))


class PlanTests(unittest.TestCase):
    def test_current_save_needs_nothing(self):
        plan, _ = plan_for(save_records((A, B, C)), make_target())
        self.assertIs(plan.state, SaveState.CURRENT)
        self.assertEqual(plan.profile_label, "Current profile")

    def test_profile_that_gained_members_is_relinked_in_place(self):
        records = save_records((A, C))
        plan, _ = plan_for(records, make_target())
        self.assertIs(plan.state, SaveState.UPDATABLE)
        self.assertIn("Beta", plan.summary)
        current = parts_for((A, B, C))
        self.assertEqual([m for m, _ in plan.records],
                         [S1, S2, current["Any"].mod_id, current["MajestyExpansion"].mod_id])

    @staticmethod
    def history(*members):
        main = parts_for(members)["Any"].mod_id
        names = {A: "Alpha", B: "Beta", C: "Gamma"}
        return {main: KnownBuild(main, tuple(ModRef(m, names[m]) for m in members), {"Any": main})}

    def test_profile_that_lost_a_member_is_left_alone(self):
        plan, _ = plan_for(save_records((A, B, C)), make_target(members=(A, C), known=self.history(A, B, C)))
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("Beta", plan.summary)
        # Without history, recomputation cannot explain a larger old profile either.
        plan, _ = plan_for(save_records((A, B, C)), make_target(members=(A, C)))
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("cannot account", plan.summary)

    def test_member_moved_from_merge_to_standard_is_left_alone(self):
        target = make_target(members=(A,), standard=(S1, S2, B), known=self.history(A, B))
        plan, _ = plan_for(save_records((A, B)), target)
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("moved", plan.summary)

    def test_standard_mod_now_merged_is_dropped(self):
        records = save_records((A, C), standard=(S1, B, S2))
        plan, _ = plan_for(records, make_target())
        self.assertIs(plan.state, SaveState.UPDATABLE)
        self.assertNotIn(B, [m for m, _ in plan.records])
        self.assertTrue(any("Now loads through" in line for line in (plan.summary, *plan.details)))

    def test_unknown_profile_is_left_alone(self):
        records = [(S1, "Standard One"), (S2, "Standard Two"), (gid(0xFEED), NAME)]
        plan, _ = plan_for(records, make_target())
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("cannot account", plan.summary)

    def test_mods_outside_the_selection_leave_the_save_alone(self):
        records = save_records((A, B, C), standard=(S1, S2, S3))
        plan, _ = plan_for(records, make_target(installed_extra=(S3,)))
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("not selected", plan.summary)
        plan, _ = plan_for(records, make_target())
        self.assertIn("not installed", plan.summary)

    def test_new_standard_mod_goes_in_launch_order_ahead_of_the_profile(self):
        records = save_records((A, B, C), standard=(S1, S2))
        plan, _ = plan_for(records, make_target(standard=(S1, S3, S2), installed_extra=()))
        self.assertIs(plan.state, SaveState.UPDATABLE)
        self.assertEqual([m for m, _ in plan.records][:3], [S1, S3, S2])

    def test_only_the_scripts_part_for_the_save_rules_is_kept_or_added(self):
        plan, _ = plan_for(save_records((A,), standard=(S1, S2), scope=None), make_target())
        self.assertIs(plan.state, SaveState.UPDATABLE)
        current = parts_for((A, B, C))
        self.assertEqual([m for m, _ in plan.records][-2:],
                         [current["Any"].mod_id, current["MajestyExpansion"].mod_id])

    def test_unknown_rules_block_adding_a_scripts_part(self):
        plan, _ = plan_for(save_records((A,), standard=(S1,), scope=None), make_target(standard=(S1,)))
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("quest rules", plan.summary)

    def test_profile_added_to_a_save_played_without_one(self):
        plan, _ = plan_for([(S1, "Standard One"), (S2, "Standard Two")], make_target())
        self.assertIs(plan.state, SaveState.CAUTION)
        self.assertIn("without one", plan.summary)

    def test_classic_selection_cannot_take_a_profile_save(self):
        plan, _ = plan_for(save_records((A,)), make_target(members=(), parts={}))
        self.assertIs(plan.state, SaveState.BLOCKED)
        self.assertIn("without one", plan.summary)

    def test_new_types_and_shared_content_are_cautions(self):
        stock = {"majestyexpansion": frozenset({"pal1"})}
        target = make_target(unit_types={B: frozenset({"pal1", "new1"})}, stock=stock)
        plan, _ = plan_for(save_records((A, C)), target)
        self.assertIs(plan.state, SaveState.CAUTION)
        self.assertTrue(any("new unit" in line for line in plan.cautions))
        target = make_target(overlaps=[ContentOverlap("gravestone", "any", frozenset({A, B}))])
        plan, _ = plan_for(save_records((A, C)), target)
        self.assertTrue(any("gravestone" in line for line in plan.cautions))
        target = make_target(overlaps=[ContentOverlap("Lair", "majestyexpansion", frozenset({A, B}),
                                                      retained=frozenset({A}))])
        plan, _ = plan_for(save_records((A, C)), target)
        self.assertIs(plan.state, SaveState.UPDATABLE)

    def test_saved_profile_label(self):
        old = parts_for((A,))["Any"].mod_id
        known = {old: KnownBuild(old, (ModRef(A, "Alpha"),), {"Any": old}, label='Saved profile "Mine"')}
        plan, _ = plan_for(save_records((A,)), make_target(known=known))
        self.assertEqual(plan.profile_label, 'Saved profile "Mine"')
        self.assertIs(plan.state, SaveState.UPDATABLE)

    def test_inconsistent_profile_entries_are_left_alone(self):
        records = save_records((A,), scope=None) + [(parts_for((A, B))["Majesty"].mod_id,
                                                     NAME + " (Majesty scripts)")]
        plan, _ = plan_for(records, make_target())
        self.assertIs(plan.state, SaveState.BLOCKED)


class FolderAndWriteTests(unittest.TestCase):
    def test_folder_plans_and_updated_copies(self):
        target = make_target()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "Day 5.GMP"
            original.write_bytes(make_save(save_records((A, C))))
            (root / "notes.txt").write_text("not a save")
            (root / "Broken.GMP").write_bytes(b"junk")
            plans = {p.path.name: p for p in plan_save_updates(root, target)}
            self.assertEqual(set(plans), {"Day 5.GMP", "Broken.GMP"})
            self.assertIs(plans["Broken.GMP"].state, SaveState.UNREADABLE)
            before = original.read_bytes()
            written = write_updated_copy(plans["Day 5.GMP"])
            self.assertEqual(written.name, "Day 5 (updated).GMP")
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(read_mod_list(written.read_bytes()).mod_ids,
                             tuple(m for m, _ in plans["Day 5.GMP"].records))
            again = {p.path.name: p for p in plan_save_updates(root, target)}
            self.assertIs(again["Day 5.GMP"].state, SaveState.UPDATED)
            self.assertIs(again["Day 5 (updated).GMP"].state, SaveState.CURRENT)
            self.assertEqual(write_updated_copy(plans["Day 5.GMP"]).name, "Day 5 (updated 2).GMP")
            self.assertEqual(sorted(p.name for p in root.glob("*.tmp")), [])

    def test_a_changed_original_is_not_written(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Day 6.GMP"
            path.write_bytes(make_save(save_records((A, C))))
            plan = plan_save_update(path, read_save_head(path), make_target())
            path.write_bytes(make_save(save_records((A,))))
            with self.assertRaisesRegex(SaveUpdateError, "changed"):
                write_updated_copy(plan)
            self.assertEqual(list(Path(folder).glob("*updated*")), [])

    def test_blocked_and_current_plans_cannot_be_written(self):
        plan, _ = plan_for(save_records((A, B, C)), make_target())
        with self.assertRaises(SaveUpdateError):
            write_updated_copy(plan)


class HistoryAndReportTests(unittest.TestCase):
    def test_history_roundtrip_dedupes_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = saves.history_path(Path(folder))
            self.assertEqual(load_prepared_builds(path), {})
            first = parts_for((A,))
            record_prepared_build(path, profile_id=first["Any"].mod_id,
                                  generated_ids=[first["Any"].mod_id, first["MajestyExpansion"].mod_id],
                                  members=[ModRef(A, "Alpha")])
            record_prepared_build(path, profile_id=first["Any"].mod_id, generated_ids=[first["Any"].mod_id],
                                  members=[ModRef(A, "Alpha")])
            builds = load_prepared_builds(path)
            self.assertEqual(list(builds), [first["Any"].mod_id])
            self.assertEqual(builds[first["Any"].mod_id].parts, {"Any": first["Any"].mod_id})
            for n in range(saves.HISTORY_LIMIT + 5):
                record_prepared_build(path, profile_id=gid(5000 + n), generated_ids=[], members=[])
            self.assertEqual(len(json.loads(path.read_text())["builds"]), saves.HISTORY_LIMIT)
            path.write_text("{not json")
            self.assertEqual(load_prepared_builds(path), {})

    def test_report_overlaps(self):
        report = {
            "merge": {"gpl": {
                "instruction_merges": [{"function": "gravestone", "owners": [
                    "alpha-" + A.replace("-", "").lower(), "beta-" + B.replace("-", "").lower()]}],
                "conflicts": [{"kind": "function", "name": "gravestone", "owners": [
                    "alpha-" + A.replace("-", "").lower(), "beta-" + B.replace("-", "").lower()]},
                    {"kind": "function", "name": "solo", "owners": ["alpha-" + A.replace("-", "").lower()]}],
            }},
            "xml_mod_preferences": [{"dataset": "majestyexpansion", "name": "Lair", "contributors": ["Alpha", "Gamma"],
                                     "retained_mod_ids": [C.lower()]}],
        }
        found = report_overlaps(report, {"Alpha": A, "Gamma": C})
        self.assertEqual([(o.name, o.mod_ids, o.retained) for o in found], [
            ("gravestone", frozenset({A, B}), None),
            ("Lair", frozenset({A, C}), frozenset({C})),
        ])
        self.assertEqual(report_overlaps({}, {}), ())


if __name__ == "__main__":
    unittest.main()
