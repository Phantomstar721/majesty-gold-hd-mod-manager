from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from majesty_cam.gpl import parse_gpl
from majesty_cam.compose import ScopedSemanticResolution, merge_gpl_resources, ComposeError
from majesty_cam.manager.compatibility import load_compatibility_registry

class ReviewedComponentTests(TestCase):
    def test_actual_direct_bodies_debit_once_after_both_defenses(self):
        import re
        from gpl_sampler_harness import SamplerHarness, Agent
        names={'whp_directspelldamage','bards_direct_spell_damage','bards_playerspellattackattributeddamage'}
        for rule in load_compatibility_registry().combination_resolutions:
            if not rule.source_sha256 or 'bards' not in rule.source_path.name:continue
            source='\n'.join(f.text for f in parse_gpl(rule.source_path.read_text()).items if f.normalized_name in names)
            # Explicit native fixtures: zero intelligence/enchanted armor;
            # real component ordering with deterministic rolls and defenses.
            source=re.sub(r'#(?:intelligence_div|armor_magic_mult)\b','1',source,flags=re.I)
            source=re.sub(r'#(\w+)',lambda m:'"'+m[1].lower()+'"',source)
            source=re.sub(r"'s\s+\"([^\"]+)\"",lambda m:"'s \""+m[1].lower()+'"',source)
            source=re.sub(r'\b(\w+)\s*-=\s*([^;]+);',lambda m:f'{m[1]} = {m[1]} - ({m[2]});',source)
            vm=SamplerHarness(source);events=[]
            attacker=Agent();attacker.fields={'type':'hero','subtype':'hero','attrib_intelligence':0}
            defender=Agent();defender.fields={'type':'hero','subtype':'hero','attrib_armor_magic_bonus':0,'attrib_hp':100}
            vm.calls.update({'randomnumber':lambda n:n-1,'getattribute':lambda a,k:a[k],
                'bards_refrain_bonus':lambda a:3 if a is attacker else 0,
                'bards_direct_damage':lambda a,d,n:n-3,'whp_directdamage':lambda a,d,n:n//2,
                'bards_renown_hit':lambda a,d,n:events.append(('renown',n)),
                'adjustattribute':lambda a,k,n:events.append(('hp',n)),
                'whp_afterdirectdamage':lambda a,d,n:events.append(('after',n))})
            for name,args in [('whp_directspelldamage',(attacker,defender,20,1)),
                              ('bards_direct_spell_damage',(attacker,defender,20,1)),
                              ('bards_playerspellattackattributeddamage',(attacker,None,defender,20,1))]:
                events.clear();vm.call(name,*args)
                self.assertEqual(events,[('renown',10),('hp',-10),('after',100)])

    def test_current_bard_damage_keeps_flourish_and_attributed_refrain(self):
        from majesty_cam.gameplay_events import stock_tokens
        for rule in load_compatibility_registry().combination_resolutions:
            if not rule.source_sha256 or 'bards' not in rule.source_path.name:
                continue
            functions={f.normalized_name: ''.join(stock_tokens(f.text)).casefold()
                       for f in parse_gpl(rule.source_path.read_text()).items}
            damage=functions['damage']
            self.assertEqual(damage.count('$bards_consume_flourish'),1)
            self.assertEqual(damage.count('$bards_refrain_bonus'),1)
            self.assertIn('if(bardsflourish)dmg+=3',damage)
            self.assertIn('bardsflourish&&critical_effect==false',damage)
            self.assertLess(damage.index('dmg_stopped=dmg_stopped/2'),damage.index('t=dmg_stopped/4'))
            self.assertLess(damage.index('$whp_damagewithfloor'),damage.index('$bards_renown_hit'))
            self.assertLess(damage.index('$bards_finale_record'),damage.index('whp_before='))
            self.assertEqual('$alchemy_paralytic_oil_begin' in damage,'alchemist' in rule.source_path.name)
            for name, source in (('whp_directspelldamage','attacker'),('bards_playerspellattackattributeddamage','source')):
                body=functions[name]
                self.assertEqual(body.count('$bards_refrain_bonus'),1)
                self.assertIn('$bards_refrain_bonus('+source+')',body)
                self.assertLess(body.index('$bards_refrain_bonus'),body.index('#attrib_armor_magic_bonus'))
                self.assertLess(body.index('$whp_directdamage'),body.index('$bards_renown_hit'))
                self.assertEqual(body.count('$adjustattribute'),1)
                self.assertLess(body.index('$adjustattribute'),body.index('$whp_afterdirectdamage'))

    def source(self,value):
        return parse_gpl(f"function PrivateHelper() is integer\nbegin\nreturn {value};\nend\n")

    def merge(self, sources, resolution):
        inventories=tuple(SimpleNamespace(selected=SimpleNamespace(alias=owner)) for owner in sources)
        with patch("majesty_cam.compose._parse_inventory_gpl_sources",side_effect=lambda inv:[sources[inv.selected.alias]]):
            return merge_gpl_resources(inventories,semantic_resolutions={resolution.item.key:resolution})

    def test_component_replaces_single_provider_and_keeps_unrelated_items(self):
        resolution=ScopedSemanticResolution(self.source(3).items[0],frozenset(("first","second")),True)
        second=parse_gpl("function Other()\nbegin\nend\n")
        result=self.merge({"first":self.source(1),"second":second},resolution)
        self.assertIn("return 3",result.source_set.gpl_text)
        self.assertIn("function Other",result.source_set.gpl_text)
        self.assertNotIn("return 1",result.source_set.gpl_text)

    def test_component_cannot_discard_a_foreign_provider(self):
        resolution=ScopedSemanticResolution(self.source(3).items[0],frozenset(("first","second")),True)
        with self.assertRaisesRegex(ComposeError,"additional mod owners"):
            self.merge({"first":self.source(1),"third":self.source(7)},resolution)

    def test_identical_component_is_not_an_unused_resolution_error(self):
        resolution=ScopedSemanticResolution(self.source(1).items[0],frozenset(("first",)),True)
        result=self.merge({"first":self.source(1)},resolution)
        self.assertEqual(result.source_set.gpl_text.count("function PrivateHelper"),1)

    def test_registered_pairs_and_triple_are_exclusive_and_hash_pinned(self):
        registry=load_compatibility_registry()
        reviewed=[r for r in registry.combination_resolutions if r.source_sha256]
        self.assertEqual(len(reviewed),3)
        import hashlib
        for rule in reviewed:
            self.assertEqual(hashlib.sha256(rule.source_path.read_bytes()).hexdigest(),rule.source_sha256)
            self.assertEqual(set(rule.input_function_hashes),set(rule.required_mod_ids))
            selected=set(rule.required_mod_ids)
            active=[r for r in reviewed if set(r.required_mod_ids)<=selected and not set(r.excluded_mod_ids)&selected]
            self.assertEqual(active,[rule])
