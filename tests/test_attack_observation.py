from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from majesty_cam.attack_observation import (
    AttackObservation, CAPABILITY, FEATURE_TYPE, exports, feature_mapping,
    parse_feature, require_exact_profile, validate_bindings,
)
from majesty_cam.compose import ComposeError, SelectedMod, compose_package, resolve_attack_observation_bindings
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.gpl import parse_gpl
from majesty_cam.manager.capabilities import SUPPORTED_RUNTIME_CAPABILITIES
from majesty_cam.package import PackageFormatError, parse_mod_definition


FEATURE = AttackObservation("shots", "WHP", "Hunter", "Bolt", "Projectile", "Released")
XML = '''<Majesty>
<Description type="Unit" subType="Character" ID="HU01" Name="Hunter"><Engine version="1"/></Description>
<Description type="Action" subType="Standard" ID="AC01" Name="Bolt"><Engine version="1">
<Projectile value="Projectile"/><Script type="0" cProc="0" GPLFunction="Released"/>
</Engine></Description>
<Description type="Unit" subType="Projectile" ID="PR01" Name="Projectile"><Engine version="1">
<Script type="0" cProc="0" GPLFunction="make_attack"/>
</Engine></Description></Majesty>'''
GPL = '''function Released(agent Actor, agent Target)
begin
end
function make_attack(agent Actor, agent Target)
begin
end
'''
MOD_ID = "{00000000-0000-0000-0000-000000000001}"


class AttackObservationTests(unittest.TestCase):
    def setUp(self):
        self.records = parse_descriptions(XML).records
        self.source = parse_gpl(GPL)
        self.packages = ((MOD_ID, (FEATURE,), self.records, (self.source,)),)

    def test_eight_alias_signatures_match_consumer(self):
        self.assertEqual([len(args) for _, args in exports(FEATURE)], [2,3,3,2,4,1,3,5])
        self.assertEqual(exports(FEATURE)[0], ("WHP_AttackSettled", ("out integer", "agent")))
        self.assertEqual(exports(FEATURE)[-1][0], "WHP_ShotRetired")

    def test_parser_rejects_unsafe_unknown_or_malformed_fields(self):
        value = feature_mapping(FEATURE)
        self.assertEqual(parse_feature(value), FEATURE)
        for key, item in (("offset", 123), ("dll", "package.dll"), ("type", "unknown"),
                          ("actor", ""), ("api_prefix", "MM_Observer"),
                          ("api_prefix", "a"*47), ("projectile", True),
                          ("release_callback_symbol", "WHP_ReleaseId")):
            with self.subTest(key=key, item=item), self.assertRaises(ValueError):
                parse_feature(dict(value, **{key: item}))
        with self.assertRaises(ValueError): parse_feature({"type": FEATURE_TYPE})

    def test_schema_roundtrip_and_duplicate_identity(self):
        value = dict(schema_version=3, mod_id=MOD_ID, internal_name="Fixture",
                     display_name="Fixture", custom_buildings=[], runtime_features=[feature_mapping(FEATURE)])
        self.assertEqual(parse_mod_definition(value).runtime_features, (FEATURE,))
        value["runtime_features"] *= 2
        with self.assertRaises(PackageFormatError): parse_mod_definition(value)

    def test_effective_definition_binding(self):
        binding, = validate_bindings(self.packages, self.records, self.source.items)
        self.assertEqual(binding.owner, MOD_ID)
        self.assertEqual(binding.descriptions, self.records)

    def test_missing_or_overridden_callback(self):
        for source in (GPL.replace("Released", "Other"), GPL.replace("function Released", "function Released").replace("begin", "begin\n $Changed();", 1)):
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_bindings(self.packages, self.records, parse_gpl(source).items)

    def test_wrong_callback_signature(self):
        source = parse_gpl(GPL.replace("Released(agent Actor", "Released(integer Actor"))
        packages = ((MOD_ID, (FEATURE,), self.records, (source,)),)
        with self.assertRaisesRegex(ValueError, "expected"):
            validate_bindings(packages, self.records, source.items)

    def test_foreign_callback_owner(self):
        packages = ((MOD_ID, (FEATURE,), self.records, ()), ("other", (), (), (self.source,)))
        with self.assertRaisesRegex(ValueError, "package-owned"):
            validate_bindings(packages, self.records, self.source.items)

    def test_effective_resource_mismatch(self):
        for changed in (XML.replace('value="Projectile"', 'value="Other"'),
                        XML.replace('GPLFunction="Released"', 'GPLFunction="Other"'),
                        XML.replace('GPLFunction="make_attack"', 'GPLFunction="reflection"')):
            with self.subTest(xml=changed), self.assertRaises(ValueError):
                validate_bindings(self.packages, parse_descriptions(changed).records, self.source.items)

    def test_declared_bad_mapping_is_rejected_too(self):
        changed = parse_descriptions(XML.replace('value="Projectile"', 'value="Other"')).records
        with self.assertRaisesRegex(ValueError, "action/projectile"):
            validate_bindings(((MOD_ID,(FEATURE,),changed,(self.source,)),),changed,self.source.items)

    def test_duplicate_exports_and_actor_ownership(self):
        for second in (replace(FEATURE, feature_key="other"), replace(FEATURE, api_prefix="Other")):
            with self.subTest(feature=second), self.assertRaises(ValueError):
                validate_bindings((*self.packages,("other",(second,),self.records,(self.source,))), self.records,self.source.items)

    def test_native_export_cannot_be_shadowed_by_gpl(self):
        source = parse_gpl(GPL + "function WHP_ReleaseId()\nbegin\nend\n")
        with self.assertRaisesRegex(ValueError, "collides"):
            validate_bindings(self.packages,self.records,source.items)

    def test_profile_rejects_labels_without_a_supported_pe(self):
        with TemporaryDirectory() as tmp:
            exe = Path(tmp)/"MajestyHD.exe"
            for content in (b"Steam 1.5.2.24", b"Steam beta2 1.5.2.28", b"GOG 1.5.2.28"):
                exe.write_bytes(content)
                with self.assertRaisesRegex(ValueError,"audited"): require_exact_profile(exe)
            exe.unlink()
            with self.assertRaisesRegex(ValueError,"audited"): require_exact_profile(exe)

    def test_capability_is_derived_not_caller_asserted(self):
        from majesty_cam.compose import _derive_runtime_capabilities
        self.assertIn(CAPABILITY, SUPPORTED_RUNTIME_CAPABILITIES)
        caps, _ = _derive_runtime_capabilities((CAPABILITY,),has_private_activity_text=False)
        self.assertNotIn(CAPABILITY,caps)
        caps, _ = _derive_runtime_capabilities((),has_private_activity_text=False,has_attack_observation=True)
        self.assertIn(CAPABILITY,caps)

    def test_competing_description_owner_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"package-owned"):
            validate_bindings((*self.packages,("other",(),self.records,())),
                              self.records,self.source.items)

    def test_composition_refuses_before_creating_output_parent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            definition = SimpleNamespace(runtime_features=(FEATURE,))
            package = SimpleNamespace(mod_id=MOD_ID, definition=definition)
            output = root/"untouched"/"profile"
            selected = (SelectedMod("fixture",package),)
            with self.assertRaisesRegex(ComposeError,"executable"):
                compose_package(root,output,selected,profile_slug="fixture")
            self.assertFalse(output.parent.exists())

    def test_composition_entrypoint_reads_package_sources(self):
        with TemporaryDirectory() as tmp:
            xml = Path(tmp)/"descriptions.xml"
            xml.write_text(XML)
            package = SimpleNamespace(mod_id=MOD_ID,definition=SimpleNamespace(runtime_features=(FEATURE,)))
            inventory = SimpleNamespace(selected=SelectedMod("fixture",package),
                                        descriptions=(xml,),semantic_sources=(self.source,))
            result = resolve_attack_observation_bindings((inventory,),self.records,self.source.items)
            self.assertEqual(result[0].feature,FEATURE)

    def test_declared_equipment_transform_not_mistaken_for_foreign_override(self):
        from majesty_cam.equipment import StockEquipment, registration
        with TemporaryDirectory() as tmp:
            xml=Path(tmp)/'hero.xml'
            source=XML.replace('<Engine version="1"/></Description>',
                '<Engine version="1"/><Game><AllowedWeapon value="Crossbow"/>'
                '<AllowedArmor value="Leather"/></Game></Description>',1)
            xml.write_text(source)
            equipment=StockEquipment('private-weapon','weapon','ZNAM','ZIMG',1004,('HU01',))
            definition=SimpleNamespace(mod_id=MOD_ID,runtime_features=(FEATURE,equipment))
            package=SimpleNamespace(mod_id=MOD_ID,definition=definition)
            inventory=SimpleNamespace(selected=SelectedMod('fixture',package),
                                      descriptions=(xml,),semantic_sources=(self.source,))
            transformed=source.replace('value="Crossbow"','value="'+registration(MOD_ID,equipment).enum_name+'"')
            records=parse_descriptions(transformed).records
            bindings=resolve_attack_observation_bindings((inventory,),records,self.source.items)
            self.assertEqual(bindings[0].descriptions,records)
            for bad in (source,transformed.replace('value="Leather"','value="Plate"'),
                        transformed.replace('<Engine version="1"/>','<Engine version="2"/>',1)):
                with self.assertRaisesRegex(ComposeError,'overridden'):
                    resolve_attack_observation_bindings((inventory,),parse_descriptions(bad).records,self.source.items)


if __name__ == "__main__": unittest.main()
