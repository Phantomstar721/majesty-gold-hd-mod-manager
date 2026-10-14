from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from majesty_cam.standard_scripts import read

class ProjectRecoveryTests(unittest.TestCase):
    def test_matching_project_under_source_directory_is_snapshotted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'GPL').mkdir()
            manifest = root/'example.mmxml'
            manifest.write_text('<Mod id="11111111-1111-1111-1111-111111111111"><DisplayName>Example</DisplayName><DataConfiguration><Dataset base="Any"><Load><GPL>Example.bcd</GPL></Load></Dataset></DataConfiguration></Mod>')
            (root/'Example.bcd').write_bytes(b'fixture')
            project = root/'GPL/Example.gplproj'
            project.write_text('source="Logic.gpl"\n')
            source = root/'GPL/Logic.gpl'
            source.write_text('function Example()\ndeclare\nbegin\nend\n')
            entry = SimpleNamespace(package_root=root, manifest_path=manifest,
                content_id='11111111-1111-1111-1111-111111111111', display_name='Example')
            result = read(entry)
            self.assertEqual(result.loads[0].sources[0].declared_path, 'Logic.gpl')
            self.assertIn(project, result.paths)
            self.assertIn(source, result.paths)
            self.assertEqual(result.payloads, ((source, source.read_bytes()),))
