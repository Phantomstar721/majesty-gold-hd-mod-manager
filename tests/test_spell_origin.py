from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import re
import unittest

from majesty_cam.spell_origin import (SOURCE, SpellOrigin, feature_mapping, parse_feature,
    compose_service, validate_service, CAPABILITY)
from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.compose import compile_gpl, _derive_runtime_capabilities
from gpl_sampler_harness import Agent, SamplerHarness
from test_occupant_runtime_profiles import PeImage


class SpellOriginTests(unittest.TestCase):
    def vm(self):
        vm = SamplerHarness(SOURCE)
        vm.calls["isvalidgamepiece"] = lambda a: isinstance(a, Agent) and a.alive
        original_add = vm.calls["addattribute"]
        def add(agent, name, kind, value):
            self.assertEqual(kind, "agentref")
            return original_add(agent, name, kind, value)
        vm.calls["addattribute"] = add
        return vm

    def agent(self, kind="hero"):
        a = Agent()
        a.fields["type"] = kind
        a.fields["subtype"] = kind
        return a

    def test_birth_periodic_child_and_saved_reference_graph(self):
        vm = self.vm()
        hero, spell, child = self.agent(), self.agent("spell"), self.agent("spell")
        self.assertEqual(vm.call("MM_SO_Record", spell, hero), 1)
        self.assertIs(vm.call("MM_OriginalCaster", spell), hero)
        self.assertEqual(vm.call("MM_SO_Record", child, spell), 1)
        self.assertIs(vm.call("MM_OriginalCaster", child), hero)
        # Model only the saved reference graph, not Majesty's actual save codec.
        loaded_hero, loaded_spell, loaded_child = deepcopy((hero, spell, child))
        self.assertIs(vm.call("MM_OriginalCaster", loaded_child), loaded_hero)
        self.assertIs(vm.call("MM_OriginalCaster", loaded_spell), loaded_hero)
        loaded_hero.alive = False
        self.assertIsNone(vm.call("MM_OriginalCaster", loaded_child))
        self.assertEqual(vm.call("MM_SO_Record", spell, self.agent()), 0)
        self.assertIs(vm.call("MM_OriginalCaster", spell), hero)

    def test_sovereign_nonhero_and_absent_provenance_are_null(self):
        vm = self.vm()
        sovereign, child = self.agent("spell"), self.agent("spell")
        self.assertIsNone(vm.call("MM_OriginalCaster", sovereign))
        self.assertEqual(vm.call("MM_SO_Record", child, sovereign), 1)
        self.assertIsNone(vm.call("MM_OriginalCaster", child))
        self.assertIsNone(vm.call("MM_OriginalCaster", self.agent("monster")))
        self.assertIsNone(vm.call("MM_OriginalCaster", None))

    def test_schema_capability_and_literal_service(self):
        f = SpellOrigin("origin")
        self.assertEqual(f, parse_feature(feature_mapping(f)))
        capabilities, _ = _derive_runtime_capabilities((CAPABILITY,),has_private_activity_text=False)
        self.assertNotIn(CAPABILITY, capabilities)
        capabilities, _ = _derive_runtime_capabilities((),has_private_activity_text=False,has_spell_origin=True)
        self.assertIn(CAPABILITY, capabilities)
        result = compose_service(SemanticMergeResult((), ()),True)
        funcs = {i.normalized_name:i.text for i in result.items}
        counts = {k:1 for k in funcs}
        validate_service(funcs,True,counts)
        with self.assertRaises(ValueError): validate_service(funcs,False,counts)
        funcs["mm_so_record"] = funcs["mm_so_record"].replace('"agentref"','"integer"')
        with self.assertRaises(ValueError): validate_service(funcs,True,counts)

    def test_hidden_heroes_and_failed_attribute_creation(self):
        vm = self.vm()
        hero = self.agent()
        for kind in ("hidden", "invisible", "camouflaged"):
            hero.fields["type"] = kind
            self.assertIs(vm.call("MM_OriginalCaster", hero), hero)
        vm.calls["addattribute"] = lambda *args: None
        self.assertEqual(vm.call("MM_SO_Record", self.agent("spell"), hero), 0)

    def test_compiles(self):
        compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
        if not compiler.is_file(): self.skipTest("stock compiler unavailable")
        result = SemanticMergeResult(parse_gpl(SOURCE).items, ())
        with TemporaryDirectory(prefix="spell-origin-") as tmp:
            compile_gpl(result.emit_project_source_set(),compiler,Path(tmp)/"compiler")

    def verify_native(self, profile, variable):
        path = os.environ.get(variable)
        if not path: self.skipTest(variable+" not set")
        image = PeImage(path)
        header = (Path(__file__).parents[1]/"runtime/SpellOriginProfiles.h").read_text()
        row = re.search(r"k"+profile+r"\{([^}]+)\}",header).group(1)
        create, argument, unit, birth, expected = [int(v,16) for v in row.split(",")]
        value = 2166136261
        for byte in image.read(create,0x175): value = ((value ^ byte)*16777619)&0xFFFFFFFF
        self.assertEqual(value,expected)
        self.assertEqual(image.read(create,5),bytes.fromhex("83EC2C5355"))
        self.assertEqual(image.target(create+0xF),argument)
        self.assertEqual(image.target(create+0x35),unit)
        self.assertEqual(image.target(create+0x168),birth)
        self.assertEqual(image.read(create+0x139,4),bytes.fromhex("8BD885DB"))
    def test_public(self): self.verify_native("Public","MAJESTY_PUBLIC_EXE")
    def test_beta2(self): self.verify_native("Beta2","MAJESTY_BETA2_EXE")
    def test_gog(self): self.verify_native("Gog","MAJESTY_GOG_EXE")


if __name__ == "__main__": unittest.main()
