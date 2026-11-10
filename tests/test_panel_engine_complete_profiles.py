import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_panel_engine_sdk_clients import verify as sdk_clients
from verify_panel_engine_ui_providers import verify as ui_providers
from verify_panel_engine_controller_tables import verify as controller_tables
from generate_panel_engine_bindings import generate


class CompleteEngineProfiles(unittest.TestCase):
    def test_explicit_three_build_bindings_agree_with_all_primary_reports(self):
        self.assertEqual(generate(),json.loads((ROOT/'profiles/panel-engine/engine-bindings.json').read_bytes()))
        fixtures={b:Path(os.environ['MAJESTY_'+b.upper()+'_EXE']) for b in ('public','beta2','gog')}
        for name,verify in (('sdk-clients',sdk_clients),('ui-providers',ui_providers),('controller-tables',controller_tables)):
            with self.subTest(report=name):
                self.assertEqual(verify(fixtures),json.loads((ROOT/'profiles/panel-engine'/(name+'.json')).read_bytes()))


if __name__=='__main__':unittest.main()
