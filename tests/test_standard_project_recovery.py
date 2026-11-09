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

    def test_discovery_stays_with_component(self):
        from majesty_cam.standard_scripts import verify
        for boundary in (".mqxml", ".mmxml"):
            for project_name in ("Example", "map"):
                with self.subTest(boundary=boundary, project=project_name), TemporaryDirectory() as temp:
                    root = Path(temp)
                    manifest = root / "main.mmxml"
                    mod_id = "11111111-1111-1111-1111-111111111111"
                    manifest.write_text(f'<Mod id="{mod_id}"><DisplayName>Main</DisplayName>'
                                        '<DataConfiguration><Dataset base="Any"><Load><GPL>Example.bcd</GPL>'
                                        '</Load></Dataset></DataConfiguration></Mod>')
                    (root / "Example.bcd").write_bytes(b"fixture")
                    foreign = root / "extra"
                    foreign.mkdir()
                    (foreign / ("nested" + boundary)).write_text("<Majesty/>")
                    (foreign / (project_name + ".gplproj")).write_text('source="nested.gpl"')
                    (foreign / "nested.gpl").write_text("function Wrong()")
                    entry = SimpleNamespace(package_root=root, manifest_path=manifest,
                                            content_id=mod_id, display_name="Main")
                    item = read(entry)
                    self.assertFalse(item.loads[0].sources)
                    (root / "unused.exe").touch()
                    with self.assertRaisesRegex(ValueError, "Example.bcd has no registered GPL sources"):
                        verify(item, root / "unused.exe")

                    local = root / "scripts"
                    local.mkdir()
                    project = local / "legacy.gplproj"
                    project.write_text('source="main.gpl"')
                    (local / "main.gpl").write_text("function Main()")
                    self.assertEqual(read(entry).loads[0].recovered_project.absolute_path, project)
                    project.write_text('source="../extra/nested.gpl"')
                    self.assertFalse(read(entry).loads[0].sources)
                    (foreign / ("nested" + boundary)).unlink()
                    if project_name == "Example":
                        self.assertEqual(read(entry).loads[0].recovered_project.absolute_path,
                                         foreign / "Example.gplproj")
