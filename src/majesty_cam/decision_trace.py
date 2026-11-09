"""Temporary opt-in GPL decision breadcrumbs; no runtime addresses or game state.

Disabled unless the diagnostic Manager process explicitly requests function names.
Uses the stock DebugOut(911, ...) facility. Output enablement must be probed in
the next user-launched session; absence of output never means absence of execution.
"""
from dataclasses import replace
import json
import os
import re

from .gpl import DefinitionKind, SemanticMergeResult
from .gpl_function_merge import _Parser, _Node, _code, _render

ENV = 'MAJESTY_DECISION_TRACE'
PREFIX = 'MMDEC1'


def requested():
    raw = os.environ.get(ENV, '').strip()
    if not raw:
        return frozenset()
    names = raw.split(',')
    if len(names) > 8 or any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', n) for n in names):
        raise ValueError('Decision trace needs 1..8 comma-separated GPL function names')
    return frozenset(n.casefold() for n in names)


def instrument(text):
    signature, declarations, body = _Parser(text).function()
    name = signature[1]
    # Require an actual agent argument: no property lookups, invented identity
    # helper, new locals, timers, or persistent per-unit diagnostic state.
    if len(signature) < 6 or signature[3] != 'agent':
        raise ValueError('Decision trace requires an agent as the first argument')
    actor = signature[4]
    if PREFIX in text:
        raise ValueError('Function already contains temporary decision tracing')
    serial = 0

    def mark(label):
        literal = json.dumps(f'{PREFIX} {name} {label}', ensure_ascii=True)
        return _Node('statement', ('$debugout', '(', '911', ',', literal, ',', actor, ')', ';'))

    def visit(nodes):
        nonlocal serial
        out = []
        for node in nodes:
            serial += 1
            index = serial
            calls = ','.join(t[1:] for t in node.head if t.startswith('$'))
            label = f'{index} {node.head[0]} {calls}'.strip()
            out.append(mark('before ' + label))
            out.append(replace(node, body=visit(node.body), otherwise=visit(node.otherwise)))
            if node.head[0] != 'return':
                out.append(mark('after ' + label))
        return tuple(out)

    traced = (mark('entry'), *visit(body), mark('fallthrough'))
    # Native GPL requires DECLARE even when its local-variable section is empty.
    lines = [_code(signature), 'declare']
    lines.extend(f'\t{kind} {variable};' for variable, kind in declarations.items())
    lines.extend(('begin', *_render(traced), 'end'))
    return '\n'.join(lines)


def transform(result):
    names = requested()
    if not names:
        return result
    from .scoped_output import source_items
    items = source_items(result.source_set)
    edited = tuple(replace(item, text=instrument(item.text), span=None)
                   if item.kind == DefinitionKind.FUNCTION and item.normalized_name in names
                   else item for item in items)
    if edited == items:
        return result
    return replace(result, source_set=SemanticMergeResult(edited, ()).emit_project_source_set())


def launch_arguments(arguments):
    """Only the explicitly diagnostic Manager launch opts into stock logging."""
    return (*arguments, '-debugout') if requested() and '-debugout' not in arguments else tuple(arguments)
