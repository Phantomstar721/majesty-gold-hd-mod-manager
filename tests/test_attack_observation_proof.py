from dataclasses import replace
import hashlib
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from majesty_cam.attack_observation import validate_bindings
from majesty_cam.attack_observation_proof import (build_proof, encode, decode,
    from_composed_output, BASELINES, BASELINE_SHA256, PUBLIC_BASELINE_SHA256, STOCK_COMBAT_NAMES,
    audited_baseline, validate_output)
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.gpl import parse_gpl, DefinitionKind as Kind
from test_attack_observation import FEATURE, XML, GPL
from test_bcd import compiled


class ProofTests(unittest.TestCase):
    def test_installed_baseline_handoff_and_final_validation_agree(self):
        root=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        if not all((root/path).is_file() for path in BASELINES):
            self.skipTest('installed stock archives unavailable')
        # Only read installed inputs. No Manager profile is composed or written.
        proof=from_composed_output(root,self.bindings,self.output)
        validate_output(decode(encode(proof)),(self.output,))

    def test_final_validation_accepts_both_whole_bundles_and_checks_actual_output(self):
        common=compiled((Kind.FUNCTION,"Released"))
        base=compiled((Kind.FUNCTION,"make_attack"),(Kind.FUNCTION,"BaseOnly"))
        expansion=compiled((Kind.FUNCTION,"make_attack"),(Kind.FUNCTION,"ExpansionOnly"))
        for outputs in ((self.output,), (common,base,expansion)):
            original=build_proof(self.bindings,self.baseline,outputs)
            for bundle in (BASELINE_SHA256,PUBLIC_BASELINE_SHA256):
                proof=replace(original,digests=tuple(bytes.fromhex(d) for d in bundle)+original.digests[6:])
                validate_output(decode(encode(proof)),outputs)
                for changed in (outputs[:-1], (*outputs[:-1],outputs[-1]+b'changed')):
                    with self.assertRaisesRegex(ValueError,'compiled output'):
                        validate_output(proof,changed)
                if len(outputs)==3:
                    with self.assertRaisesRegex(ValueError,'compiled output'):
                        validate_output(proof,(common,expansion,base))
            mixed=(PUBLIC_BASELINE_SHA256[0],*BASELINE_SHA256[1:])
            self.assertFalse(audited_baseline(mixed))
            with self.assertRaisesRegex(ValueError,'stock bundle'):
                validate_output(replace(original,digests=tuple(bytes.fromhex(d) for d in mixed)+original.digests[6:]),outputs)

    def test_native_baseline_constants_match_python(self):
        header = (Path(__file__).parents[1] / 'runtime/AttackObservationBaseline.h').read_text()
        original, public = header.split('publicChanged[4][32]=', 1)
        def digests(text):
            return tuple(bytes(int(x, 16) for x in row.split(',')).hex()
                         for row in re.findall(r'\{((?:0x[0-9a-f]{2},?)+)\}', text))
        self.assertEqual(digests(original), BASELINE_SHA256)
        changed = digests(public)
        self.assertEqual((changed[0], BASELINE_SHA256[1], changed[1], changed[2],
                          BASELINE_SHA256[4], changed[3]), PUBLIC_BASELINE_SHA256)

    def setUp(self):
        records = parse_descriptions(XML).records
        source = parse_gpl(GPL)
        self.bindings = validate_bindings((("owner", (FEATURE,), records, (source,)),), records, source.items)
        self.baseline = tuple(compiled((Kind.FUNCTION, f"stock_{i}")) for i in range(6))
        self.output = compiled((Kind.FUNCTION, "Released"), (Kind.FUNCTION, "make_attack"))

    def test_hashes_the_actual_compiled_output_and_alias(self):
        proof = build_proof(self.bindings, self.baseline, self.output)
        self.assertEqual(proof.digests[6], hashlib.sha256(self.output).digest())
        self.assertEqual(decode(encode(proof)), proof)
        # A different composed function changes its proof; no isolated DLL/BCD hash.
        modified = self.output.replace(b"Released", b"RELEASED")
        second = build_proof(self.bindings, self.baseline, modified)
        self.assertNotEqual(second.digests[6], proof.digests[6])

    def test_missing_callbacks_and_shadowing_native_aliases(self):
        for output in (compiled(), compiled((Kind.FUNCTION,"Released")),
                       compiled((Kind.FUNCTION,"Released"),(Kind.FUNCTION,"make_attack"),(Kind.PROTOTYPE,"WHP_ReleaseId"))):
            with self.subTest(output=output), self.assertRaises(ValueError):
                build_proof(self.bindings,self.baseline,output)

    def test_optional_archives_cannot_override_any_protected_definition(self):
        for name in ("Released", "WHP_ImpactId", "make_attack"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,"overrides"):
                build_proof(self.bindings,self.baseline,self.output,(compiled((Kind.FUNCTION,name)),))
        extra=compiled((Kind.FUNCTION,"quest_private"))
        self.assertEqual(len(build_proof(self.bindings,self.baseline,self.output,(extra,extra)).digests),8)

    def test_standard_function_not_changed_by_profile_is_not_a_conflict(self):
        optional=compiled((Kind.FUNCTION,"gettohit"))
        proof=build_proof(self.bindings,self.baseline,self.output,(optional,))
        self.assertNotIn('gettohit',proof.protected_names)
        changed=compiled((Kind.FUNCTION,"Released"),(Kind.FUNCTION,"make_attack"),(Kind.FUNCTION,"gettohit"))
        with self.assertRaisesRegex(ValueError,'overrides'):
            build_proof(self.bindings,self.baseline,changed,(optional,))

    def test_unrelated_baseline_override_is_allowed_but_still_hash_pinned(self):
        # A quest can replace an unrelated baseline entry point. Its actual
        # bytes remain required by the native loader's digest admission check.
        override=compiled((Kind.FUNCTION,"stock_0"),(Kind.FUNCTION,"quest_private"))
        proof=build_proof(self.bindings,self.baseline,self.output,(override,))
        self.assertEqual(proof.digests[-1],hashlib.sha256(override).digest())

    def test_every_truncation_duplicate_and_trailing_bytes_rejected(self):
        proof=build_proof(self.bindings,self.baseline,self.output)
        data=encode(proof)
        for n in range(len(data)):
            with self.subTest(length=n), self.assertRaises(ValueError): decode(data[:n])
        with self.assertRaises(ValueError): decode(data+b"x")
        with self.assertRaises(ValueError): encode(replace(proof,digests=(*proof.digests[:6],proof.digests[0])))

    def test_protected_names_are_bounded_and_canonical(self):
        proof=build_proof(self.bindings,self.baseline,self.output)
        for names in (("make_attack", "make_attack"), ("z", "a"),
                      ("MAKE_ATTACK",), ("#",), ("#1bad",), ("1bad",),
                      ("bad\x00name",), ("a"*129,)):
            with self.subTest(names=names), self.assertRaises(ValueError):
                encode(replace(proof,protected_names=names))
        for names in (("#constant",), ("_callback2",)):
            candidate=replace(proof,protected_names=names)
            self.assertEqual(decode(encode(candidate)),candidate)

    def test_composed_handoff_reads_all_baselines_and_filters_unsafe_quest_files(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            for path,data in zip(BASELINES,self.baseline):
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            (root/"Data/allowed.bcd").write_bytes(compiled((Kind.FUNCTION,"quest_private")))
            (root/"Data/overriding.bcd").write_bytes(compiled((Kind.FUNCTION,"make_attack")))
            with self.assertRaisesRegex(ValueError,"baseline archives"):
                from_composed_output(root,self.bindings,self.output)
            with patch("majesty_cam.attack_observation_proof.BASELINE_SHA256",tuple(hashlib.sha256(data).hexdigest() for data in self.baseline)):
                proof=from_composed_output(root,self.bindings,self.output)
                self.assertEqual(len(proof.digests),8)
                self.assertEqual(proof.digests[6],hashlib.sha256(self.output).digest())

    def test_missing_ambiguous_or_opaque_input_is_not_a_proof(self):
        for bindings,baseline,output in (((),self.baseline,self.output),
            (self.bindings*2,self.baseline,self.output),(self.bindings,self.baseline[:-1],self.output),
            (self.bindings,self.baseline,b"opaque")):
            with self.assertRaises(ValueError): build_proof(bindings,baseline,output)

    def test_dataset_proof_requires_complete_effective_callbacks_in_both_views(self):
        common=compiled((Kind.FUNCTION,"Released"))
        base=compiled((Kind.FUNCTION,"make_attack"),(Kind.FUNCTION,"BaseOnly"))
        expansion=compiled((Kind.FUNCTION,"make_attack"),(Kind.FUNCTION,"ExpansionOnly"))
        proof=build_proof(self.bindings,self.baseline,(common,base,expansion))
        self.assertTrue(proof.scoped)
        self.assertEqual(decode(encode(proof)),proof)
        for outputs in ((common,base),(common,base,compiled((Kind.FUNCTION,"ExpansionOnly")))):
            with self.assertRaises(ValueError):build_proof(self.bindings,self.baseline,outputs)
        proof=build_proof(self.bindings,self.baseline,(common,base,expansion),(compiled((Kind.FUNCTION,"ExpansionOnly")),))
        self.assertNotIn('expansiononly',proof.protected_names)
        self.assertIn('make_attack',proof.protected_names)
        self.assertEqual(decode(encode(proof)),proof)

    def test_dependent_native_aliases_are_protected_in_all_loads(self):
        alias="Placement_Commit"
        optional=compiled((Kind.FUNCTION,alias))
        with self.assertRaisesRegex(ValueError,"overrides"):
            build_proof(self.bindings,self.baseline,self.output,(optional,),extra_protected_names=(alias,))
        baseline=(optional,*self.baseline[1:])
        with self.assertRaisesRegex(ValueError,"baseline"):
            build_proof(self.bindings,baseline,self.output,extra_protected_names=(alias,))
