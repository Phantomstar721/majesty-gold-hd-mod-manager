"""Prove notification anchors and captured inputs, not author-owned gameplay.

Paths include every branch/loop and body/else edge. A call in a different
branch is not the same boundary, but unrelated siblings need not match stock.
All changes use source spans so selected instructions survive literally.
"""

from collections import Counter

from .gpl_function_merge import _SourceParser, _tokens, _unparen


def _and_terms(tokens):
    """Split positive conjunctions only; keep OR/unsupported outer syntax whole."""
    tokens = _unparen(tokens)
    depth, cuts = 0, []
    for index, token in enumerate(tokens):
        if depth == 0:
            if token in ('||', '?', ':', '=', '+=', '-=', '*=', '/='):
                return (tokens,)
            if token == '&&':
                cuts.append(index)
        depth += (token == '(') - (token == ')')
    if not cuts:
        return (tokens,)
    terms, start = [], 0
    for end in (*cuts, len(tokens)):
        terms.extend(_and_terms(tokens[start:end]))
        start = end + 1
    return tuple(terms)


def _scope_shape(path):
    return tuple((node.kind, node.head, edge) for node, edge in path)


def _encloses(parent, child):
    return len(parent) <= len(child) and all(
        a is b and edge == other_edge for (a, edge), (b, other_edge) in zip(parent, child))


def _always_returns(nodes):
    """Prove an explicit straight-line return from a branch."""
    return bool(nodes) and nodes[-1].head == ('return', ';') and all(
        node.kind == 'statement' and node.head[0] not in ('break', 'continue', 'goto')
        for node in nodes[:-1])


def _same_success_path(actual, reference, *, nested=False):
    """Retain every stock guard and edge, with opt-in deeper positive branches.

    Tightening an if's body restricts when the selected transaction executes.
    Tightening its else would broaden that branch, so else and loops stay exact.
    Callers that permit nesting must validate the transaction within that scope.
    """
    if len(actual) < len(reference):
        return False
    extra = actual[len(reference):]
    if extra and (not nested or any(node.kind != 'if' or edge != 'body' for node, edge in extra)):
        return False
    for (kind, head, edge), (stock_kind, stock_head, stock_edge) in zip(
            _scope_shape(actual), _scope_shape(reference)):
        if kind != stock_kind or edge != stock_edge:
            return False
        if head == stock_head:
            continue
        if kind != 'if' or edge != 'body':
            return False
        if head[:2] != ('if', '(') or stock_head[:2] != ('if', '('):
            return False
        if Counter(_and_terms(stock_head[2:-1])) - Counter(_and_terms(head[2:-1])):
            return False
    return True


def entries(nodes, path=()):
    for index, node in enumerate(nodes):
        yield node, path, nodes, index
        yield from entries(node.body, (*path, (node, "body")))
        yield from entries(node.otherwise, (*path, (node, "else")))


class EventBoundary:
    def __init__(self, current, stock):
        self.current, self.stock = current, stock
        self.parser, self.reference = _SourceParser(current.text), _SourceParser(stock.text)
        signature, self.locals, self.body = self.parser.function()
        expected, self.stock_locals, self.stock_body = self.reference.function()
        if signature != expected:
            self.fail("callback signature changed")
        self.actual_entries = tuple(entries(self.body))
        self.stock_entries = tuple(entries(self.stock_body))
        self.paths = {id(node): path for node, path, _, _ in self.actual_entries}
        self.edits = []

    def fail(self, detail):
        raise ValueError(f"{self.current.name} ({self.current.source_name}): Manager cannot place its "
                         f"notification at the required success/cleanup boundary: {detail}")

    def locate(self, instruction, *, callee_change=False, before=None, scope=None,
               nested=False, optional=False):
        head = _tokens(instruction)
        references = [e for e in self.stock_entries if e[0].head == head]
        if len(references) != 1:
            self.fail("stock reference boundary is missing or ambiguous: " + instruction)
        reference = references[0]
        def same_head(actual):
            return (actual == head or callee_change and actual[:1]
                    and actual[0].startswith('$') and actual[1:] == head[1:])
        matches = [e for e in self.actual_entries if same_head(e[0].head)
                   and _same_success_path(e[1], reference[1], nested=nested)]
        if before is not None:
            matches = [e for e in matches if _encloses(e[1], self.paths[id(before)])]
        if scope is not None:
            context = self.paths[id(scope)]
            matches = [e for e in matches if len(e[1]) == len(context) and _encloses(e[1], context)]
        if optional and not matches:
            return reference, None
        if len(matches) != 1:
            self.fail("missing, moved or ambiguous boundary: " + instruction)
        return reference, matches[0]

    def types(self, tokens):
        used = set(tokens)
        if any(self.locals.get(name) != kind for name, kind in self.stock_locals.items()
               if name in used):
            self.fail("event variable type changed")

    def anchor(self, instruction, *, callee_change=False, scope=None, nested=False, optional=False):
        """Require one insertion point in its original conditional scope."""
        reference, actual = self.locate(instruction, callee_change=callee_change, scope=scope,
                                        nested=nested, optional=optional)
        self.types(reference[0].head)
        return actual[0] if actual is not None else None

    def offset(self, node):
        return self.parser.node_spans[id(node)][0]

    def ordered(self, *nodes):
        offsets = tuple(self.offset(node) for node in nodes)
        if offsets != tuple(sorted(set(offsets))):
            self.fail("notification boundary order changed")

    def reaching_nodes(self, before, after):
        """Visit the intervening nodes that can fall through to the destination."""
        start, end = self.offset(before), self.offset(after)
        target_path = self.paths[id(after)]
        for node, path, _, _ in self.actual_entries:
            if not start < self.offset(node) < end:
                continue
            for depth, (guard, edge) in enumerate(path, 1):
                if _encloses(path[:depth], target_path):
                    continue
                branch = guard.body if edge == 'body' else guard.otherwise
                if guard.kind == 'if' and _always_returns(branch):
                    break
            else:
                yield node

    def stable(self, name, before, after):
        """Reject explicit rebinding of a captured input across the boundary."""
        lhs = _tokens(name)
        self.types(lhs)
        assignments = {"=", "+=", "-=", "*=", "/=", "++", "--"}
        for node in self.reaching_nodes(before, after):
            head = node.head
            if node.kind == 'foreach' and head[1:1+len(lhs)] == lhs:
                self.fail("notification input is reassigned: " + name)
            for i in range(len(head) - len(lhs)):
                if head[i:i+len(lhs)] == lhs:
                    tail = head[i+len(lhs):]
                    prefix = head[:i]
                    while prefix and prefix[-1] == '(':
                        prefix = prefix[:-1]
                    while tail[:1] == (')',):
                        tail = tail[1:]
                    if tail and (tail[0] in assignments or
                                 prefix[-1:] in (("++",), ("--",))):
                        self.fail("notification input is reassigned: " + name)

    def binding(self, instruction, before):
        reference, actual = self.locate(instruction, before=before)
        self.types(reference[0].head)
        node = actual[0]
        self.ordered(node, before)
        lhs = instruction.split("=", 1)[0].strip()
        self.stable(lhs, node, before)
        return node

    def no_exit_between(self, before, after):
        start, end = self.offset(before), self.offset(after)
        for node, *_ in self.actual_entries:
            if (start < self.offset(node) < end and
                    (node.head[:1] == ("return",) or self.destroys_recipient(node))):
                self.fail("notification boundary crosses an early return or destruction")

    def live_recipient_at(self, before, after):
        self.stable('ThisAgent', before, after)
        if any(node.head[:1] == ('return',) or self.destroys_recipient(node)
               for node in self.reaching_nodes(before, after)):
            self.fail('notification recipient is destroyed or the success site is unreachable')

    @staticmethod
    def call_arguments(node):
        head = node.head
        if (node.kind != 'statement' or not head[0].startswith('$') or
                head[1:2] != ('(',) or head[-2:] != (')', ';')):
            return ()
        args, start, depth = [], 2, 0
        for i in range(2, len(head) - 1):
            token = head[i]
            if depth == 0 and token in (',', ')'):
                args.append(_unparen(head[start:i]))
                start = i + 1
            depth += (token == '(') - (token == ')')
        return tuple(args)

    @classmethod
    def destroys_recipient(cls, node):
        return (node.head[:1] in (("$deletegamepiece",), ("$henchman_dead",))
                and cls.call_arguments(node)[:1] == (("thisagent",),))

    def guard_before(self, instruction, before):
        reference, actual = self.locate(instruction)
        if actual[1] or actual[0] != reference[0]:
            self.fail("notification entry guard changed: " + instruction)
        self.ordered(actual[0], before)

    def _edit(self, start, end, replacement):
        if any((start < b and a < end) or
               (start == end and a < start < b) or
               (a == b and start < a < end) or (start == end == a == b)
               for a, b, _ in self.edits):
            self.fail("overlapping event edits")
        self.edits.append((start, end, replacement))

    def edit(self, node, transform):
        start, end = self.parser.node_spans[id(node)]
        self._edit(start, end, transform(self.current.text[start:end]))

    def insert(self, node, text, *, after=False):
        # An unbraced conditional owns only one statement. Adding a sibling
        # would leak it out of that branch; explicitly retain its ownership.
        entry = next(e for e in self.actual_entries if e[0] is node)
        if entry[1] and len(entry[2]) == 1:
            self.edit(node, lambda original: 'begin\n' +
                      (original + text if after else text + original) + '\nend')
            return
        offset = self.parser.node_spans[id(node)][int(after)]
        self._edit(offset, offset, text)

    def text(self):
        text = self.current.text
        for start, end, replacement in sorted(self.edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        return text
