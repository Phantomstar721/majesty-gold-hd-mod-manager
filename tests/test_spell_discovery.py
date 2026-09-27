from dataclasses import replace
import unittest
import xml.etree.ElementTree as ET

from majesty_cam.spell_policy import SpellPolicyDiscovery, SpellPolicyProvider, feature_mapping, parse_feature
from majesty_cam.spell_discovery import discover, compose_discovered, transform_descriptions
from majesty_cam.descriptions import merge_descriptions
from majesty_cam.gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from test_spell_policy import PROVIDERS, CONSUMERS, CAST

POLICY = SpellPolicyDiscovery("policy",("basic",),("example_special",),(),(),("Area_Hit",),(),("Example_Hit",))
BINDINGS = (("provider",POLICY),
            ("provider",SpellPolicyProvider("block","block-direct-projectile","Example_Block")),
            ("provider",SpellPolicyProvider("suppress","suppress-special-spell","Example_Suppress")))
XML = '''<Majesty><Description type="Action" ID="AB01" Name="example_special"><Game><Flags value="IsSpell"/></Game>
<Engine><Script type="0" cProc="0" GPLFunction="Example_Cast"/></Engine></Description>
<Description type="Unit" subType="Projectile" ID="AB02" Name="Bolt"><Engine><Script type="0" cProc="0" GPLFunction="Example_Hit"/></Engine></Description>
<Description type="Unit" subType="Projectile" ID="AB03" Name="Area"><Engine><Script type="0" cProc="0" GPLFunction="Area_Hit"/></Engine></Description></Majesty>'''


class SpellDiscoveryTests(unittest.TestCase):
    def test_consumers_need_no_declarations_and_area_is_untouched(self):
        self.assertEqual(parse_feature(feature_mapping(POLICY)),POLICY)
        plan = discover(BINDINGS,tuple(ET.fromstring(XML)))
        self.assertEqual(plan.impacts,("Example_Hit",))
        result = merge_descriptions(b"<Majesty/>",(("consumer",XML),))
        updated = transform_descriptions(result,plan)
        self.assertIn(plan.actions[0].wrapper("Validate").encode(),updated.payload)
        self.assertNotIn(b"MM_SP_",result.payload)
        gpl = SemanticMergeResult(parse_gpl(PROVIDERS+CONSUMERS+CAST).items,())
        generated = compose_discovered(gpl,BINDINGS,plan,None)
        names = {i.normalized_name for i in generated.items}
        self.assertIn("mm_blockdirectprojectile",names)
        self.assertNotIn("area_hit",names)

    def test_projectile_launched_action_does_not_require_cast_script(self):
        xml = XML.replace('<Script type="0" cProc="0" GPLFunction="Example_Cast"/>','<Projectile value="Bolt"/>')
        plan = discover(BINDINGS,tuple(ET.fromstring(xml)))
        self.assertEqual(plan.actions[0].cast,"")
        gpl = SemanticMergeResult(parse_gpl(PROVIDERS+CONSUMERS+CAST).items,())
        compose_discovered(gpl,BINDINGS,plan,None)

    def test_ambiguous_policy_and_unclassified_content_fail_explicitly(self):
        for bindings,xml in (
            (BINDINGS,XML.replace('Name="example_special"','Name="Unclassified"')),
            ((("provider",replace(POLICY,suppression_exempt_actions=("example_special",))),*BINDINGS[1:]),XML),
            (BINDINGS,XML.replace('GPLFunction="Example_Cast"','GPLFunction="Example_Hit"')),
        ):
            with self.assertRaises(ValueError): discover(bindings,tuple(ET.fromstring(xml)))


if __name__ == "__main__": unittest.main()
