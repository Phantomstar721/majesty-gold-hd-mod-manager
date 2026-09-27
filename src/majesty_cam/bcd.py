"""Read native BCD definition tables, without interpreting or rewriting code.

The stock loader reads instruction, symbol and DAT tables in that order.
Symbol maps enumerate declarations, not calls/string operands. See
docs/stock-bcd-ownership.md for the compiler and all-version loader trace.
"""
from __future__ import annotations

import re
import struct

from .gpl import DefinitionKind


class BcdIndexError(ValueError):
    pass


class _Reader:
    def __init__(self, data, start=0, end=None):
        self.data, self.pos = data, start
        self.end = len(data) if end is None else end

    def uint(self):
        if self.pos + 4 > self.end:
            raise BcdIndexError('truncated BCD table')
        value = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return value

    def block(self, version):
        start = self.pos
        size = self.uint()
        if size < 16 or start + size > self.end or self.uint() != version:
            raise BcdIndexError('unsupported or truncated BCD block')
        end = start + size
        if self.data[end - 8:end] != b'\0\0\0\0\xff\xff\xff\xff':
            raise BcdIndexError('invalid BCD block terminator')
        body = _Reader(self.data, self.pos, end - 8)
        self.pos = end
        return body

    def count(self):
        count = self.uint()
        # Every named record occupies at least one string byte and a block.
        if count > (self.end - self.pos) // 17:
            raise BcdIndexError('invalid BCD definition count')
        return count

    def name(self, kind):
        end = self.data.find(b'\0', self.pos, self.end)
        if end < 0:
            raise BcdIndexError('unterminated BCD definition name')
        raw = self.data[self.pos:end]
        pattern = rb'#[A-Za-z_][A-Za-z_0-9]*' if kind is DefinitionKind.EXPRESSION else rb'[A-Za-z_][A-Za-z_0-9]*'
        if not re.fullmatch(pattern, raw):
            raise BcdIndexError('unsupported BCD definition name')
        self.pos = end + 1
        return raw.decode('ascii').lower()

    def finish(self):
        if self.pos != self.end:
            raise BcdIndexError('unexpected data in BCD table')


def definition_keys(data: bytes) -> frozenset:
    """Index only supported, structurally framed native declaration tables.

    This is not a bytecode verifier. Opaque executable payloads stay native;
    an unsupported envelope/table is unknown, never an empty ownership set.
    """
    file = _Reader(data)
    if file.uint() != len(data) - 4:
        raise BcdIndexError('invalid BCD file size')
    root = file.block(0xffffffff)
    file.finish()
    if root.uint() != 0:
        raise BcdIndexError('BCD contains compilation errors')
    root.block(0)  # Instructions: payload is not needed to read declarations.
    symbols = root.block(1)
    keys = set()
    for kind in (DefinitionKind.PROTOTYPE, DefinitionKind.FUNCTION, DefinitionKind.EXPRESSION):
        for _ in range(symbols.count()):
            key = kind, symbols.name(kind)
            if key in keys:
                raise BcdIndexError('duplicate BCD definition')
            keys.add(key)
            symbols.block(1)  # Serialized signature/local types, not GPL text.
    symbols.finish()
    records = root.block(1)
    for _ in range(records.count()):
        key = DefinitionKind.DAT_BLOCK, records.name(DefinitionKind.DAT_BLOCK)
        if key in keys:
            raise BcdIndexError('duplicate BCD data record')
        keys.add(key)
        records.block(1)
    records.finish()
    root.finish()
    return frozenset(keys)
