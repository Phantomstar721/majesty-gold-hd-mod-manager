import unittest
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from dataclasses import replace

from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.kingdom_research import (
    KingdomResearch, MAX_INTEGER, award_with_carry, kingdom_research_mapping,
    parse_kingdom_research, registration, validate_registration,
)
from majesty_cam.kingdom_research_gpl import compose_service, service_source
from majesty_cam.runtime_features import (normalize_runtime_features,
    encode_runtime_feature_registry, decode_runtime_feature_registry,
    derive_feature_runtime_capabilities as effective_runtime_capabilities,
    EquipmentRegistration, NativeTimingFeature)


UUID = "39ee2697-33c8-42e2-a575-c26c00640f24"
FEATURE = KingdomResearch("earned-rewards", "Example_Guild", 0x7300, 0x139C,
                          3, 3000, 15, 15, 0x7301, 0x7302, "Example Research")
GOLD = '''function give_gold(agent thisagent, integer amount)
declare
begin
    if (amount > 0)
        begin
            // Preserve the stock presentation/write order.
            $createeffector(thisagent,"got_gold",0, Amount);
            $adjustattribute(thisagent,#ATTRIB_gold,amount);
            $debugout(thisagent's "title","got",amount,"gold.");
        end
end
'''
XP = '''function give_exp(agent thisagent, integer new_exp)
declare
    integer exp, exp_level;
begin
    exp_level = $getattribute(thisagent,#ATTRIB_experiencelevel);
    new_exp = new_exp / exp_level;
    exp += new_exp;
    $setattribute(thisagent,#ATTRIB_experience,exp);
end
'''


class KingdomResearchTests(unittest.TestCase):
    def setUp(self):
        self.record = registration(UUID, FEATURE, "EXG")
        self.bindings = ((self.record, FEATURE.parent_building),)

    def test_schema_roundtrip_and_stable_namespace(self):
        self.assertEqual(parse_kingdom_research(kingdom_research_mapping(FEATURE)), FEATURE)
        self.assertEqual(registration(UUID.upper(), FEATURE, "EXG"), self.record)
        validate_registration(self.record)
        other = registration(UUID, replace(FEATURE, feature_key="other"), "EXG")
        self.assertNotEqual(other.identity, self.record.identity)
        self.assertNotEqual(other.completion_attribute, self.record.completion_attribute)
        self.assertEqual(self.record.action_control_id + 1000, FEATURE.price_control_id)

    def test_invalid_fields_fail_closed(self):
        for name, value in (("price", True), ("price", -1), ("required_level", 4),
                            ("gold_bonus_percent", 101), ("experience_bonus_percent", -1),
                            ("action_control_id", 0x139C), ("feature_key", "../name"),
                            ("parent_building", 'unsafe"'), ("completion_text", "x\0y"),
                            ("progress_control_id", FEATURE.price_control_id),
                            ("descriptor_template_control_id", 0x1400),
                            ("active_effector", 'x"'), ("active_effector", None),
                            ("active_effector", '0Bad'), ("active_effector", 'a'*65)):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                parse_kingdom_research(dict(kingdom_research_mapping(FEATURE), **{name: value}))

    def test_wire_roundtrip_truncation_collisions_and_opt_in(self):
        extras = (EquipmentRegistration(0x800001, 0, "ZN01"), NativeTimingFeature())
        visual = replace(self.record, active_effector="Example_Active")
        for features in ((self.record,), (self.record, *extras), (visual,), (visual, *extras)):
            registry = normalize_runtime_features(features)
            wire = encode_runtime_feature_registry(registry)
            self.assertEqual(struct.unpack_from('<I', wire, 4)[0], 6 if features[0].active_effector else 5)
            self.assertEqual(decode_runtime_feature_registry(wire), registry)
            self.assertIn('manager.kingdom-research.v1', effective_runtime_capabilities((), registry))
            for length in range(len(wire)):
                with self.assertRaises(ValueError): decode_runtime_feature_registry(wire[:length])
        for duplicate in (self.record, replace(self.record, identity='f'*32),
                          replace(self.record, identity='f'*32, action_control_id=0x7900,
                                  completion_attribute=0xD1234567)):
            with self.assertRaises(ValueError): normalize_runtime_features((self.record, duplicate))
        with self.assertRaises(ValueError): validate_registration(replace(self.record, building_family=ord('X')))
        self.assertNotIn('manager.kingdom-research.v1', effective_runtime_capabilities(
            ('manager.kingdom-research.v1',), normalize_runtime_features(())))

    def test_stock_compiler_accepts_generated_service_and_real_award_insertions(self):
        game = os.environ.get('MAJESTY_BETA2_EXE')
        if not game: self.skipTest('stock compiler fixture not supplied')
        root = Path(game).parent / 'SDK'
        sources = root / 'OriginalQuests/GPLMx'
        stock = {}
        for path in (sources/'mx_Monster_Deaths.gpl', sources/'TaskModules/Subtasks/mx_give_exp.gpl'):
            for item in parse_gpl(path.read_text(encoding='cp1252')).items:
                if item.normalized_name in ('give_gold', 'give_exp'): stock[item.normalized_name] = item
        # Compile the optional visual functions and their completion insertion
        # with the actual stock compiler, too (no package preparation).
        visual = replace(self.record, active_effector="Example_Active")
        result = compose_service(SemanticMergeResult((), ()), ((visual, FEATURE.parent_building),), stock)
        text = (sources/'mx_defines.gpl').read_text(encoding='cp1252') + '\n' + result.render()
        # Isolated compiler fixture, not a Manager profile or deployed mod.
        with tempfile.TemporaryDirectory(prefix='kingdom-research-') as directory:
            fixture = Path(directory)
            (fixture/'fixture.gpl').write_text(text, encoding='cp1252')
            (fixture/'fixture.gplproj').write_text('source="fixture.gpl"\n', encoding='ascii')
            run = subprocess.run((str(root/'Gplbcc.exe'), '-in', 'fixture.gplproj',
                '-out', 'fixture.bcd', '-stdout'), cwd=fixture, capture_output=True,
                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(run.returncode, 0, (run.stdout+run.stderr).decode('cp1252'))
            self.assertTrue((fixture/'fixture.bcd').is_file(), (run.stdout+run.stderr).decode('cp1252'))

    def test_native_lifecycle_fingerprints_match_stock(self):
        game = os.environ.get('MAJESTY_BETA2_EXE')
        if not game: self.skipTest('stock executable fixture not supplied')
        from test_occupant_runtime_profiles import PeImage
        image = PeImage(game)
        source = (Path(__file__).resolve().parents[1]/'runtime/KingdomResearchRuntime.inl').read_text()
        hashes = re.findall(r'hash\((0x[0-9A-F]+)u, (0x[0-9A-F]+|\d+)\) == (0x[0-9A-F]+)u', source)
        self.assertEqual(len(hashes), 8)
        for rva, size, expected in hashes:
            value = 2166136261
            for byte in image.read(int(rva, 16), int(size, 0)): value = ((value ^ byte)*16777619)&0xffffffff
            self.assertEqual(value, int(expected, 16), rva)

    def test_small_awards_retain_exact_fraction(self):
        total = carry = 0
        for _ in range(100):
            value, carry = award_with_carry(1, 15, carry)
            total += value
        self.assertEqual((total, carry), (115, 0))
        self.assertEqual(award_with_carry(0, 15, 90), (0, 90))
        self.assertEqual(award_with_carry(1, 15, 90), (2, 5))

    def test_stock_integer_binary_arithmetic_has_fixed_point_conversion(self):
        game = os.environ.get('MAJESTY_BETA2_EXE')
        if not game: self.skipTest('stock executable fixture not supplied')
        from test_occupant_runtime_profiles import PeImage
        image = PeImage(game)
        # GplInteger's original vtable, not a Python simulation of its math.
        for slot, target in ((1, 0x59A860), (0x28//4, 0x59A710),
                             (0x60//4, 0x59A730), (0x6C//4, 0x59A850)):
            self.assertEqual(struct.unpack('<I', image.read(0x36034C+slot*4, 4))[0], target)
        # Both integer subtraction and addition shift left 10 before the
        # operation and arithmetic-right 10 afterwards. INT_MAX becomes -1.
        self.assertEqual(image.read(0x19ABDB, 15), bytes.fromhex(
            'c1 e6 0a 2b 30 8b 42 28 8b cf c1 fe 0a ff d0'))
        self.assertEqual(image.read(0x19AB81, 15), bytes.fromhex(
            'c1 e6 0a 03 30 8b 42 28 8b cf c1 fe 0a ff d0'))

    def test_overflow_never_wraps_or_loses_original_base(self):
        self.assertEqual(award_with_carry(MAX_INTEGER, 100, 0), (MAX_INTEGER, 0))
        for base in (1, 7, 100, 999, 2000000000, MAX_INTEGER):
            for percent in (0, 1, 15, 100):
                award, carry = award_with_carry(base, percent, 31)
                self.assertGreaterEqual(award, base)
                self.assertLessEqual(award, MAX_INTEGER)
                self.assertTrue(0 <= carry < 100)

    def test_service_has_no_scheduler_and_uses_saved_typed_state(self):
        text = service_source(self.bindings)
        parsed = parse_gpl(text)
        self.assertEqual(len(parsed.items), 9)
        for forbidden in ("NewThread", "RunThread", "KillThread", "CreateAgent", "CreateEffector"):
            self.assertNotIn(forbidden, text)
        self.assertIn('"GplAIRoot"', text)
        self.assertIn('PendingPlayer = $ListMember(Pending, Index)', text)
        self.assertIn('Completed << PendingPlayer', text)
        self.assertIn('Hero\'s "subtype" != "Hero"', text)
        self.assertIn('$MM_KR_Eligible(Building', text)
        self.assertIn('$MM_KR_Order(PendingBuilding', text)

    def test_visual_service_is_optional_idempotent_and_uses_original_payer(self):
        self.assertNotIn('_Visual', service_source(self.bindings))
        record = replace(self.record, active_effector="Example_Active")
        text = service_source(((record, FEATURE.parent_building),))
        self.assertEqual(len(parse_gpl(text).items), 11)
        for forbidden in ('NewThread', 'RunThread', 'KillThread', 'CreateAgent'):
            self.assertNotIn(forbidden, text)
        self.assertIn('$CheckEffector(Building, "Example_Active")', text)
        self.assertIn('$CreateEffector(Building, "Example_Active", 1, "Infinite")', text)
        self.assertIn('if (Present) $DeleteEffector', text)
        self.assertIn('CompletedPlayer = PendingPlayer;', text)
        self.assertIn('_Visuals(Building, CompletedPlayer)', text)
        self.assertLess(text.index('_done" = Completed;'), text.index('_Visuals(Building, CompletedPlayer)'))
        self.assertIn('$GetUnitPlayerNumber(Building) == Player', text)
        self.assertIn('if ((Operation == 2) && Matched)', text)

    def test_v6_rejects_missing_visual_and_bad_names(self):
        plain = bytearray(encode_runtime_feature_registry((self.record,)))
        struct.pack_into('<I', plain, 4, 6)
        for name in (b'', b'1Bad', b'x\0bad', b'x'*65, b'\xff'):
            wire = bytes(plain)+struct.pack('<I', len(name))+name
            with self.assertRaises(ValueError): decode_runtime_feature_registry(wire)
        feature = replace(FEATURE, active_effector="Example_Active")
        self.assertEqual(parse_kingdom_research(kingdom_research_mapping(feature)), feature)
        self.assertEqual(registration(UUID, feature, 'EXG').active_effector, 'Example_Active')

    def test_reward_math_uses_native_integer_storage_not_gpl_fixed_point(self):
        text = service_source(self.bindings)
        self.assertIn('$MM_KR_AwardBonus(Base, Percent, Carry)', text)
        self.assertIn('$MM_KR_CapAdd(Result, $', text)
        self.assertNotIn('function MM_KR_CapAdd', text)
        for unsafe in ('2147483647', 'Base <=', 'Base /', 'Base %', 'Base *'):
            self.assertNotIn(unsafe, text)

    def test_only_guarded_gold_and_post_divisor_xp_insertions(self):
        stock = {item.normalized_name: item for item in parse_gpl(GOLD + XP).items}
        result = compose_service(SemanticMergeResult((), ()), self.bindings, stock)
        modified = {item.normalized_name: item.text for item in result.items}
        gold = modified["give_gold"]
        self.assertEqual(gold.replace("Amount = $MM_KR_Gold(ThisAgent, Amount);\n\t\t\t", ""), stock["give_gold"].text)
        self.assertEqual(modified["give_exp"].replace("\n\tnew_exp = $MM_KR_XP(ThisAgent, new_exp);", ""), stock["give_exp"].text)
        with self.assertRaisesRegex(ValueError, "collides"):
            compose_service(result, self.bindings, stock)

    def test_unselected_has_zero_generated_work(self):
        original = SemanticMergeResult((), ())
        self.assertEqual(service_source(()), "")
        self.assertIs(compose_service(original, (), {}), original)

    def test_changed_award_boundary_is_rejected(self):
        stock = {item.normalized_name: item for item in parse_gpl(GOLD + XP).items}
        for name, text in (("give_gold", GOLD.replace("got_gold", "other")),
                           ("give_exp", XP.replace("new_exp / exp_level", "new_exp * exp_level"))):
            altered = parse_gpl(text).items[0]
            with self.subTest(name=name), self.assertRaises(ValueError):
                compose_service(SemanticMergeResult((altered,), ()), self.bindings, stock)
