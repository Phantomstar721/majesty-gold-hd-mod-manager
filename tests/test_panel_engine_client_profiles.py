import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_panel_engine_clients import verify, verify_integer_clients


class PanelEngineClientProfileTests(unittest.TestCase):
    def test_all_three_complete_client_bodies_and_known_callees(self):
        fixtures={name:Path(os.environ['MAJESTY_'+name.upper()+'_EXE']) for name in ('public','beta2','gog')}
        expected=json.loads((ROOT/'profiles/panel-engine/provider-clients.json').read_bytes())
        actual=verify(fixtures)
        actual['relatedClients']=verify_integer_clients(fixtures)
        self.assertEqual(actual,expected)
        self.assertEqual(set(actual['profiles']),{'public','beta2','gog'})
