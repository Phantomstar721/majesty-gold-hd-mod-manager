from pathlib import Path
import sys
import unittest
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_panel_engine_owner_fixture import verify


class PanelEngineOwnerFixtureTests(unittest.TestCase):
    def test_existing_action_owner_under_engine_presentation(self):
        sdk = ROOT.parent / '.audits/flamey-window-engine-sdk-20261109/sdk/Window Engine/src/we_engine.cpp'
        result = verify(sdk, Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha'))/'handoff-owner-fixture', handoff=True)
        self.assertTrue(result['handlerHandoff'])

    def test_source_owner_and_navigation_contract(self):
        sdk = ROOT.parent / '.audits/flamey-window-engine-sdk-20261109/sdk/Window Engine/src/we_engine.cpp'
        result = verify(sdk, Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha'))/'owner-fixture')
        self.assertTrue(result['boundedVtableCopy'])
        self.assertFalse(result['nativeGameCallsExecuted'])
        self.assertIn('one destructor with original flags and return', result['coverage'])
