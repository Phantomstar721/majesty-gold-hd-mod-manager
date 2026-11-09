import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import zipfile
from majesty_cam.manager.support_report import export_report, record_launch, LIMIT

class SupportReportTests(unittest.TestCase):
    def test_bounded_allowlist_and_missing_files(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); runtime=root/'runtime';runtime.mkdir()
            merged=root/'merged';merged.mkdir()
            game=root/'game.exe';game.write_bytes(b'executable')
            dll=runtime/'MajestyBuildingRuntime.dll';dll.write_bytes(b'runtime')
            paths=SimpleNamespace(runtime_root=runtime,game_executable=game,runtime_dll=dll,merged_output_root=merged)
            (runtime/'MajestyBuildingRuntime.log').write_bytes(b'x'*(LIMIT+1))
            (runtime/'MajestyBuildingRuntime.log.fault').write_text('first cause')
            (runtime/'secret.save').write_text('not for export')
            (merged/'CAM-MERGE-REPORT.json').write_text('{}')
            for i in range(5):record_launch(paths,[str(i)],{str(i):'Fixture'})
            self.assertEqual(len(list(runtime.glob('manager-launch.json*'))),3)
            report=export_report(paths,root/'report.zip')
            with zipfile.ZipFile(report) as z:
                self.assertNotIn('runtime/MajestyBuildingRuntime.log',z.namelist())
                self.assertEqual(z.read('runtime/MajestyBuildingRuntime.log.fault'),b'first cause')
                self.assertFalse(any(n.endswith(('.dll','.exe','.save')) for n in z.namelist()))
                metadata=json.loads(z.read('REPORT.json'))
                self.assertTrue(any(f['status']=='omitted: size limit' for f in metadata['files']))
                self.assertEqual(json.loads(z.read('launch/manager-launch.json'))['active_mods'][0]['id'],'4')
            self.assertEqual((merged/'CAM-MERGE-REPORT.json').read_text(),'{}')
            with self.assertRaises(ValueError):export_report(paths,runtime/'MajestyBuildingRuntime.log')
