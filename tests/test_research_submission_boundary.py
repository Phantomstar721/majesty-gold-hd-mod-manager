"""Pinned three-profile scheduler ABI; no game process is launched."""
import hashlib,os,re,struct,unittest
from pathlib import Path
from test_occupant_runtime_profiles import PeImage

class ResearchSubmissionBoundaryTests(unittest.TestCase):
    def test_scheduler_literal_and_processor_vtables(self):
        root=Path(__file__).parents[1]
        source=(root/'tests/ResearchSubmissionChecks.inl').read_text()
        literal=re.search(r'body\[\]=\{(.*?)\};',source,re.S).group(1)
        body=bytes(int(v,16) for v in re.findall(r'0x([0-9A-F]{2})',literal))
        self.assertEqual(hashlib.sha256(body).hexdigest(),'8d442931c2a248075474857629ecc84d776e9f07a4c3fa92c9e610900a85b062')
        fixtures=root.parent/'majesty-gold-hd-mod-manager-gog-support/local/fixtures'
        profiles=[('public',0x740094,0x4dcdf0,0x4dfce0),('beta2',0x758d94,0x4dd400,0x4e02f0),('gog-pristine',0x757f4c,0x4ddb40,0x4e0a30)]
        paths=[(fixtures/name/'MajestyHD.exe',table,scheduler,executor) for name,table,scheduler,executor in profiles]
        if os.environ.get('MAJESTY_BETA2_EXE'):paths.append((Path(os.environ['MAJESTY_BETA2_EXE']),0x758d94,0x4dd400,0x4e02f0))
        for path,table,scheduler,executor in paths:
            if not path.is_file():self.skipTest('local profile fixture missing')
            p=PeImage(path)
            self.assertEqual(p.read(scheduler-p.base,len(body)),body)
            self.assertEqual(struct.unpack('<I',p.read(table+0x78-p.base,4))[0],scheduler)
            self.assertEqual(struct.unpack('<I',p.read(table+0x88-p.base,4))[0],executor)
            col=struct.unpack('<I',p.read(table-4-p.base,4))[0]
            td=struct.unpack('<I',p.read(col+12-p.base,4))[0]
            self.assertEqual(p.read(td+8-p.base,len(b'.?AVGS_OrderProcessor@@\x00')),b'.?AVGS_OrderProcessor@@\x00')
            # Building is dereferenced at the executor entry, before any debit.
            self.assertEqual(p.read(executor-p.base,9),bytes.fromhex('5153568b7424108b06'))

    def test_relocated_executor_fixture_matches_native_body(self):
        root=Path(__file__).parents[1]
        path=os.environ.get('MAJESTY_BETA2_EXE')
        if not path:self.skipTest('modified beta2 fixture not provided')
        source=(root/'tests/QueuedResearchChecks.inl').read_text()
        literal=re.search(r'executorBody\[\]=\{(.*?)\};',source,re.S).group(1)
        body=bytes(int(v,16) for v in re.findall(r'0x([0-9A-F]{2})',literal))
        p=PeImage(path)
        self.assertEqual(p.read(0xE02F0,0x131),body)
        for offset,target in ((0x2F,0x4A8FD0),(0x3B,0x4A6E90),(0xF7,0x46BE70),
                              (0x107,0x426CD0),(0x10E,0x424FF0),(0x117,0x46BE90)):
            self.assertEqual(p.target(0xE02F0+offset)+p.base,target)
        self.assertEqual(struct.unpack_from('<I',body,0x9A)[0],0x7E3FDC)
        self.assertEqual(struct.unpack_from('<I',body,0xE7)[0],0x7DFE4C)
        runtime=(root/'runtime/ResearchSubmissionRuntime.inl').read_text()
        literal=re.search(r'kResearchSchedulerBody\[\] = \{(.*?)\};',runtime,re.S).group(1)
        expected=bytes(int(v,16) for v in re.findall(r'0x([0-9A-F]{2})',literal))
        self.assertEqual(expected,p.read(0xDD400,0x46))
