"""Read-only Standard script inputs; native load order remains authoritative.

Only generated overlapping definitions are emitted. A Standard package is not
converted into a Merge package and its other resources are never copied.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path
import hashlib
import tempfile
import subprocess
import json
import re
import struct

from .gpl import (DefinitionKind, ParsedSemanticSource, SemanticMergeResult,
                  require_complete_semantic_coverage)
from .gpl_features import StockHeroQuestParticipant
from .gpl_function_merge import merge_function, FunctionMergeError, _tokens, _Parser
from .package import GplLoad, ModPackage, load_standard_component, load_standard_definition
from .stock_input_cache import StockInputCache
from .bcd import definition_keys, BcdIndexError

_CACHE = StockInputCache(capacity=64)
_PROOFS = StockInputCache(capacity=32)


@dataclass(frozen=True)
class StandardScripts:
    name: str
    package: ModPackage
    loads: tuple[GplLoad, ...]
    sources: tuple[ParsedSemanticSource, ...]
    participants: tuple[StockHeroQuestParticipant, ...]
    paths: tuple[Path, ...]
    bases: tuple[str, ...] = ()
    digests: tuple[tuple[str, str | None], ...] = ()
    payloads: tuple[tuple[Path, bytes], ...] = ()
    compiled_payloads: tuple[tuple[Path, bytes], ...] = ()

    @cached_property
    def parsed_sources(self):
        sources = self.sources or tuple(self._parse_source(path) for path, _ in self.payloads)
        for source in sources:
            require_complete_semantic_coverage(source)
        return sources

    @cached_property
    def items(self):
        # Majesty replaces definitions in manifest/project load order.
        return {item.key: item for source in self.parsed_sources for item in source.items}

    @cached_property
    def _block_indexes(self):
        return {}

    @cached_property
    def _parsed_by_path(self):
        return {}

    @cached_property
    def _items_by_path(self):
        return {}

    @cached_property
    def _payload_by_path(self):
        return dict(self.payloads)

    def _parse_source(self, path):
        from .compose import _parse_semantic_source_file_cached
        if path not in self._parsed_by_path:
            if path not in self._payload_by_path:
                raise ValueError(f'{self.name}: registered source {path} is absent from the input snapshot')
            source = _parse_semantic_source_file_cached(str(path), self._payload_by_path[path])
            require_complete_semantic_coverage(source)
            self._parsed_by_path[path] = source
            self._items_by_path[path] = {item.key: item for item in source.items}
        return self._parsed_by_path[path]

    def _block_keys(self, index):
        if index not in self._block_indexes:
            target = getattr(self.loads[index], 'target', None)
            data = dict(self.compiled_payloads).get(getattr(target, 'absolute_path', None))
            if data is None:
                raise BcdIndexError('compiled target is absent from the input snapshot')
            try:
                self._block_indexes[index] = definition_keys(data)
            except BcdIndexError as exc:
                raise BcdIndexError(f'{target.relative_path}: {exc}') from exc
        return self._block_indexes[index]

    @cached_property
    def compiled_keys(self):
        """Native availability uses the same compiled ownership as lookup."""
        if not self.loads:
            return frozenset(self.items)
        try:
            return frozenset(key for index in range(len(self.loads)) for key in self._block_keys(index))
        except BcdIndexError as exc:
            raise ValueError(f'{self.name}: cannot determine compiled GPL ownership: {exc}') from exc

    def owner(self, key):
        """Last native load owning this key; source is optional, ownership is not."""
        if not self.loads:  # Semantic-only callers/fixtures.
            return (None, self.items[key]) if key in self.items else None
        for index in reversed(range(len(self.loads))):
            block = self.loads[index]
            if key not in self._block_keys(index):
                continue
            source = None
            for path in block.sources:
                self._parse_source(path.absolute_path)
                source = self._items_by_path[path.absolute_path].get(key, source)
            return index, source
        return None


def read(entry):
    """Snapshot declared files once; defer semantic parsing until composition.

    No project discovery or compiler work belongs in selection/plan refresh.
    Bytecode indexing and source parsing are deferred until composition.
    """
    root = entry.package_root.resolve()
    package = None
    manifest_bytes = None

    def inputs():
        nonlocal package, manifest_bytes
        if package is None:
            manifest_bytes = entry.manifest_path.read_bytes()
            package = load_standard_component(root, manifest_path=entry.manifest_path,
                                              mod_id=entry.content_id,
                                              recover_project_sources=False)
        return (entry.manifest_path.resolve(), root / 'mod-definition.json',
                *(f.file.absolute_path for d in package.datasets[:1] for load in d.loads
                  for directive in load.directives if isinstance(directive, GplLoad)
                  for f in directive.files),
                *(directive.recovered_project.absolute_path
                  for d in package.datasets[:1] for load in d.loads
                  for directive in load.directives if isinstance(directive, GplLoad)
                  and directive.recovered_project))

    def load():
        pairs = tuple((d.base.casefold(), x) for d in package.datasets[:1] for b in d.loads
                      for x in b.directives if isinstance(x, GplLoad))
        loads = tuple(x for _, x in pairs)
        if any(base not in ('any', 'majesty', 'majestyexpansion') for base, _ in pairs):
            raise ValueError(f'{entry.display_name}: unsupported Standard GPL dataset base')
        participants = ()
        definition_path = root / 'mod-definition.json'
        if definition_path.is_file():
            try:
                definition = load_standard_definition(definition_path, entry.content_id)
            except ValueError as exc:
                raise ValueError(f'{entry.display_name}: {exc}') from exc
            participants = definition.runtime_features
        paths = tuple(inputs())
        payloads = {p: p.read_bytes() if p.is_file() else None for p in paths}
        if payloads[entry.manifest_path.resolve()] != manifest_bytes:
            raise ValueError(f'{entry.display_name}: manifest changed while reading its declared inputs; retry')
        digests = tuple((str(p), hashlib.sha256(payloads[p]).hexdigest() if payloads[p] is not None else None)
                        for p in paths)
        return StandardScripts(entry.display_name, package, loads, (),
                               participants, paths, tuple(base for base, _ in pairs), digests,
                               tuple((p.absolute_path, payloads[p.absolute_path])
                                     for block in loads for p in block.sources),
                               tuple((block.target.absolute_path, payloads[block.target.absolute_path])
                                     for block in loads))
    return _CACHE.get(root, (entry.content_id, str(entry.manifest_path)), inputs, load)


def file_inputs(inputs):
    """Exact source/target identity, including absence of an optional declaration."""
    return tuple((item.package.mod_id, item.digests) for item in inputs
                 if item.loads or item.participants)


def fingerprint(entries):
    if not entries:
        return ""
    values = file_inputs(tuple(read(e) for e in entries))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest() if values else ""


def for_dataset(inputs, dataset):
    """Native Mod scope is the first Dataset, not independent sibling blocks."""
    return tuple(item for item in inputs if not item.bases or item.bases[0] in ('any', dataset))


def verify(item, compiler, block_index=None):
    """Prove manifest sources reproduce loaded BCD; cache by bounded inputs."""
    from .compose import no_console_window_options
    def prove():
        sources = dict(item.payloads)
        targets = dict(item.compiled_payloads)
        for block in (item.loads if block_index is None else (item.loads[block_index],)):
            if not block.sources:
                raise ValueError(f'{item.name}: {block.target.relative_path} has no registered GPL sources; '
                                 'cannot safely preserve its scripts in the generated profile')
            files = {f'Source{i}{p.absolute_path.suffix}': p.absolute_path
                     for i, p in enumerate(block.sources)}
            # Preserve original source order, including DAT declarations.
            project = ''.join(f'{"data" if path.suffix.lower() == ".dat" else "source"}="{name}"\n'
                              for name, path in files.items())
            with tempfile.TemporaryDirectory(prefix='majesty-standard-proof-') as temp:
                directory = Path(temp)
                (directory / 'Proof.gplproj').write_text(project, encoding='ascii')
                for name, path in files.items():
                    (directory / name).write_bytes(sources[path])
                def run(output):
                    try:
                        return subprocess.run((str(compiler), '-in', 'Proof.gplproj', '-out', output, '-stdout'),
                            cwd=directory, capture_output=True, timeout=60, **no_console_window_options())
                    except subprocess.TimeoutExpired as exc:
                        raise ValueError(f'{item.name}: source verification timed out for {block.target.relative_path}') from exc
                process = run('Proof.bcd')
                target = directory / 'Proof.bcd'
                if process.returncode or not target.is_file():
                    raise ValueError(f'{item.name}: registered source compilation failed: '
                                     + process.stdout.decode('cp1252', errors='replace')[-1500:])
                exact = target.read_bytes()
                runtime = targets[block.target.absolute_path]
                if exact != runtime:
                    # BCD stores source filenames in diagnostic records. Prove
                    # their exact locations with a filename-only compiler probe;
                    # never erase arbitrary strings or instruction bytes.
                    probe_project = project.replace('Source', 'ProbeX')
                    for name, path in files.items():
                        (directory / name.replace('Source', 'ProbeX')).write_bytes(sources[path])
                    (directory / 'Proof.gplproj').write_text(probe_project, encoding='ascii')
                    process = run('Probe.bcd')
                    probe_path = directory / 'Probe.bcd'
                    probe = probe_path.read_bytes() if not process.returncode and probe_path.is_file() else b''
                    names = {name.encode(): p.relative_path for name, p in
                             zip(files, block.sources)}
                    if not _matches_source_locations(runtime, exact, probe, names):
                        raise ValueError(f'{item.name}: registered GPL source does not reproduce '
                                         f'{block.target.relative_path}; update matching source and bytecode together')
        return True
    stamp = compiler.stat()
    return _PROOFS.get(item.package.root, (item.package.mod_id,
                      block_index, item.digests,
                      tuple(load.target.relative_path for load in item.loads), str(compiler),
                      stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns),
                      lambda: item.paths, prove)


def _matches_source_locations(runtime, exact, probe, names):
    """Ignore only filename fields whose position the compiler itself proves."""
    if len(exact) != len(probe):
        return False
    # The BCD envelope repeats file-size-minus-four, then carries the end of
    # its executable-record section at +16. Filename bytes live in that
    # section. Require the exact same size delta in all three fields; no code
    # words, line numbers, operands or arbitrary offsets are masked.
    if min(len(runtime), len(exact)) < 24:
        return False
    delta = len(runtime) - len(exact)
    normalized = bytearray(runtime)
    for offset in (0, 4, 16):
        actual = struct.unpack_from('<I', runtime, offset)[0]
        expected = struct.unpack_from('<I', exact, offset)[0]
        if actual - expected != delta:
            return False
        if offset in (0, 4) and expected != len(exact) - 4:
            return False
        struct.pack_into('<I', normalized, offset, expected)
    runtime = bytes(normalized)
    fields = []
    patched = bytearray(exact)
    for match in re.finditer(rb'Source[0-9]+\.(?:gpl|dat)\x00', exact, re.I):
        name = match.group()[:-1]
        alternate = name.replace(b'Source', b'ProbeX') + b'\0'
        if name in names and probe[match.start():match.end()] == alternate:
            patched[match.start():match.end()] = alternate
            fields.append((match.start(), match.end(), names[name]))
    if bytes(patched) != probe or not fields:
        return False
    offset = start = 0
    for left, right, relative in fields:
        chunk = exact[start:left]
        if runtime[offset:offset + len(chunk)] != chunk:
            return False
        offset += len(chunk)
        end = runtime.find(b'\0', offset)
        if end < 0:
            return False
        filename = runtime[offset:end].decode('cp1252', errors='replace').replace('\\', '/').lower()
        filename = re.sub('/+', '/', filename)
        expected = relative.replace('\\', '/').lower()
        if filename != expected and not filename.endswith('/' + expected):
            return False
        offset = end + 1
        start = right
    return runtime[offset:] == exact[start:]


def participant_inventories(inputs):
    from .compose import SelectedMod, PackageInventory
    result = []
    for item in inputs:
        if not item.participants:
            continue
        keys = tuple(dict.fromkeys(f.hero_script.casefold() for f in item.participants))
        owned = []
        for key in keys:
            owner = item.owner((DefinitionKind.FUNCTION, key))
            if owner is None or owner[1] is None:
                raise ValueError(f'{item.name}: quest participant {key} has no manifest-registered source')
            winner = _native_winner(inputs, (DefinitionKind.FUNCTION, key))
            if winner is None or winner[0].package.mod_id != item.package.mod_id:
                raise ValueError(f'{item.name}: quest participant {key} is replaced by a later Standard mod; '
                                 'the effective provider must declare its own participation')
            owned.append(owner[1])
        definition = replace(item.package.definition, runtime_features=item.participants)
        package = replace(item.package, definition=definition)
        selected = SelectedMod(alias='standard-' + package.mod_id.strip('{}').lower(),
                               package=package, semantic_passthrough=True)
        result.append(PackageInventory(selected, (), (), (), (),
                      semantic_sources=(ParsedSemanticSource(item.name, '', tuple(owned)),)))
    return tuple(result)


def _native_winner(inputs, key):
    for provider in reversed(inputs):
        try:
            owner = provider.owner(key)
        except BcdIndexError as exc:
            raise ValueError(f'{provider.name}: cannot determine compiled GPL ownership for '
                             f'{key[0].value}:{key[1]}: {exc}') from exc
        if owner is None:
            continue
        index, source = owner
        if source is None:
            target = provider.loads[index].target.relative_path
            raise ValueError(f'{provider.name}: {target} supplies {key[0].value}:{key[1]}, '
                             'which the generated profile also needs to change; matching manifest '
                             'Source files are required to combine this specific definition safely')
        return provider, source, index
    return None


class Providers:
    """Effective native definitions for one composition, not a second merger.

    Reconcile authored inputs before feature transforms. Supply native fallback
    functions to those transforms, and remove untouched native definitions at
    the end. Scoped output is deliberately not manufactured here.
    """

    def __init__(self, inputs, stock_loader, compiler, dataset='any', *, source_ancestor_loader=None):
        if dataset not in ('any', 'majesty', 'majestyexpansion'):
            raise ValueError(f'unsupported output dataset {dataset}')
        self.inputs = tuple(inputs)
        self.stock_loader = stock_loader
        self.source_ancestor_loader = source_ancestor_loader
        self.compiler = compiler
        self.dataset = dataset
        self.native = {}
        self.native_names = {}
        self.native_owners = {}
        self.ancestors = {}
        self.verified = set()

    def _winner(self, key, dataset):
        return _native_winner(for_dataset(self.inputs, dataset), key)

    def stock(self, names):
        missing = tuple(n for n in names if (DefinitionKind.FUNCTION, n.casefold()) not in self.ancestors)
        if missing and self.stock_loader is not None:
            found = self.stock_loader(missing)
            self.ancestors.update(((DefinitionKind.FUNCTION, n.casefold()),
                                   found.get((DefinitionKind.FUNCTION, n.casefold()))) for n in missing)
        return {key: self.ancestors[key] for n in names
                for key in ((DefinitionKind.FUNCTION, n.casefold()),) if self.ancestors.get(key) is not None}

    def lookup(self, key):
        if key in self.native:
            return self.native[key]
        datasets = ('majesty', 'majestyexpansion') if self.dataset == 'any' else (self.dataset,)
        winners = [self._winner(key, dataset) for dataset in datasets]
        if not any(winners):
            self.native[key] = None
            return None
        # Missing native ownership is not equivalent to an expansion stock
        # ancestor: that function may be absent/different in the base dataset.
        texts = [_tokens(w[1].text) if w else None for w in winners]
        if any(text != texts[0] for text in texts[1:]):
            names = ', '.join(dict.fromkeys(w[0].name for w in winners if w))
            raise ValueError(f'{names}: {key[0].value}:{key[1]} has different base-game and expansion '
                             'definitions; a scoped output is required, not an Any replacement')
        for winner in winners:
            if winner is None:
                continue
            provider, _, index = winner
            identity = (provider.package.mod_id, index)
            if identity not in self.verified:
                verify(provider, self.compiler, index)
                self.verified.add(identity)
        native = next(w[1] for w in winners if w)
        self.native[key] = native
        self.native_names[key] = ', '.join(dict.fromkeys(w[0].name for w in winners if w))
        owners = {w[0].package.mod_id.strip('{}').casefold() for w in winners if w}
        self.native_owners[key] = tuple(sorted(owners))
        return native

    def native_label(self, key):
        self.lookup(key)
        return self.native_names.get(key, 'Standard mod')

    def native_candidate(self, key):
        from .script_review import ScriptCandidate
        item = self.lookup(key)
        if item is None:
            return None
        owners = self.native_owners[key]
        if len(owners) != 1:
            raise ValueError('Different Standard owners require separate quest-scope choices')
        return ScriptCandidate(self.native_label(key), item, owners[0])

    def functions(self, names):
        stock = self.stock(names)
        return {key: item for name in names for key in ((DefinitionKind.FUNCTION, name.casefold()),)
                for item in (self.lookup(key) or stock.get(key),) if item is not None}

    def reconcile(self, result, fallbacks=(), *, review=None, skip_keys=(), merge_candidates=None,
                  merge_compatibility_groups=None):
        from .script_review import ScriptConflict
        skip_keys = frozenset(skip_keys)
        items = dict((item.key, item) for item in result.items)
        for fallback in fallbacks:
            if fallback is not None and fallback.key not in items and fallback.key not in skip_keys:
                native = self.lookup(fallback.key)
                if native is None and self.dataset != 'any':
                    native = self.stock((fallback.name,)).get(fallback.key)
                if native is not None:
                    items[fallback.key] = native
        output = []
        for item in items.values():
            if item.key in skip_keys:
                output.append(item)
                continue
            native = self.lookup(item.key)
            if native is None or _tokens(item.text) == _tokens(native.text):
                output.append(item)
                continue
            base = self.stock((item.name,)).get(item.key) if item.kind is DefinitionKind.FUNCTION else None
            if base is not None and _tokens(item.text) == _tokens(base.text):
                output.append(native)
                continue
            # Both sides here are authored source. Their shared SDK ancestry
            # is not necessarily the destination quest's native stock body.
            # Keep the latter for fallbacks above and functions(), not diffing.
            if item.kind is DefinitionKind.FUNCTION and self.source_ancestor_loader is not None:
                base = self.source_ancestor_loader((item.name,)).get(item.key, base)
            if base is not None and _tokens(item.text) == _tokens(base.text):
                output.append(native)
                continue
            error = None
            if base is None:
                error = 'Standard and generated definitions differ without a stock ancestor'
            else:
                try:
                    text = merge_function(base.text, {native.source_name: _align_parameters(base.text, native.text),
                                                      'Manager profile': _align_parameters(base.text, item.text)})
                except FunctionMergeError as exc:
                    error = str(exc)
            if error is not None:
                if review is None:
                    raise ValueError(f'{native.source_name}: cannot safely combine {item.kind.value}:{item.name}: {error}')
                # A combined result is not a mod the player can prefer. Keep
                # the real authored candidates through automatic composition.
                candidates = tuple((merge_candidates or {}).get(item.key, ()))
                if base is not None:
                    candidates = tuple(candidate for candidate in candidates
                                       if _tokens(candidate.item.text) != _tokens(base.text))
                if not candidates:
                    raise ValueError(f'{item.name}: cannot attribute the conflicting generated behavior '
                                     'to an authored mod; a mod preference cannot override Manager requirements')
                conflict = ScriptConflict(self.dataset, item.key, item.name, error, base,
                    (self.native_candidate(item.key), *candidates),
                    compatibility_groups=tuple((merge_compatibility_groups or {}).get(item.key, ())))
                resolved = review.resolve(conflict)
                if resolved is not None:
                    output.append(resolved)
                continue
            output.append(replace(item, text=text, span=None))
        return SemanticMergeResult(tuple(output), result.conflicts)

    def prune(self, result):
        output = []
        for item in result.items:
            known = item.key in self.native
            native = self.lookup(item.key)
            if native is not None:
                if _tokens(item.text) == _tokens(native.text):
                    continue
                if not known:
                    raise ValueError(f'generated {item.kind.value}:{item.name} collides with a Standard definition '
                                     'that was not included in feature composition')
            output.append(item)
        return SemanticMergeResult(tuple(output), result.conflicts)


def _align_parameters(base_text, text):
    """Parameter spelling is not an ABI change; rename bound tokens only."""
    base = _Parser(base_text).function()[0]
    signature, locals_, _ = _Parser(text).function()
    def params(tokens):
        left, right = tokens.index('('), tokens.index(')')
        parts = tokens[left + 1:right]
        values = [tuple(p.split()) for p in ' '.join(parts).split(',')] if parts else []
        if any(len(p) != 2 for p in values):
            return None
        return values, (tokens[:left], tokens[right:])
    a, b = params(base), params(signature)
    if not a or not b or a[1] != b[1] or len(a[0]) != len(b[0]):
        return text
    if any(x[0] != y[0] for x, y in zip(a[0], b[0])):
        return text
    names = {old[1]: new[1] for new, old in zip(a[0], b[0]) if new[1] != old[1]}
    tokens = _tokens(text)
    old_names = {p[1] for p in b[0]}
    if any(new in locals_ or (new in tokens and new not in old_names) for new in names.values()):
        return text  # Do not capture an existing variable/reference.
    return ' '.join(names.get(token, token) for token in tokens) if names else text
