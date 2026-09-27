"""Prove notification anchors and captured inputs, not author-owned gameplay.

Paths include every branch/loop and body/else edge. A call in a different
branch is not the same boundary, but unrelated siblings need not match stock.
All changes use source spans so selected instructions survive literally.
"""

from .gpl_function_merge import _SourceParser, _tokens, _unparen


def entries(nodes, path=()):
    for index, node in enumerate(nodes):
        yield node, path, nodes, index
        yield from entries(node.body, (*path, (node.kind, node.head, "body")))
        yield from entries(node.otherwise, (*path, (node.kind, node.head, "else")))


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
        self.edits = []

    def fail(self, detail):
        raise ValueError(f"{self.current.name} ({self.current.source_name}): Manager cannot place its "
                         f"notification at the required success/cleanup boundary: {detail}")

    def locate(self, instruction, *, callee_change=False):
        head = _tokens(instruction)
        references = [e for e in self.stock_entries if e[0].head == head]
        if len(references) != 1:
            self.fail("stock reference boundary is missing or ambiguous: " + instruction)
        reference = references[0]
        def same_head(actual):
            return (actual == head or callee_change and actual[:1]
                    and actual[0].startswith('$') and actual[1:] == head[1:])
        matches = [e for e in self.actual_entries
                   if e[1] == reference[1] and same_head(e[0].head)]
        if len(matches) != 1:
            self.fail("missing, moved or ambiguous boundary: " + instruction)
        return reference, matches[0]

    def types(self, tokens):
        used = set(tokens)
        if any(self.locals.get(name) != kind for name, kind in self.stock_locals.items()
               if name in used):
            self.fail("event variable type changed")

    def anchor(self, instruction, *, callee_change=False):
        """Require one insertion point in its original conditional scope."""
        reference, actual = self.locate(instruction, callee_change=callee_change)
        self.types(reference[0].head)
        return actual[0]

    def offset(self, node):
        return self.parser.node_spans[id(node)][0]

    def ordered(self, *nodes):
        offsets = tuple(self.offset(node) for node in nodes)
        if offsets != tuple(sorted(set(offsets))):
            self.fail("notification boundary order changed")

    def stable(self, name, before, after):
        """Reject explicit rebinding of a captured input across the boundary."""
        lhs = _tokens(name)
        self.types(lhs)
        start, end = self.offset(before), self.offset(after)
        assignments = {"=", "+=", "-=", "*=", "/=", "++", "--"}
        for node, *_ in self.actual_entries:
            if not start < self.offset(node) < end:
                continue
            head = node.head
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
        node = self.anchor(instruction)
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
