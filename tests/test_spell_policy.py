from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from majesty_cam.gpl import parse_gpl, DefinitionKind, SemanticMergeResult
from majesty_cam.spell_policy import (SpellPolicyProvider, DirectProjectileImpact,
    SpecialSpell, validate_bindings, compose_guards, feature_mapping, parse_feature,
    BLOCK, SUPPRESS)

BLOCKER = SpellPolicyProvider("block", "block-direct-projectile", "Example_Block")
SUPPRESSOR = SpellPolicyProvider("suppress", "suppress-special-spell", "Example_Suppress")
IMPACT = DirectProjectileImpact("impact", "Example_Hit")
SPECIAL = SpecialSpell("special", "example_special", "Example_Check", "Example_Cast")
PROVIDERS = '''function Example_Block(agent Source, agent Target) is boolean
declare
begin
return False;
end
function Example_Suppress(agent Source, string Spell) is boolean
declare
begin
return False;
end
'''
CONSUMERS = '''function Example_Hit(agent Shooter, agent Victim)
declare
begin
$Example_Payload(Shooter, Victim);
$Example_Chill(Victim);
end
function Example_Payload(agent Shooter, agent Victim)
declare
begin
end
function Example_Chill(agent Victim)
declare
begin
end
function Example_Check(agent Subject) is integer
declare
begin
return 1;
end
function Example_Cast(agent Actor, agent Target)
declare
begin
$Example_Payload(Actor, Target);
end
'''
CAST = '''function Cast(agent Caster, string Name, agent Target, string Arg)
declare
begin
$Example_Payload(Caster, Target);
end
'''
ACTION = '''<Description type="Action" Name="example_special"><Engine>
<Script type="0" cProc="0" GPLFunction="Example_Cast"/></Engine><Game>
<ValidationScript value="Example_Check"/></Game></Description>'''


class SpellPolicyTests(unittest.TestCase):
    def packages(self, providers=(BLOCKER, SUPPRESSOR), consumers=(IMPACT, SPECIAL),
                 source=CONSUMERS, action=ACTION):
        return (("provider", providers, (parse_gpl(PROVIDERS),), ()),
                ("consumer", consumers, (parse_gpl(source),), (ET.fromstring(action),)))

    def compose(self, packages=None):
        packages = self.packages() if packages is None else packages
        bindings = validate_bindings(packages)
        items = tuple(i for _, _, sources, _ in packages for s in sources for i in s.items)
        stock = parse_gpl(CAST).require(DefinitionKind.FUNCTION, "cast")
        return compose_guards(SemanticMergeResult(items, ()), bindings, lambda _: {stock.key: stock})

    def test_roundtrip_and_strict_fields(self):
        from majesty_cam.package import _runtime_feature_mapping, parse_mod_definition
        for feature in (BLOCKER, SUPPRESSOR, IMPACT, SPECIAL):
            data = feature_mapping(feature)
            self.assertEqual(feature, parse_feature(data))
            self.assertEqual(data, _runtime_feature_mapping(feature))
            definition = parse_mod_definition({
                "schema_version": 3, "mod_id": "12345678-1234-1234-1234-123456789012",
                "internal_name": "Example", "display_name": "Example",
                "custom_buildings": [], "runtime_features": [data]})
            self.assertEqual(definition.runtime_features, (feature,))
            with self.assertRaises(ValueError):
                parse_feature({**data, "extra": True})
        with self.assertRaises(ValueError):
            parse_feature({**feature_mapping(BLOCKER), "policy": "all-damage"})

    def test_impact_guards_entire_payload_not_global_damage(self):
        result = self.compose()
        text = next(i.text for i in result.items if i.normalized_name == "example_hit")
        self.assertLess(text.index(BLOCK), text.index("$Example_Payload"))
        self.assertLess(text.index(BLOCK), text.index("$Example_Chill"))
        self.assertEqual(text.count(BLOCK), 1)
        self.assertNotIn("spell_attack", "\n".join(i.text for i in result.items))

    def test_validation_and_both_execution_boundaries(self):
        text = {i.normalized_name: i.text for i in self.compose().items}
        self.assertIn(f'if (${SUPPRESS}(Subject, "example_special")) return 0;', text["example_check"])
        self.assertIn(f'if (${SUPPRESS}(Actor, "example_special")) return;', text["example_cast"])
        self.assertIn(f'if (${SUPPRESS}(Caster, Name)) return;', text["cast"])
        self.assertLess(text["cast"].index(SUPPRESS), text["cast"].index("$Example_Payload"))
        self.assertIn('SpellName == "example_special"', text[SUPPRESS.casefold()])

    def test_no_provider_means_no_changes_or_stock_load(self):
        packages = self.packages(providers=())
        before = SemanticMergeResult(tuple(i for _, _, ss, _ in packages for s in ss for i in s.items), ())
        self.assertEqual(before, compose_guards(before, validate_bindings(packages)))

    def test_order_independent_and_first_block_consumes_once(self):
        packages = self.packages()
        self.assertEqual({i.key: i.text for i in self.compose(packages).items},
                         {i.key: i.text for i in self.compose(tuple(reversed(packages))).items})
        result = self.compose()
        block = next(i.text for i in result.items if i.normalized_name == BLOCK.casefold())
        self.assertIn("if ($Example_Block(Source, Target)) return True;", block)

    def test_reject_bad_ownership_signature_duplicates_and_xml(self):
        for packages in (
            self.packages(source=CONSUMERS.replace("agent Shooter, agent Victim", "agent Shooter")),
            self.packages(consumers=(IMPACT, IMPACT)),
            self.packages(action=ACTION.replace("Example_Check", "Unrelated_Check")),
            self.packages(action=ACTION.replace('type="0"', 'type="1"')),
            (*self.packages(), ("other", (), (parse_gpl(PROVIDERS),), ())),
        ):
            with self.assertRaises(ValueError):
                validate_bindings(packages)

    def test_original_bodies_are_preserved(self):
        result = {i.normalized_name: i for i in self.compose().items}
        for original in parse_gpl(CONSUMERS).items:
            generated = result[original.normalized_name].text
            if original.normalized_name in ("example_hit", "example_check", "example_cast"):
                generated = __import__("re").sub(r"\n    if \(\$MM_[^\n]+\n", "", generated)
            self.assertEqual(original.text, generated)

    def test_multiple_providers_short_circuit_and_source_cast_shapes(self):
        other = replace(BLOCKER, callback_symbol="A_OtherBlock")
        source = parse_gpl(PROVIDERS.replace("Example_Block", "A_OtherBlock").split("function Example_Suppress")[0])
        packages = (*self.packages(), ("other", (other,), (source,), ()))
        block = next(i.text for i in self.compose(packages).items if i.normalized_name == BLOCK.casefold())
        self.assertLess(block.index("$A_OtherBlock"), block.index("$Example_Block"))
        self.assertEqual(block.count("return True;"), 2)
        from majesty_cam.spell_policy import signature
        sdk = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/OriginalQuests")
        for relative in ("GPL/TaskModules/Subtasks/Cast.gpl", "GPLMx/TaskModules/Subtasks/mx_Cast.gpl"):
            path = sdk / relative
            if path.is_file():
                item = parse_gpl(path.read_text()).require(DefinitionKind.FUNCTION, "Cast")
                signature(item, ("agent", "string", "agent", "string"))

    def test_generated_source_compiles_with_stock_compiler(self):
        compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
        if not compiler.is_file():
            self.skipTest("stock compiler not available")
        from majesty_cam.compose import compile_gpl
        with TemporaryDirectory(prefix="spell-policy-") as tmp:
            compile_gpl(self.compose().emit_project_source_set(), compiler, Path(tmp)/"compiler")


if __name__ == "__main__":
    unittest.main()
