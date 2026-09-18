"""Conservative, stock-relative N-way merging of GPL function instructions.

This is source composition, not a proof of gameplay equivalence. Expressions
and simple statements are indivisible. Branches are parsed so an edit to a
condition can coexist with edits inside its body without guessing block scope.
No package, symbol, event, or gameplay-specific exception belongs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from difflib import SequenceMatcher
import re
from typing import Mapping


class FunctionMergeError(ValueError):
    pass


_LEX = re.compile(
    r'\s+|//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
    r"'s\b|[$#]?[A-Za-z_][A-Za-z_0-9]*|0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?|"
    r"==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|<<|>>|[^\s]",
    re.IGNORECASE,
)


def _tokens(text: str) -> tuple[str, ...]:
    values = []
    for match in _LEX.finditer(text):
        value = match.group()
        if value.isspace() or value.startswith(("//", "/*")):
            continue
        if value == '"' or value == "/*":
            raise FunctionMergeError("unterminated string or comment")
        values.append(value if value.startswith('"') else value.casefold())
    return tuple(values)


def _code(tokens) -> str:
    return " ".join(tokens).replace(" 's", "'s")


@dataclass(frozen=True)
class _Node:
    kind: str
    head: tuple[str, ...]
    body: tuple['_Node', ...] = ()
    otherwise: tuple['_Node', ...] = ()


class _Parser:
    def __init__(self, text):
        self.values = _tokens(text)
        self.pos = 0

    def peek(self):
        return self.values[self.pos] if self.pos < len(self.values) else ""

    def take(self, expected=None):
        value = self.peek()
        if not value or (expected is not None and value != expected):
            raise FunctionMergeError(f"unsupported GPL structure near {value!r}; expected {expected!r}")
        self.pos += 1
        return value

    def through(self, delimiter):
        start = self.pos
        depth = 0
        while self.peek():
            value = self.take()
            if value == delimiter and depth == 0:
                return self.values[start:self.pos]
            depth += (value == "(") - (value == ")")
            if depth < 0 or value in ("begin", "end"):
                break
        raise FunctionMergeError(f"unsupported GPL structure: missing {delimiter!r}")

    def statement(self, depth=0):
        if depth > 100:
            raise FunctionMergeError("function nesting exceeds source-merge limit")
        if self.peek() == "begin":
            self.take()
            items = []
            while self.peek() != "end":
                items.extend(self.statement(depth + 1))
            self.take("end")
            return tuple(items)
        if self.peek() == "if":
            self.take()
            self.take("(")
            head = ("if", "(", *self.through(")"))
            body = self.statement(depth + 1)
            otherwise = ()
            if self.peek() == "else":
                self.take()
                otherwise = self.statement(depth + 1)
            return (_Node("if", head, body, otherwise),)
        if self.peek() in ("foreach", "while"):
            kind = self.peek()
            head = self.through("do")
            return (_Node(kind, head, self.statement(depth + 1)),)
        if self.peek() in ("", "else", "end", "function", "declare"):
            raise FunctionMergeError(f"unexpected {self.peek()!r} in function body")
        return (_Node("statement", self.through(";")),)

    def function(self):
        self.take("function")
        name = self.take()
        if not re.fullmatch(r"[a-z_][a-z_0-9]*", name):
            raise FunctionMergeError("invalid function name")
        self.take("(")
        signature = ("function", name, "(", *self.through(")"))
        if self.peek() == "is":
            signature += (self.take(), self.take())
        declarations = {}
        if self.peek() == "declare":
            self.take()
            while self.peek() != "begin":
                kind = self.take()
                if kind not in ("agent", "integer", "boolean", "string", "list", "location", "function", "float"):
                    raise FunctionMergeError(f"unsupported declaration type {kind!r}")
                # GPL locals have no initializers. Reject unfamiliar syntax.
                while True:
                    variable = self.take()
                    if not re.fullmatch(r"[a-z_][a-z_0-9]*", variable) or variable in declarations:
                        raise FunctionMergeError(f"ambiguous local declaration {variable!r}")
                    declarations[variable] = kind
                    if self.peek() != ",":
                        break
                    self.take()
                self.take(";")
        if self.peek() != "begin":
            raise FunctionMergeError("missing function body")
        body = self.statement()
        if self.peek():
            raise FunctionMergeError("unconsumed source after function end")
        return signature, declarations, body


def _short(value):
    if isinstance(value, _Node):
        return _code(value.head)[:140]
    if isinstance(value, tuple) and value and isinstance(value[0], _Node):
        return " / ".join(_short(node) for node in value)[:180]
    return _code(value)[:140] if isinstance(value, tuple) else str(value)


def _pick(base, variants, path):
    changed = [(owner, value) for owner, value in variants if value != base]
    if not changed:
        return base
    first = changed[0][1]
    if all(value == first for _, value in changed):
        return first
    details = "; ".join(f"{owner}: {_short(value)}" for owner, value in changed)
    raise FunctionMergeError(f"{path}: competing edits ({details})")


@dataclass(frozen=True)
class _Edit:
    owner: str
    start: int
    end: int
    replacement: tuple[_Node, ...]


def _edits(base, changed, owner):
    counts = Counter(base)
    after = Counter(changed)
    if any(count > 1 and after[node] != count for node, count in counts.items()):
        raise FunctionMergeError(f"{owner}: repeated/ambiguous instruction anchors need an explicit resolution")
    matcher = SequenceMatcher(a=base, b=changed, autojunk=False)
    edits = tuple(_Edit(owner, a, b, changed[c:d])
                  for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal")
    # Moving code and editing it elsewhere must not silently create two copies
    # or discard the edit. Repeated exact statements also make that ambiguous.
    removed = {node for edit in edits for node in base[edit.start:edit.end]}
    added = {node for edit in edits for node in edit.replacement}
    if removed & added:
        raise FunctionMergeError(f"{owner}: moved/reordered instructions need an explicit resolution")
    reverse = SequenceMatcher(a=base[::-1], b=changed[::-1], autojunk=False)
    reverse_edits = tuple(sorted(
        (len(base)-b, len(base)-a, changed[len(changed)-d:len(changed)-c])
        for tag, a, b, c, d in reverse.get_opcodes() if tag != "equal"
    ))
    if tuple((e.start, e.end, e.replacement) for e in edits) != reverse_edits:
        raise FunctionMergeError(f"{owner}: repeated/ambiguous instruction anchors need an explicit resolution")
    refined = []
    for edit in edits:
        if edit.end - edit.start == 1 and len(edit.replacement) > 1:
            original = base[edit.start]
            candidates = [i for i, node in enumerate(edit.replacement)
                          if _identity(node) == _identity(original)]
            if len(candidates) == 1:
                index = candidates[0]
                if index:
                    refined.append(_Edit(owner, edit.start, edit.start, edit.replacement[:index]))
                refined.append(_Edit(owner, edit.start, edit.end, (edit.replacement[index],)))
                if index + 1 < len(edit.replacement):
                    refined.append(_Edit(owner, edit.end, edit.end, edit.replacement[index + 1:]))
                continue
        refined.append(edit)
    return tuple(refined)


def _identity(node):
    if node.kind != "statement":
        return (node.kind, node.head)
    for index, token in enumerate(node.head):
        if token in ("=", "+=", "-=", "*=", "/=", "<<", ">>"):
            return ("assignment", node.head[:index])
    return ("statement", node.head[:1])


def _overlap(a, b):
    if a.start == a.end and b.start == b.end:
        return a.start == b.start
    if a.start == a.end:
        return (b.start < a.start < b.end or
                (a.start in (b.start, b.end) and bool(set(a.replacement) & set(b.replacement))))
    if b.start == b.end:
        return _overlap(b, a)
    return a.start < b.end and b.start < a.end


def _merge_node(base, variants, path):
    changed = [(owner, node) for owner, node in variants if node != base]
    if not changed or all(node == changed[0][1] for _, node in changed):
        return _pick(base, variants, path)
    if base.kind == "statement" or any(node.kind != base.kind for _, node in changed):
        return _pick(base, variants, path)
    head = _pick(base.head, [(o, n.head) for o, n in variants], path + " condition")
    body = _merge_sequence(base.body, [(o, n.body) for o, n in variants], path + " body")
    otherwise = _merge_sequence(base.otherwise, [(o, n.otherwise) for o, n in variants], path + " else")
    return _Node(base.kind, head, body, otherwise)


def _merge_sequence(base, variants, path):
    changed = [(owner, seq) for owner, seq in variants if seq != base]
    if not changed or all(seq == changed[0][1] for _, seq in changed):
        return _pick(base, variants, path)
    edits = sorted((edit for owner, seq in changed for edit in _edits(base, seq, owner)),
                   key=lambda e: (e.start, e.end, e.owner))
    result = []
    cursor = 0
    while edits:
        cluster = [edits.pop(0)]
        while edits and any(_overlap(edit, edits[0]) for edit in cluster):
            cluster.append(edits.pop(0))
        start, end = min(e.start for e in cluster), max(e.end for e in cluster)
        result.extend(base[cursor:start])
        choices = []
        for owner in sorted({e.owner for e in cluster}):
            replacement = []
            position = start
            for edit in (e for e in cluster if e.owner == owner):
                replacement.extend(base[position:edit.start])
                replacement.extend(edit.replacement)
                position = edit.end
            replacement.extend(base[position:end])
            choices.append((owner, tuple(replacement)))
        original = base[start:end]
        location = f"{path} near [{_short(original) if original else 'insertion gap'}]"
        if all(seq == choices[0][1] for _, seq in choices):
            result.extend(choices[0][1])
        elif original and all(len(seq) == len(original) for _, seq in choices):
            for index, node in enumerate(original):
                result.append(_merge_node(node, [(o, seq[index]) for o, seq in choices], location))
        else:
            _pick(original, choices, location)  # raises, never orders differing insertions
        cursor = end
    result.extend(base[cursor:])
    return tuple(result)


def _render(nodes, depth=1):
    lines = []
    indent = "\t" * depth
    for node in nodes:
        lines.append(indent + _code(node.head))
        if node.kind != "statement":
            lines.append(indent + "begin")
            lines.extend(_render(node.body, depth + 1))
            lines.append(indent + "end")
            if node.otherwise:
                lines.extend((indent + "else", indent + "begin"))
                lines.extend(_render(node.otherwise, depth + 1))
                lines.append(indent + "end")
    return lines


def merge_function(base_text: str, variants: Mapping[str, str]) -> str:
    """Combine disjoint instruction edits, or explain why composition is ambiguous.

    Only called for conflicting functions. Nothing in this module is installed
    in the game or run during discovery. Input order does not choose a winner.
    """
    try:
        base = _Parser(base_text).function()
        sides = [(owner, _Parser(text).function()) for owner, text in sorted(variants.items())]
        changed = [(owner, parsed) for owner, parsed in sides if parsed != base]
        if not changed:
            return base_text
        if all(parsed == changed[0][1] for _, parsed in changed):
            return variants[changed[0][0]]
        if any(parsed[0] != base[0] for _, parsed in changed):
            raise FunctionMergeError("function signature changed alongside other edits")
        declarations = {}
        keys = sorted(set(base[1]).union(*(set(p[1]) for _, p in sides)))
        for name in keys:
            value = _pick(base[1].get(name), [(o, p[1].get(name)) for o, p in sides], f"local {name}")
            if value is not None:
                declarations[name] = value
        body = _merge_sequence(base[2], [(o, p[2]) for o, p in sides], "body")
        lines = [_code(base[0]), "declare"]
        lines.extend(f"\t{kind} {name};" for name, kind in declarations.items())
        lines.extend(("begin", *_render(body), "end"))
        result = "\n".join(lines) + "\n"
        # Rendering must round-trip to precisely the composed structure.
        if _Parser(result).function() != (base[0], declarations, body):
            raise FunctionMergeError("composed function did not preserve its branch structure")
        return result
    except RecursionError as exc:
        raise FunctionMergeError("function nesting exceeds source-merge limit") from exc
