"""Read-only installed plan -> final capability handoff; never Prepare."""
from dataclasses import replace
from pathlib import Path
import unittest

from majesty_cam.compose import _derive_runtime_capabilities
from majesty_cam.attack_observation import CAPABILITY as OBSERVER
from majesty_cam.checked_placement import CAPABILITY as PLACEMENT
from majesty_cam.inventory_spell_display import CAPABILITY as INVENTORY
from majesty_cam.runtime_capabilities import PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY as TEXT
from majesty_cam.exploration_events import CAPABILITY as EXPLORATION
from majesty_cam.spell_origin import CAPABILITY as ORIGIN
from majesty_cam.manager.build import create_build_plan, _validate_finalized_runtime_registries, ManagerBuildError
from majesty_cam.manager.catalog import Catalog, CatalogEntry, CatalogKind, CatalogSource
from majesty_cam.manager.compatibility import load_compatibility_registry
from majesty_cam.package import load_package


class SourceCapabilityHandoffTests(unittest.TestCase):
    def test_real_selected_declarations_survive_final_handoff(self):
        game=Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        roots=(Path('C:/Users/bterr/Documents/My Games/MajestyHD/Mods/WitchHunterFourSkills'),
               Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3813128205'),
               Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3793509198'))
        if not all(p.is_dir() for p in roots):self.skipTest('installed development sources unavailable')
        entries=[]
        for root in roots:
            package=load_package(root)
            identity=package.mod_id.strip('{}').upper()
            entries.append(CatalogEntry(identity,package.mod_id,identity,CatalogKind.MERGE,
                CatalogSource.LOCAL_MODS,root,package.manifest_path,True,True))
        for chosen in (entries[:1],entries[:2],entries):
            plan=create_build_plan(Catalog(tuple(chosen)),{e.content_id:True for e in chosen},
                                   game_path=game,registry=load_compatibility_registry())
            self.assertFalse(plan.issues,plan.issues)
            self.assertTrue({OBSERVER,PLACEMENT} <= set(plan.runtime_capabilities))
            # Simulate the sole late source-derived feature independently; the
            # real compositor must additionally validate native binding proofs.
            for hidden in ((),('A040',)):
                finalized=replace(plan.runtime_feature_registry,hidden_inventory_actions=hidden)
                caps,_=_derive_runtime_capabilities(plan.runtime_capabilities,
                    runtime_feature_registry=finalized,controller_registry=plan.controller_registry,
                    has_private_activity_text=TEXT in plan.runtime_capabilities,
                    has_source_exploration=EXPLORATION in plan.runtime_capabilities,
                    has_spell_origin=ORIGIN in plan.runtime_capabilities,
                    has_attack_observation=True,has_checked_placement=True)
                _validate_finalized_runtime_registries(plan.runtime_feature_registry,
                    plan.runtime_capabilities,finalized,finalized,caps)
                self.assertEqual(INVENTORY in caps,bool(hidden))
                for missing in (OBSERVER,PLACEMENT):
                    with self.assertRaises(ManagerBuildError):
                        _validate_finalized_runtime_registries(plan.runtime_feature_registry,
                            plan.runtime_capabilities,finalized,finalized,tuple(c for c in caps if c!=missing))


if __name__=='__main__':unittest.main()
