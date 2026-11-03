from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from majesty_cam.decision_trace import ENV, PREFIX, instrument, launch_arguments, requested
from majesty_cam.gpl_function_merge import _Parser, _code, _render
from majesty_cam.gpl import merge_sources, parse_gpl
from majesty_cam.compose import compile_gpl

SOURCE = '''function Decision(agent unit) is boolean
declare integer counter;
begin
counter = 0;
if ($Decide(unit) && $Other(unit)) begin
    if (counter == 0) return TRUE;
end else $Alternative(unit);
while (counter < 2) do begin counter = counter + 1; end
return FALSE;
end'''

EMPTY_LOCALS = '''function EmptyLocals(agent unit)
declare
begin
if ($Decide(unit)) return;
$Alternative(unit);
end'''


def strip(nodes):
    return tuple(replace(n, body=strip(n.body), otherwise=strip(n.otherwise))
                 for n in nodes if not (n.head[0] == '$debugout' and
                                        any(PREFIX in t for t in n.head)))


class DecisionTraceTests(unittest.TestCase):
    def test_retired_trace_has_no_production_imports(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        for relative in ('src/majesty_cam/compose.py', 'src/majesty_cam/manager/launch.py'):
            tree = ast.parse((root / relative).read_text(encoding='utf-8'))
            imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertNotIn('decision_trace', imports, relative)
        launcher = (root / 'scripts/Start-DecisionTraceTest.ps1').read_text()
        self.assertNotIn('$env:MAJESTY_DECISION_TRACE', launcher)

    def test_original_instructions_and_control_flow_unchanged(self):
        sig, declarations, body = _Parser(SOURCE).function()
        actual_sig, actual_declarations, traced = _Parser(instrument(SOURCE)).function()
        self.assertEqual((sig, declarations, body), (actual_sig, actual_declarations, strip(traced)))
        self.assertEqual(instrument(SOURCE).count('$decide'), 1)

    def test_empty_declare_is_preserved(self):
        traced = instrument(EMPTY_LOCALS)
        self.assertIn('\ndeclare\nbegin\n', traced)
        sig, declarations, body = _Parser(EMPTY_LOCALS).function()
        actual_sig, actual_declarations, actual = _Parser(traced).function()
        self.assertEqual((sig, declarations, body), (actual_sig, actual_declarations, strip(actual)))

    def test_disabled_by_default_and_no_duplicate_launch_switch(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(requested())
            self.assertEqual(launch_arguments(('abc',)), ('abc',))
        with patch.dict('os.environ', {ENV: 'Solarus_tree'}):
            self.assertEqual(launch_arguments(()), ('-debugout',))
            self.assertEqual(launch_arguments(('-debugout',)), ('-debugout',))

    def test_rejects_invalid_targets_and_duplicate_trace(self):
        with patch.dict('os.environ', {ENV: 'bad name'}):
            with self.assertRaises(ValueError): requested()
        with self.assertRaises(ValueError): instrument(instrument(SOURCE))
        with self.assertRaises(ValueError): instrument('function F(integer n) begin return; end')

    def test_current_solarus_source_preserved(self):
        path = Path(r'C:\Users\bterr\Documents\My Games\MajestyHD\Mods\Majesty Mod Manager - Merged\GPL\Merged.gpl')
        if not path.is_file(): self.skipTest('local source receipt unavailable')
        item = next(i for i in parse_gpl(path.read_text()).items if i.normalized_name == 'solarus_tree')
        sig, declarations, body = _Parser(item.text).function()
        # The user may already have prepared the diagnostic version. Restore
        # only this test fixture's baseline; never rewrite the installed source.
        body = strip(body)
        baseline = '\n'.join((_code(sig), 'declare',
            *(f'{kind} {name};' for name, kind in declarations.items()),
            'begin', *_render(body), 'end'))
        actual_sig, actual_declarations, traced = _Parser(instrument(baseline)).function()
        self.assertEqual((sig, declarations, body), (actual_sig, actual_declarations, strip(traced)))
        compiler = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Gplbcc.exe')
        if compiler.is_file():
            # Compile just this function in a disposable language fixture, not
            # a Manager profile or the user's prepared package.
            source = merge_sources([], {'fixture': [parse_gpl(instrument(baseline))]})
            with TemporaryDirectory(prefix='solarus-trace-fixture-') as tmp:
                compile_gpl(source.emit_project_source_set('Fixture.gpl', 'Fixture.dat'),
                            compiler, Path(tmp) / 'compiler', stem='Fixture')

    def test_stock_compiler_accepts_diagnostic_calls(self):
        compiler = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Majesty HD\SDK\Gplbcc.exe')
        if not compiler.is_file(): self.skipTest('SDK compiler unavailable')
        source = merge_sources([], {'fixture': [parse_gpl(
            instrument(SOURCE) + '\n' + instrument(EMPTY_LOCALS))]})
        with TemporaryDirectory(prefix='decision-trace-fixture-') as tmp:
            compile_gpl(source.emit_project_source_set('Fixture.gpl', 'Fixture.dat'),
                        compiler, Path(tmp) / 'compiler', stem='Fixture')


if __name__ == '__main__': unittest.main()
