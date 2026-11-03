from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/"src"))
from majesty_cam.checked_placement import *
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.gpl import parse_gpl
from majesty_cam.package import parse_mod_definition, PackageFormatError
from majesty_cam.compose import _derive_runtime_capabilities, ComposeError

FEATURE=CheckedPlacement("placement","Fixture","Solarus","PrivateCast","PrivateRelease","PrivateMove")
STOCK="""<Majesty><Description type="Action" subType="Standard" ID="WRd1" Name="teleport" Description="Teleport">
<Engine version="1"><ImageSet value="Cast"/><CompletionImageSet value="Stand"/><Script type="0" cProc="0" GPLFunction="Teleport_Effect"/></Engine>
<Game version="1"><Flags value="IsSpell"/><EffectorDuration value="1200"/><TimeoutDuration value="36500"/><SpellType value="4"/><CharacterLevel value="4"/><SpellRank value="4"/><ValidationScript value="teleport_check"/></Game>
</Description></Majesty>"""
ACTOR="""<Description type="Unit" subType="Character" ID="AVK1" Name="Solarus"><Engine version="1"><Info value="BlockGround"/><Attachment kind="Movement" type="Walk" ID="Class 2"/></Engine></Description>"""
ACTION=STOCK.replace('ID="WRd1"','ID="PC01"').replace('Name="teleport"','Name="PrivateCast"').replace('GPLFunction="Teleport_Effect"','GPLFunction="PrivateRelease"').replace('value="36500"','value="0"')
XML=ACTION.replace('</Majesty>',ACTOR+'</Majesty>')
GPL=release_source(FEATURE)+"function PrivateMove(agent thisagent, agent target)\nbegin\nend\n"

class CheckedPlacementTests(unittest.TestCase):
    def setUp(self):
        self.stock=parse_descriptions(STOCK).records
        self.records=parse_descriptions(XML).records
        self.source=parse_gpl(GPL)
        self.packages=(("owner",(FEATURE,),self.records,(self.source,)),)
    def validate(self,xml=None,gpl=None):
        return validate_bindings(self.packages,parse_descriptions(xml).records if xml else self.records,
            parse_gpl(gpl).items if gpl else self.source.items,self.stock)
    def test_private_stock_clone_and_effective_callbacks(self):
        self.assertEqual(self.validate()[0].feature,FEATURE)
        for changed in (XML.replace('value="Cast"','value="Attack"'),XML.replace('value="1200"','value="0"'),XML.replace('BlockGround','BlockFlying')):
            with self.assertRaises(ValueError):self.validate(xml=changed)
        with self.assertRaises(ValueError):self.validate(gpl=GPL.replace('theTimePeriod / 2','theTimePeriod'))
    def test_release_source_rejects_invented_scheduler(self):
        source=parse_gpl(GPL.replace('$RunThread','$OtherThread'))
        packages=(("owner",(FEATURE,),self.records,(source,)),)
        with self.assertRaises(ValueError):validate_bindings(packages,self.records,source.items,self.stock)

    def test_private_transition_clone_preserves_lifecycle(self):
        overlay='''<Description type="Unit" subType="Overlay" ID="WRd1" Name="teleport_effector">
<Engine version="1"><Info value="Directionless"/><Info value="DontBlock"/>
<Menu value="11"/><ImageIDBase value="WRd1"/><AttachmentPointID value="3"/>
<DefaultSound value="Teleport"/></Engine><Game version="1"><DialogID value="0"/>
<StackPriority value="0"/><Flags value="TransparentToMouse"/></Game></Description>'''
        stock=(*self.stock,*parse_descriptions('<Majesty>'+overlay+'</Majesty>').records)
        private=overlay.replace('ID="WRd1"','ID="PV01"').replace('Name="teleport_effector"','Name="PrivateTransition"')
        hidden=private.replace('</Engine>','<Info value="NotVisibleInISOView"/></Engine>')
        source=parse_gpl(GPL.replace('"teleport_effector"','"PrivateTransition"'))
        def check(xml, effective_xml=None, code=source, owned=True):
            records=(*self.records,*parse_descriptions('<Majesty>'+xml+'</Majesty>').records)
            effective=records if effective_xml is None else (*self.records,*parse_descriptions('<Majesty>'+effective_xml+'</Majesty>').records)
            return validate_bindings((("owner",(FEATURE,),records if owned else self.records,(code,)),),effective,code.items,stock)
        for clone in (private,hidden):
            self.assertEqual(check(clone)[0].feature,FEATURE)
        for changed in (hidden.replace('value="3"','value="2"'),
                        hidden.replace('value="Teleport"','value="Other"'),
                        hidden.replace('</Engine>','<Script GPLFunction="Other"/></Engine>'),
                        hidden.replace('value="0"','value="1"')):
            with self.assertRaisesRegex(ValueError,'differs from stock'):check(changed)
        with self.assertRaisesRegex(ValueError,'owned and unchanged'):check(hidden,owned=False)
        with self.assertRaisesRegex(ValueError,'owned and unchanged'):check(hidden,effective_xml=private)
        with self.assertRaisesRegex(ValueError,'stock effector/function-value/RunThread'):
            check(hidden,code=parse_gpl(GPL.replace('"teleport_effector"','"PrivateTransition"').replace('theTimePeriod / 2','theTimePeriod')))

    def test_shared_spell_policy_preserves_native_contract(self):
        from majesty_cam.spell_policy import SpellPolicyProvider
        from majesty_cam.spell_discovery import discover, transform_descriptions, compose_discovered
        from majesty_cam.descriptions import merge_descriptions
        from majesty_cam.gpl import SemanticMergeResult
        bindings=(("other",SpellPolicyProvider("suppress","suppress-special-spell","Other_Suppress")),)
        plan=discover(bindings,tuple(r.to_element() for r in self.records),placements=(FEATURE,))
        unrelated=parse_descriptions('<Majesty><Description type="Action" ID="ZZ01" Name="OtherSpell"><Game><Flags value="IsSpell"/></Game></Description></Majesty>').records
        self.assertEqual(plan,discover(bindings,tuple(r.to_element() for r in (*self.records,*unrelated)),placements=(FEATURE,)))
        self.assertEqual(plan.actions[0].native_begin,"Fixture_Begin")
        descriptions=merge_descriptions(b"<Majesty/>",(("owner",XML),))
        self.assertEqual(transform_descriptions(descriptions,plan).payload,descriptions.payload)
        extra='''function TryMove(agent Caster, agent Target) is integer
declare
integer Result;
begin
// $Fixture_Begin(Result, Caster, Target) stays a comment.
$Fixture_Begin(Result, Caster, Target);
return Result;
end
function Other_Suppress(agent Caster, string SpellName) is boolean
declare
begin
return False;
end
function Cast(agent Caster, string SpellName, agent Target, string Sound)
declare
begin
end
'''
        original=SemanticMergeResult(parse_gpl(GPL+extra).items,())
        result=compose_discovered(original,bindings,plan,None)
        self.assertEqual(validate_bindings(self.packages,self.records,result.items,self.stock,
                         spell_policy_plan=plan)[0].feature,FEATURE)
        functions={i.name:i.text for i in result.items}
        self.assertIn('Result = $'+plan.actions[0].wrapper('Begin')+'(Caster',functions['TryMove'])
        self.assertIn('// $Fixture_Begin(Result',functions['TryMove'])
        self.assertEqual(functions['PrivateMove'],original.items[1].text)
        release=functions['PrivateRelease']
        self.assertLess(release.index('MM_SpecialSpellSuppressed'),release.index('$createeffector'))
        begin=functions[plan.actions[0].wrapper('Begin')]
        self.assertLess(begin.index('Result = 0'),begin.index('MM_SpecialSpellSuppressed'))
        self.assertLess(begin.index('MM_SpecialSpellSuppressed'),begin.index('$Fixture_Begin'))
        from gpl_sampler_harness import SamplerHarness, Agent
        harness=SamplerHarness(begin+release)
        calls=[]
        harness.calls['mm_specialspellsuppressed']=lambda caster,spell: True
        harness.calls['fixture_begin']=lambda *args:calls.append('dispatch')
        harness.calls['getspellattribute']=lambda *args:calls.append('effect-duration')
        self.assertEqual(harness.call(plan.actions[0].wrapper('Begin'),Agent(),Agent()),0)
        harness.call('PrivateRelease',Agent(),Agent())
        self.assertEqual(calls,[])
        harness.calls['mm_specialspellsuppressed']=lambda caster,spell: False
        harness.call(plan.actions[0].wrapper('Begin'),Agent(),Agent())
        self.assertEqual(calls,['dispatch'])
        with self.assertRaises(ValueError):
            validate_bindings(self.packages,self.records,result.items,self.stock)
        damaged=parse_gpl('\n'.join(i.text.replace('theTimePeriod / 2','theTimePeriod') for i in result.items)).items
        with self.assertRaises(ValueError):
            validate_bindings(self.packages,self.records,damaged,self.stock,spell_policy_plan=plan)
        # Compile the actual admission wrapper with the native alias unresolved,
        # exactly as production does; this is not a playable profile.
        from tempfile import TemporaryDirectory
        from majesty_cam.compose import compile_gpl
        compiler=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe')
        if compiler.is_file():
            fixture=parse_gpl(begin+functions['MM_SpecialSpellSuppressed']+functions['Other_Suppress'])
            with TemporaryDirectory(prefix='placement-policy-') as tmp:
                compile_gpl(SemanticMergeResult(fixture.items,()).emit_project_source_set(),compiler,Path(tmp)/'compiler')
        no_provider=discover((),tuple(r.to_element() for r in self.records),placements=(FEATURE,))
        self.assertEqual(compose_discovered(original,(),no_provider,None),original)

    def test_placement_spell_conflicting_classification_is_not_ignored(self):
        from majesty_cam.spell_discovery import discover
        from majesty_cam.spell_policy import SpellPolicyDiscovery, SpellPolicyProvider
        policy=SpellPolicyDiscovery('policy',('PrivateCast',),(),(),(),(),(),())
        with self.assertRaises(ValueError):
            discover((("provider",policy),("provider",SpellPolicyProvider('s','suppress-special-spell','Suppress'))),
                     tuple(r.to_element() for r in self.records),placements=(FEATURE,))

    def test_installed_development_source_policy_integration(self):
        import os
        from majesty_cam.package import load_package
        from majesty_cam.compose import (SelectedMod, inventory_package, _spell_policy_bindings,
            _parse_inventory_gpl_sources, _load_effective_stock_descriptions,
            resolve_checked_placement_bindings)
        from majesty_cam.spell_discovery import discover, compose_discovered
        from majesty_cam.gpl import SemanticMergeResult
        game=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        roots=(Path(os.environ.get('MAJESTY_PLACEMENT_CANDIDATE', 'C:/Users/bterr/Documents/My Games/MajestyHD/Mods/WitchHunterFourSkills')),
               Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3813128205'))
        if not all(p.is_dir() for p in roots):
            self.skipTest('local development source not installed')
        inventories=tuple(inventory_package(SelectedMod(str(n),load_package(p))) for n,p in enumerate(roots))
        from majesty_cam.hero_info import HeroInfoRow, validate_hero_info_evidence
        for row in inventories[0].selected.package.definition.runtime_features:
            if isinstance(row, HeroInfoRow):
                validate_hero_info_evidence(inventories[0], row)
        features=tuple(f for i in inventories for f in i.selected.package.definition.runtime_features
                       if isinstance(f,CheckedPlacement))
        if not features:self.skipTest('installed source has no checked placement')
        records={}
        for path in inventories[0].descriptions:
            records.update(parse_descriptions(path.read_bytes()).index)
        names={f.action.casefold() for f in features}|{f.arrival_action.casefold() for f in features if f.arrival_action}
        bindings=_spell_policy_bindings(inventories)
        plan=discover(bindings,tuple(r.to_element() for r in records.values()
                      if r.to_element().get('Name','').casefold() in names),placements=features)
        sources=_parse_inventory_gpl_sources(inventories[0])
        items={i.key:i for s in sources for i in s.items}
        cast=parse_gpl((game/'SDK/OriginalQuests/GPL/TaskModules/Subtasks/Cast.gpl').read_text())
        def loader(names):return {i.key:i for i in cast.items if i.normalized_name in {n.casefold() for n in names}}
        result=compose_discovered(SemanticMergeResult(tuple(items.values()),()),bindings,plan,loader)
        # Production uses the complete stock reference catalog to certify the
        # clone, while checking effective output separately for each scope.
        reference={k:v[0] for k,v in _load_effective_stock_descriptions(game).items()}
        for scope in ('Majesty','MajestyExpansion'):
            stock={k:v[0] for k,v in _load_effective_stock_descriptions(game,scope).items()}
            effective=dict(stock)
            effective.update(records)
            resolve_checked_placement_bindings(inventories,effective.values(),result.items,reference.values(),spell_policy_plan=plan)
    def test_actual_observer_proof_digest_and_wire_bounds(self):
        data=encode(FEATURE,b"actual composed output proof")
        feature,digest=decode(data)
        self.assertEqual(feature,FEATURE)
        self.assertEqual(digest,hashlib.sha256(b"actual composed output proof").digest())
        self.assertNotEqual(data,encode(FEATURE,b"different composed output"))
        for invalid in (data+b"x",data[:-1],b"MMCP"+data[4:],data[:8]+bytes(4)+data[12:]):
            with self.assertRaises(ValueError):decode(invalid)
    def test_schema_and_unknown_fields(self):
        mapping=feature_mapping(FEATURE)
        value=dict(schema_version=3,mod_id="{00000000-0000-0000-0000-000000000001}",internal_name="Fixture",display_name="Fixture",custom_buildings=[],runtime_features=[mapping])
        self.assertEqual(parse_mod_definition(value).runtime_features[0],FEATURE)
        for distance in (600, 601, 2097120):
            extended = replace(FEATURE, maximum_range=distance)
            self.assertEqual(decode(encode(extended, b"proof"))[0], extended)
        for key,item in (("offset",1),("maximum_range",2097121),("maximum_range",0),("maximum_range",True),("api_prefix","MM_X"),("movement_callback_symbol","Fixture_Commit")):
            with self.assertRaises(ValueError):parse_feature(dict(mapping,**{key:item}))
    def test_presented_version_wire_and_private_clone(self):
        feature=replace(FEATURE,type=PRESENTED_FEATURE_TYPE,arrival_action="PrivateArrival")
        declaration=dict(schema_version=3,mod_id="{00000000-0000-0000-0000-000000000001}",internal_name="Fixture",display_name="Fixture",custom_buildings=[],runtime_features=[feature_mapping(feature)])
        self.assertEqual(parse_mod_definition(declaration).runtime_features[0],feature)
        standup='''<Description type="Action" subType="Standard" ID="A052" Name="standup"><Engine version="1"><ImageSet value="Special-3"/><CompletionImageSet value="Stand"/></Engine></Description>'''
        arrival=standup.replace('ID="A052"','ID="PA01"').replace('Name="standup"','Name="PrivateArrival"')
        xml=XML.replace('value="Cast"','value="Special-2"').replace('</Majesty>',arrival+'</Majesty>')
        records=parse_descriptions(xml).records
        stock=parse_descriptions(STOCK.replace('</Majesty>',standup+'</Majesty>')).records
        packages=(("owner",(feature,),records,(self.source,)),)
        self.assertEqual(validate_bindings(packages,records,self.source.items,stock)[0].feature,feature)
        self.assertEqual(decode(encode(feature,b'proof',image_id=0x4F534457))[0],feature)
        with self.assertRaises(ValueError):encode(feature,b'proof')
        for changed in (xml.replace('value="Special-3"','value="Attack"'),xml.replace('ID="PA01"','ID="A052"')):
            # Effective output may not substitute any part of the owned action.
            with self.assertRaises(ValueError):validate_bindings(packages,parse_descriptions(changed).records,self.source.items,stock)
        for value in (dict(feature_mapping(FEATURE),arrival_action="PrivateArrival"),
                      dict(feature_mapping(feature),arrival_action=FEATURE.action)):
            with self.assertRaises(ValueError):parse_feature(value)
    def test_capability_is_derived_and_requires_shared_observer(self):
        caps,_=_derive_runtime_capabilities((CAPABILITY,),has_private_activity_text=False)
        self.assertNotIn(CAPABILITY,caps)
        with self.assertRaises(ComposeError):_derive_runtime_capabilities((),has_private_activity_text=False,has_checked_placement=True)
        caps,_=_derive_runtime_capabilities((),has_private_activity_text=False,has_checked_placement=True,has_attack_observation=True)
        self.assertIn(CAPABILITY,caps)

    def test_learned_version_isolates_category_without_loosening_clone(self):
        from majesty_cam.checked_placement import image_identity
        feature=replace(FEATURE,type=LEARNED_FEATURE_TYPE,arrival_action="PrivateArrival",required_level=6)
        standup='<Description type="Action" subType="Standard" ID="A052" Name="standup"><Engine version="1"><ImageSet value="Special-3"/><CompletionImageSet value="Stand"/></Engine></Description>'
        arrival=standup.replace('ID="A052"','ID="PA01"').replace('Name="standup"','Name="PrivateArrival"')
        xml=XML.replace('value="Cast"','value="Special-2"').replace('<SpellType value="4"','<SpellType value="None"').replace('<CharacterLevel value="4"','<CharacterLevel value="6"').replace('</Majesty>',arrival+'</Majesty>')
        records=parse_descriptions(xml).records
        stock=parse_descriptions(STOCK.replace('</Majesty>',standup+'</Majesty>')).records
        packages=(("owner",(feature,),records,(self.source,)),)
        self.assertEqual(validate_bindings(packages,records,self.source.items,stock)[0].feature,feature)
        self.assertEqual(decode(encode(feature,b'proof',image_id=123))[0],feature)
        for level in (1,6,1000):
            wire=encode(replace(feature,required_level=level),b'proof',image_id=0x4F534457)
            self.assertEqual(image_identity(wire),0x4F534457)
            self.assertNotEqual(image_identity(wire),level)
            with self.assertRaises(ValueError):image_identity(wire[:-1])
        self.assertEqual(image_identity(encode(FEATURE,b'proof')),0)
        self.assertEqual(image_identity(encode(replace(feature,type=PRESENTED_FEATURE_TYPE,required_level=0),b'proof',image_id=123)),123)
        declaration=dict(schema_version=3,mod_id="{00000000-0000-0000-0000-000000000001}",internal_name="Fixture",display_name="Fixture",custom_buildings=[],runtime_features=[feature_mapping(feature)])
        self.assertEqual(parse_mod_definition(declaration).runtime_features[0],feature)
        for before,after in (('SpellType value="None"','SpellType value="4"'),('CharacterLevel value="6"','CharacterLevel value="4"'),('SpellRank value="4"','SpellRank value="6"'),('TimeoutDuration value="0"','TimeoutDuration value="30000"'),('teleport_check','private_check')):
            changed=parse_descriptions(xml.replace(before,after)).records
            with self.assertRaises(ValueError):
                validate_bindings((("owner",(feature,),changed,(self.source,)),),changed,self.source.items,stock)
        for level in (0,1001,True,"6"):
            with self.assertRaises(ValueError):parse_feature(dict(feature_mapping(feature),required_level=level))
        legacy=replace(feature,type=PRESENTED_FEATURE_TYPE,required_level=0)
        with self.assertRaises(ValueError):validate_bindings((("owner",(legacy,),records,(self.source,)),),records,self.source.items,stock)
