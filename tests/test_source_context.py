from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.gpl import parse_gpl, SemanticMergeResult
from majesty_cam.source_context import (SourceContextDispatch, compose, validate_bindings,
    parse_feature, feature_mapping)
from majesty_cam.compose import compile_gpl
from gpl_sampler_harness import Agent, SamplerHarness

FEATURE = SourceContextDispatch("damage", "player_spell_attack", ("agent","integer","integer"), "Attributed")
SOURCE = '''function Root(agent Source, agent Victim)
declare
begin
$StripSource(Victim);
end
function StripSource(agent Victim)
declare
begin
$player_spell_attack(Victim, 15, 2);
end
function player_spell_attack(agent Target, integer Damage, integer Minimum)
declare
begin
end
function Attributed(agent Source, agent Target, integer Damage, integer Minimum)
declare
begin
$player_spell_attack(Target, Damage, Minimum);
end
function Unrelated(agent Victim)
declare
begin
$StripSource(Victim);
end
'''


class SourceContextTests(unittest.TestCase):
    def result(self): return SemanticMergeResult(parse_gpl(SOURCE).items,())

    def test_transport_does_not_modify_original_helper_or_adapter(self):
        before = self.result()
        result = compose(before,(FEATURE,),("Root",),None)
        items = {i.name:i.text for i in result.items}
        for item in before.items:
            if item.name != "Root": self.assertEqual(items[item.name],item.text)
        vm = SamplerHarness("\n".join(i.text for i in result.items))
        seen = []
        vm.calls["attributed"] = lambda *args: seen.append(args)
        vm.calls["player_spell_attack"] = lambda *args: seen.append((None,*args))
        source, target = Agent(), Agent()
        vm.call("Root",source,target)
        self.assertEqual(seen,[(source,target,15,2)])
        vm.call("Unrelated",target)
        self.assertEqual(seen[-1],(None,target,15,2))
        self.assertEqual(len([i for i in result.items if i.name.startswith("MM_SC_")]),1)

    def test_nested_calls_and_no_argument_helper(self):
        text = SOURCE.replace("$StripSource(Victim);", "$StripSource($Identity(Victim));",1)
        text += '''function Identity(agent Value) is agent
declare
begin
return Value;
end
'''
        result = compose(SemanticMergeResult(parse_gpl(text).items,()),(FEATURE,),("Root",),None)
        with TemporaryDirectory(prefix="source-context-") as tmp:
            compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
            if compiler.is_file(): compile_gpl(result.emit_project_source_set(),compiler,Path(tmp)/"compiler")

    def test_strict_ownership_schema_and_no_provider(self):
        self.assertEqual(parse_feature(feature_mapping(FEATURE)),FEATURE)
        validate_bindings((("owner",(FEATURE,),(parse_gpl(SOURCE),)),))
        with self.assertRaises(ValueError):
            validate_bindings((("owner",(FEATURE,),(parse_gpl(SOURCE),)),("other",(),(parse_gpl(SOURCE),))))
        with self.assertRaises(ValueError):
            parse_feature({**feature_mapping(FEATURE),"callback_symbol":"player_spell_attack"})
        before = self.result()
        self.assertIs(compose(before,(),("Root",),None),before)

    def test_direct_and_repeating_hits_keep_separate_adapters_and_saved_source(self):
        from majesty_cam.spell_origin import SOURCE as ORIGIN
        periodic = SourceContextDispatch("periodic", "PeriodicAttack",
                                        ("agent", "integer", "integer"), "PeriodicAttributed")
        text = SOURCE + '''function Tick(agent Spell, agent Target)
declare
begin
$PeriodicHelper(Target);
end
function PeriodicHelper(agent Target)
declare
begin
$PeriodicAttack(Target, 24, 10);
end
function PeriodicAttack(agent Target, integer Damage, integer Minimum)
declare
begin
end
function PeriodicAttributed(agent Source, agent Target, integer Damage, integer Minimum)
declare
begin
$PeriodicAttack(Target, Damage, Minimum);
end
'''
        result = compose(SemanticMergeResult(parse_gpl(text).items,()),
                         (FEATURE,periodic),("Root","Tick"),None)
        vm = SamplerHarness(ORIGIN + "\n" + "\n".join(i.text for i in result.items))
        vm.calls["isvalidgamepiece"] = lambda a: isinstance(a,Agent) and a.alive
        hero, spell, child, target = Agent(), Agent(), Agent(), Agent()
        hero.fields["subtype"] = "hero"
        self.assertEqual(vm.call("MM_SO_Record",spell,hero),1)
        self.assertEqual(vm.call("MM_SO_Record",child,spell),1)
        seen = []
        def hit(kind, source, victim, damage, minimum):
            caster = vm.call("MM_OriginalCaster",source)
            seen.append((kind,caster,victim,damage,minimum))
        vm.calls["attributed"] = lambda *args: hit("direct",*args)
        vm.calls["periodicattributed"] = lambda *args: hit("periodic",*args)
        vm.call("Root",hero,target)
        vm.call("Tick",spell,target)
        vm.call("Tick",child,target)
        self.assertEqual(seen,[("direct",hero,target,15,2),
                               ("periodic",hero,target,24,10),
                               ("periodic",hero,target,24,10)])
        vm.call("Tick",Agent(),target)
        self.assertIsNone(seen[-1][1])
        hero.alive = False
        vm.call("Tick",child,target)
        self.assertIsNone(seen[-1][1])

    def test_no_argument_helper_and_root_called_as_helper(self):
        text = SOURCE.replace("$StripSource(Victim);", "$OtherRoot(Victim);",1)
        text += '''function OtherRoot(agent Victim)
declare
begin
$NoArgs();
end
function NoArgs()
declare
begin
$player_spell_attack($nullagent(), 8, 1);
end
'''
        result = compose(SemanticMergeResult(parse_gpl(text).items,()),(FEATURE,),
                         ("Root","OtherRoot"),None)
        vm = SamplerHarness("\n".join(i.text for i in result.items))
        seen = []
        vm.calls["attributed"] = lambda *args: seen.append(args)
        hero,target = Agent(),Agent()
        vm.call("Root",hero,target)
        self.assertEqual(seen,[(hero,None,8,1)])
        vm.call("OtherRoot",target)
        self.assertEqual(seen[-1],(target,None,8,1))

    def test_native_roots_use_resolved_descriptions_not_losing_candidates(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from majesty_cam.compose import _source_context_roots
        from majesty_cam.descriptions import parse_descriptions
        def document(callback):
            return parse_descriptions(('<Descriptions><Description type="Action" ID="TEST" Name="Test">'
                '<Engine><Script type="0" cProc="0" GPLFunction="'+callback+'"/></Engine>'
                '</Description></Descriptions>').encode())
        stock = document("StockCallback")
        resolved = SimpleNamespace(document=document("ResolvedCallback"))
        inventory = SimpleNamespace(descriptions=(Path("must-not-read-losing-input.xml"),))
        with TemporaryDirectory() as tmp, patch("majesty_cam.compose._load_effective_stock_descriptions",
                return_value={r.key:(r,) for r in stock.records}):
            roots = _source_context_roots(Path(tmp),(inventory,),
                                          descriptions=resolved,merged_items=())
        self.assertEqual(roots,("ResolvedCallback",))


if __name__ == "__main__": unittest.main()
