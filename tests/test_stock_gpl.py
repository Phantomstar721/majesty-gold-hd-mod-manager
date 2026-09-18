from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam import stock_gpl
from majesty_cam.gpl import DefinitionKind
from majesty_cam.stock_gpl import (
    LINE_METADATA_PROBE_SHIFTS,
    STOCK_GPL_RUNTIME_PAIRS,
    StockGplError,
    clear_stock_gpl_cache,
    load_stock_function_ancestors,
    snapshot_stock_gpl_inputs,
    verify_stock_gpl,
)


_PROJECT_ROW = re.compile(r'\s*(?:source|data)\s*=\s*"([^"]+)"\s*')


class StockFunctionAncestorTests(unittest.TestCase):
    def test_lazy_lookup_uses_effective_project_order_without_compilation(self):
        with TemporaryDirectory() as tmp:
            game, _, sources = _stock_game(Path(tmp))
            with patch('majesty_cam.stock_gpl.subprocess.run', side_effect=AssertionError('no compiler')):
                result = load_stock_function_ancestors(game, ('Shared',))
            self.assertEqual(len(result), 1)
            self.assertIn('Result = 6', next(iter(result.values())).text)
            self.assertEqual(load_stock_function_ancestors(game, ('Absent',)), {})
            self.assertEqual(load_stock_function_ancestors(Path('missing-game'), ()), {})

    def test_changed_source_and_project_are_not_hidden_by_cache(self):
        with TemporaryDirectory() as tmp:
            game, _, sources = _stock_game(Path(tmp))
            load_stock_function_ancestors(game, ('Shared',))
            sources[-1].write_text(_function(9), encoding='cp1252')
            self.assertIn('Result = 9', next(iter(load_stock_function_ancestors(game, ('Shared',)).values())).text)
            project = game / 'SDK/OriginalQuests' / STOCK_GPL_RUNTIME_PAIRS[-1].project_relative
            project.write_text('source="source_5.gpl"\n', encoding='cp1252')
            self.assertIn('Result = 5', next(iter(load_stock_function_ancestors(game, ('Shared',)).values())).text)

    def test_unsafe_paths_unknown_load_order_and_unparsed_ancestor_are_rejected(self):
        with TemporaryDirectory() as tmp:
            game, _, sources = _stock_game(Path(tmp))
            project = game / 'SDK/OriginalQuests' / STOCK_GPL_RUNTIME_PAIRS[-1].project_relative
            original = project.read_text()
            project.write_text('source="../outside.gpl"\n', encoding='cp1252')
            with self.assertRaisesRegex(StockGplError, 'safe relative path'):
                load_stock_function_ancestors(game, ('Shared',))
            project.write_text(original, encoding='cp1252')
            sources[-1].write_text('unsupported directive\n' + _function(6), encoding='cp1252')
            with self.assertRaisesRegex(ValueError, 'unparsed'):
                load_stock_function_ancestors(game, ('Shared',))
            manifest = game / 'Data/MajestyDatasetDefinitions.xml'
            manifest.write_text(manifest.read_text().replace('Bytecode.bcd', 'Other.bcd'),encoding='utf-8')
            with self.assertRaisesRegex(StockGplError, 'load order'):
                load_stock_function_ancestors(game, ('Shared',))


class _FakeCompiler:
    def __init__(self, exact_outputs):
        self.exact_outputs = {
            key.casefold(): value for key, value in exact_outputs.items()
        }
        self.probe_outputs = {
            line_shift: dict(self.exact_outputs)
            for line_shift in LINE_METADATA_PROBE_SHIFTS
        }
        self.calls = []
        self.on_call = None

    def __call__(self, command, **kwargs):
        command = tuple(command)
        cwd = Path(kwargs["cwd"])
        project_name = command[command.index("-in") + 1]
        output_name = command[command.index("-out") + 1]
        project = cwd / project_name
        declared = next(
            _PROJECT_ROW.fullmatch(line).group(1)
            for line in project.read_text(encoding="cp1252").splitlines()
            if _PROJECT_ROW.fullmatch(line) is not None
        )
        source = cwd / Path(declared.replace("\\", "/"))
        source_payload = source.read_bytes()
        prefix_size = len(source_payload) - len(source_payload.lstrip(b"\r\n"))
        line_shift = prefix_size // 2
        self.calls.append((project_name, line_shift))
        if self.on_call is not None:
            self.on_call(len(self.calls), project_name, line_shift)
        outputs = (
            self.probe_outputs[line_shift]
            if line_shift
            else self.exact_outputs
        )
        (cwd / output_name).write_bytes(outputs[project_name.casefold()])
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class StockGplProofTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_stock_gpl_cache()

    def test_exact_six_pair_runtime_order_and_complete_snapshot(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, sources = _stock_game(Path(tmp))
            extra = game / "SDK" / "OriginalQuests" / "GPLMx" / "extra.gpl"
            extra.write_text(_function(99, name="Extra"), encoding="cp1252")
            decoy = game / "DataMX" / "bytecode.bcd"
            decoy.write_bytes(b"unused-decoy")
            compiler = _FakeCompiler(_outputs_by_project(runtime))

            proof = verify_stock_gpl(
                game,
                runner=compiler,
                use_cache=False,
            )

            self.assertEqual(proof.runtime_pairs, STOCK_GPL_RUNTIME_PAIRS)
            self.assertEqual(
                compiler.calls,
                [
                    (pair.project_relative.name, 0)
                    for pair in STOCK_GPL_RUNTIME_PAIRS
                ]
                * 2,
            )
            shared = proof.semantic_sources[0].require(
                DefinitionKind.FUNCTION,
                "Shared",
            )
            self.assertIn("Result = 6", shared.text)
            inputs = {Path(path) for path, _sha256 in proof.input_hashes}
            self.assertIn(extra.resolve(), inputs)
            self.assertIn(
                (game / "Data" / "MajestyDatasetDefinitions.xml").resolve(),
                inputs,
            )
            self.assertIn((game / "SDK" / "Gplbcc.exe").resolve(), inputs)
            self.assertIn(
                (game / STOCK_GPL_RUNTIME_PAIRS[0].target_relative).resolve(),
                inputs,
            )
            self.assertNotIn(decoy.resolve(), inputs)
            self.assertTrue(all(source.resolve() in inputs for source in sources))

    def test_runtime_accepts_differences_only_at_line_probe_bytes(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            first = STOCK_GPL_RUNTIME_PAIRS[0]
            runtime[first.project_relative.name] = b"AAAAAA"
            (game / first.target_relative).write_bytes(b"AAAAAA")
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            compiler.exact_outputs[first.project_relative.name.casefold()] = b"ABAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[0]][
                first.project_relative.name.casefold()
            ] = b"ACAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[1]][
                first.project_relative.name.casefold()
            ] = b"ADAAAA"

            proof = verify_stock_gpl(
                game,
                runner=compiler,
                use_cache=False,
            )

            self.assertEqual(len(proof.semantic_sources), 1)
            self.assertEqual(
                sum(
                    project == first.project_relative.name and line_shift != 0
                    for project, line_shift in compiler.calls
                ),
                len(LINE_METADATA_PROBE_SHIFTS) * 2,
            )

    def test_nondeterministic_exact_compiler_byte_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            first = STOCK_GPL_RUNTIME_PAIRS[0]
            project_name = first.project_relative.name
            project_key = project_name.casefold()
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            exact_calls = 0

            def vary_one_byte(_call_count, project, line_shift):
                nonlocal exact_calls
                if project != project_name or line_shift != 0:
                    return
                exact_calls += 1
                payload = bytearray(runtime[project_name])
                payload[0] = 0x41 if exact_calls == 1 else 0x42
                compiler.exact_outputs[project_key] = bytes(payload)

            compiler.on_call = vary_one_byte
            with self.assertRaisesRegex(
                StockGplError,
                r"not deterministic.*GPL/path\.gplproj -> Data/bytecode\.bcd",
            ):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

    def test_nondeterministic_line_probe_byte_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            first = STOCK_GPL_RUNTIME_PAIRS[0]
            project_name = first.project_relative.name
            project_key = project_name.casefold()
            runtime[project_name] = b"AAAAAA"
            (game / first.target_relative).write_bytes(b"AAAAAA")
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            compiler.exact_outputs[project_key] = b"ABAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[0]][
                project_key
            ] = b"ACAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[1]][
                project_key
            ] = b"ADAAAA"
            first_probe_calls = 0

            def vary_one_probe_byte(_call_count, project, line_shift):
                nonlocal first_probe_calls
                if (
                    project != project_name
                    or line_shift != LINE_METADATA_PROBE_SHIFTS[0]
                ):
                    return
                first_probe_calls += 1
                compiler.probe_outputs[line_shift][project_key] = (
                    b"ACAAAA" if first_probe_calls == 1 else b"AEAAAA"
                )

            compiler.on_call = vary_one_probe_byte
            with self.assertRaisesRegex(
                StockGplError,
                r"not deterministic.*metadata probe.*GPL/path\.gplproj",
            ):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

    def test_one_probe_difference_cannot_admit_runtime_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            first = STOCK_GPL_RUNTIME_PAIRS[0]
            project_key = first.project_relative.name.casefold()
            runtime[first.project_relative.name] = b"AAAAAA"
            (game / first.target_relative).write_bytes(b"AAAAAA")
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            compiler.exact_outputs[project_key] = b"ABAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[0]][
                project_key
            ] = b"ACAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[1]][
                project_key
            ] = b"ABAAAA"

            with self.assertRaisesRegex(
                StockGplError,
                r"GPL/path\.gplproj -> Data/bytecode\.bcd",
            ):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

    def test_runtime_rejects_mismatch_outside_line_probe_mask_and_names_pair(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            first = STOCK_GPL_RUNTIME_PAIRS[0]
            runtime[first.project_relative.name] = b"AAAAZA"
            (game / first.target_relative).write_bytes(b"AAAAZA")
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            compiler.exact_outputs[first.project_relative.name.casefold()] = b"ABAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[0]][
                first.project_relative.name.casefold()
            ] = b"ACAAAA"
            compiler.probe_outputs[LINE_METADATA_PROBE_SHIFTS[1]][
                first.project_relative.name.casefold()
            ] = b"ADAAAA"

            with self.assertRaisesRegex(
                StockGplError,
                r"GPL/path\.gplproj -> Data/bytecode\.bcd",
            ):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

    def test_manifest_reordering_fails_before_compilation(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            manifest = game / "DataMX" / "MajestyExpansionDatasetDefinitions.xml"
            manifest.write_text(
                _manifest(
                    "MajestyExpansion",
                    "Majesty",
                    (
                        "$(MajestyExpansionBytecodeDataPath)/MX_Data.bcd",
                        "$(MajestyExpansionBytecodeDataPath)/MX_Build.bcd",
                        "$(MajestyExpansionBytecodeDataPath)/MX_Decision.bcd",
                        "$(MajestyExpansionBytecodeDataPath)/MX_Task.bcd",
                    ),
                ),
                encoding="utf-8",
            )
            compiler = _FakeCompiler(_outputs_by_project(runtime))

            with self.assertRaisesRegex(StockGplError, "GPL load order"):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

            self.assertEqual(compiler.calls, [])

    def test_declared_project_escape_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            project = (
                game
                / "SDK"
                / "OriginalQuests"
                / STOCK_GPL_RUNTIME_PAIRS[0].project_relative
            )
            project.write_text('source="..\\outside.gpl"\n', encoding="cp1252")
            compiler = _FakeCompiler(_outputs_by_project(runtime))

            with self.assertRaisesRegex(StockGplError, "safe relative path"):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

            self.assertEqual(compiler.calls, [])

    def test_source_mutation_during_compile_invalidates_proof(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, sources = _stock_game(Path(tmp))
            compiler = _FakeCompiler(_outputs_by_project(runtime))

            def mutate(call_count, _project, _line_shift):
                if call_count == 1:
                    sources[0].write_text(
                        _function(100, name="Changed"),
                        encoding="cp1252",
                    )

            compiler.on_call = mutate
            with self.assertRaisesRegex(StockGplError, "changed during runtime proof"):
                verify_stock_gpl(
                    game,
                    runner=compiler,
                    use_cache=False,
                )

    def test_successful_content_proof_is_cached_in_process(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, _sources = _stock_game(Path(tmp))
            compiler = _FakeCompiler(_outputs_by_project(runtime))
            clear_stock_gpl_cache()

            with patch(
                "majesty_cam.stock_gpl.subprocess.run",
                side_effect=compiler,
            ) as run:
                first = verify_stock_gpl(game)
                second = verify_stock_gpl(game)

            self.assertIs(first, second)
            self.assertEqual(run.call_count, len(STOCK_GPL_RUNTIME_PAIRS) * 2)

    def test_parser_incomplete_source_stays_fingerprinted_but_is_not_an_ancestor(self) -> None:
        with TemporaryDirectory() as tmp:
            game, runtime, sources = _stock_game(Path(tmp))
            sources[-1].write_text("unsupported stock syntax", encoding="cp1252")
            compiler = _FakeCompiler(_outputs_by_project(runtime))

            proof = verify_stock_gpl(
                game,
                runner=compiler,
                use_cache=False,
            )

            shared = proof.semantic_sources[0].require(
                DefinitionKind.FUNCTION,
                "Shared",
            )
            self.assertIn("Result = 5", shared.text)
            inputs = {Path(path) for path, _sha256 in proof.input_hashes}
            self.assertIn(sources[-1].resolve(), inputs)

    def test_snapshot_rejects_reparse_point_in_corpus(self) -> None:
        with TemporaryDirectory() as tmp:
            game, _runtime, sources = _stock_game(Path(tmp))
            source = sources[0]
            real_is_reparse = stock_gpl._is_reparse_point

            def marked_reparse(path):
                return Path(path) == source or real_is_reparse(path)

            with patch(
                "majesty_cam.stock_gpl._is_reparse_point",
                side_effect=marked_reparse,
            ), self.assertRaisesRegex(StockGplError, "symlink or reparse point"):
                snapshot_stock_gpl_inputs(game)


def _stock_game(root: Path):
    game = root / "game"
    corpus = game / "SDK" / "OriginalQuests"
    (game / "Data").mkdir(parents=True)
    (game / "DataMX").mkdir()
    (corpus / "GPL").mkdir(parents=True)
    (corpus / "GPLMx").mkdir()
    (game / "SDK" / "Gplbcc.exe").write_bytes(b"fixture compiler")
    (game / "Data" / "MajestyDatasetDefinitions.xml").write_text(
        _manifest(
            "Majesty",
            None,
            (
                "$(MajestyBytecodeDataPath)/Bytecode.bcd",
                "$(MajestyExpansionBytecodeDataPath)/MX_Compatibility.bcd",
            ),
        ),
        encoding="utf-8",
    )
    (game / "DataMX" / "MajestyExpansionDatasetDefinitions.xml").write_text(
        _manifest(
            "MajestyExpansion",
            "Majesty",
            (
                "$(MajestyExpansionBytecodeDataPath)/MX_Build.bcd",
                "$(MajestyExpansionBytecodeDataPath)/MX_Data.bcd",
                "$(MajestyExpansionBytecodeDataPath)/MX_Decision.bcd",
                "$(MajestyExpansionBytecodeDataPath)/MX_Task.bcd",
            ),
        ),
        encoding="utf-8",
    )

    runtime = {}
    sources = []
    for index, pair in enumerate(STOCK_GPL_RUNTIME_PAIRS, 1):
        project = corpus / pair.project_relative
        project.parent.mkdir(parents=True, exist_ok=True)
        source = project.parent / f"source_{index}.gpl"
        source.write_text(_function(index), encoding="cp1252")
        project.write_text(f'source="{source.name}"\n', encoding="cp1252")
        payload = f"runtime target {index}".encode("ascii")
        target = game / pair.target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        runtime[pair.project_relative.name] = payload
        sources.append(source)
    return game, runtime, tuple(sources)


def _outputs_by_project(runtime):
    return {name: payload for name, payload in runtime.items()}


def _manifest(name, base, gpl_paths):
    base_attribute = f' base="{base}"' if base is not None else ""
    loads = "".join(f"<GPL>{path}</GPL>" for path in gpl_paths)
    return (
        f'<Majesty><DataConfiguration name="{name}"><Dataset{base_attribute}>'
        f"<Load>{loads}</Load></Dataset></DataConfiguration></Majesty>"
    )


def _function(value, *, name="Shared"):
    return (
        f"function {name}()\n"
        "begin\n"
        f"\tResult = {value};\n"
        "end\n"
    )


if __name__ == "__main__":
    unittest.main()
