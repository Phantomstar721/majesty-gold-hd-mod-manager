import os
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_panel_engine_persistence_fixture import verify


class AlphaPersistenceFixture(unittest.TestCase):
    def test_stock_restore_and_alpha_filename_on_all_three_profiles(self):
        verify(Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha'))/'persistence-fixture')
