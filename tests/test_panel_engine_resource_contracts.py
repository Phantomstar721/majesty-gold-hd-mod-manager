"""Actual development panel inputs at the production text-composition boundary."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_panel_resource_contracts import inventory,check,verify
from majesty_cam.compose import ComposeError,_split_smnu_records,_smnu_record_index
from majesty_cam.manager.paths import workspace_input


class ActualPanelResourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        override = os.environ.get('MAJESTY_DEVELOPMENT_PACKAGE')
        cls.root = Path(override) if override else workspace_input(
            ROOT.parent, 'custom-guilds/majesty-gold-hd-custom-guild-witch-hunter/src/current/WitchHunterFourSkills')

    def test_actual_resources_use_full_text_materialization_all_versions(self):
        result=verify(self.root)
        self.assertEqual([c['branch'] for c in result['cases']],['public','beta2','gog'])
        self.assertTrue(all(c['panels'] and c['liveAgentLists'] for c in result['cases']))

    def test_collapsed_native_price_control_is_rejected_in_memory(self):
        original=inventory(self.root)
        found=False
        changed=[]
        for resource in original.resources:
            if resource.section==b'SMNU' and resource.key==b'WSHR':
                records=list(_split_smnu_records(resource.entry.data,owner='fixture',label='WSHR'))
                index=_smnu_record_index(records,0x1F46,owner='fixture',label='WSHR')
                value=bytearray(records[index]);struct.pack_into('<4I',value,8,0,0,0,0)
                records[index]=bytes(value)
                resource=replace(resource,entry=replace(resource.entry,data=b''.join(records)))
                found=True
            changed.append(resource)
        self.assertTrue(found,'Required live-list regression fixture is absent')
        bad=replace(original,resources=tuple(changed))
        for var in ('MAJESTY_BCD_GAME','MAJESTY_BCD_GOG_GAME'):
            with self.subTest(stock=var),self.assertRaisesRegex(ComposeError,'0x00001F46.*exact stock MX05'):
                check(Path(os.environ[var]),bad)
