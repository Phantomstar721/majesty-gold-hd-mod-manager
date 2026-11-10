"""Typed WE|1 records, following the supplied native parse_line contract.

This module parses and relocates data only. It neither installs an engine nor
claims that a native build supports these records. Callers supply the effective,
dataset-scoped resources after ordinary preferred-mod selection.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
import re
from typing import Mapping

from .strt import parse_strt, StrtTable, StrtRecord

PANEL_SERVICE = "window-engine.v1"
ACTION_SERVICE = "script-functions.map-action.v1"
FUNCTION_KINDS = frozenset(("CLICK", "TEXT", "HINT", "STATE", "STATEHINT", "SHOWIF",
    "HIDEIF", "LIST", "TABLE", "TCLICK", "TICK", "CHOSEN", "PICK", "BAR"))
SIMPLE_KINDS = frozenset(("HIDE", "BACK", "HIDEBUSY", "TFOLLOW", "TOPEN", "TALL"))
NUMERIC_KINDS = frozenset(("RECRUIT", "COST", "DOES", "HIDEWHEN"))
LABEL_KINDS = frozenset(("LABEL", "CHOICE"))
COLUMN_VALUES = frozenset(("count", "level", "hp", "maxhp", "gold"))


class PanelEngineError(ValueError):
    pass


def _number(value, *, nonzero=False):
    if not re.fullmatch(r"[0-9]+", value) or not 0 <= int(value) <= 0xffffffff:
        raise PanelEngineError("WE1 expects a decimal uint32 value: " + value)
    if nonzero and int(value) == 0:
        raise PanelEngineError("WE1 control/reference must be nonzero")
    return int(value)


def _symbol(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value) or len(value) > 47:
        raise PanelEngineError("WE1 callback must be an identifier of at most 47 bytes: " + value)


def _fourcc(value):
    if len(value) != 4 or any(ord(c) < 32 or ord(c) > 255 or c == "|" for c in value):
        raise PanelEngineError("WE1 expects a four-byte resource ID: " + value)


@dataclass(frozen=True)
class Reference:
    kind: str
    field: int
    value: str
    # TABLE stores its scrollbar and mode together as "bar~mode".
    component: int | None = None


@dataclass(frozen=True)
class Behavior:
    fields: tuple[str, ...]
    references: tuple[Reference, ...]

    @property
    def kind(self):
        return self.fields[2]

    def text(self):
        return "|".join(self.fields)

    def remap(self, *, panels=None, callbacks=None, images=None, controls=None):
        maps = {"panel": panels or {}, "callback": callbacks or {},
                "image": images or {}, "control": controls or {}}
        fields = list(self.fields)
        for reference in self.references:
            replacement = maps[reference.kind].get(reference.value)
            if replacement is None:
                continue
            if reference.component is None:
                fields[reference.field] = str(replacement)
            else:
                pieces = fields[reference.field].split("~")
                pieces[reference.component] = str(replacement)
                fields[reference.field] = "~".join(pieces)
        return parse_behavior("|".join(fields))


def parse_behavior(text):
    if isinstance(text, bytes):
        text = text.decode("latin1")
    if not text.startswith("WE|"):
        return None
    fields = tuple(text.split("|"))
    if len(fields) < 4 or fields[:2] != ("WE", "1"):
        raise PanelEngineError("Unsupported or incomplete Window Engine protocol")
    if "\0" in text:
        raise PanelEngineError("WE1 record contains an embedded NUL")
    kind = fields[2]
    refs = []
    def need(count):
        if len(fields) < count:
            raise PanelEngineError("Incomplete WE1 " + kind + " record")
    def callback(index):
        need(index + 1)
        _symbol(fields[index])
        refs.append(Reference("callback", index, fields[index]))
    def control(index, *, component=None):
        need(index + 1)
        value = fields[index] if component is None else fields[index].split("~")[component]
        _number(value, nonzero=True)
        refs.append(Reference("control", index, value, component))
    if kind == "BASE":
        _fourcc(fields[3])
        refs.append(Reference("panel", 3, fields[3]))
    elif kind == "CLASS":
        if fields[3] not in ("panel", "building", "bare", "list"):
            raise PanelEngineError("Unsupported WE1 class: " + fields[3])
    else:
        _number(fields[3], nonzero=True)
        if kind != "TALL":
            control(3)
        if kind in SIMPLE_KINDS:
            pass
        elif kind == "PANEL":
            need(5)
            _fourcc(fields[4])
            refs.append(Reference("panel", 4, fields[4]))
        elif kind in FUNCTION_KINDS:
            callback(4)
            if kind in ("BAR", "STATE", "STATEHINT", "TABLE"):
                need(6)
                if not fields[5]:
                    raise PanelEngineError("WE1 " + kind + " needs its value field")
            if kind == "BAR":
                if fields[5].isdigit():
                    _number(fields[5], nonzero=True)
                else:
                    callback(5)
            elif kind == "TABLE":
                pieces = fields[5].split("~")
                if len(pieces) != 2 or pieces[1] not in ("0", "1"):
                    raise PanelEngineError("WE1 TABLE expects scrollbar~mode (0 or 1)")
                if _number(pieces[0]):
                    control(5, component=0)
            elif kind == "TICK" and len(fields) > 5 and fields[5] != "-":
                if not re.fullmatch(r"-?[0-9]+", fields[5]):
                    raise PanelEngineError("WE1 TICK expects an integer or '-'")
        elif kind in NUMERIC_KINDS:
            need(5)
            _number(fields[4], nonzero=kind in ("DOES", "HIDEWHEN"))
            if kind in ("DOES", "HIDEWHEN"):
                control(4)
        elif kind in LABEL_KINDS:
            need(5)
        elif kind == "TCOL":
            need(6)
            if fields[4] not in COLUMN_VALUES:
                callback(4)
            if not 10 <= _number(fields[5]) <= 120:
                raise PanelEngineError("WE1 table column width must be 10..120")
        elif kind in ("TSEP", "TLINE"):
            need(6)
            _fourcc(fields[4])
            _number(fields[5])
            refs.append(Reference("image", 4, fields[4]))
        else:
            raise PanelEngineError("Unsupported WE1 behavior: " + kind)
    return Behavior(fields, tuple(refs))


def behaviors(table):
    rows = tuple(b for row in table.records if (b := parse_behavior(row.text)) is not None)
    if sum(b.kind in ("BASE", "CLASS") for b in rows) > 1:
        raise PanelEngineError("WE1 panel must have at most one BASE or CLASS declaration")
    columns = Counter(b.fields[3] for b in rows if b.kind == "TCOL")
    if any(count > 4 for count in columns.values()):
        raise PanelEngineError("WE1 table has more than four value columns")
    tables = [b.fields[3] for b in rows if b.kind == "TABLE"]
    if len(set(tables)) != len(tables) or len(tables) > 16:
        raise PanelEngineError("WE1 panel has duplicate or too many table stores")
    return rows


def rewrite_table(data, **maps):
    table = parse_strt(data)
    behaviors(table)
    result = StrtTable(table.version, tuple(
        StrtRecord(row.string_id, b.remap(**maps).text().encode("latin1") if
                   (b := parse_behavior(row.text)) is not None else row.text)
        for row in table.records))
    behaviors(result)
    return data if result == table else result.to_bytes()


def find_panels(resources: Mapping[tuple[bytes, bytes], bytes]):
    """Inspect effective loaded records only; never scans package directories."""
    result = {}
    for (section, key), data in resources.items():
        if section != b"STRT":
            continue
        # Unpaired prose/example tables are not controllers. For stock STRT
        # overrides the caller includes the corresponding resolved stock SMNU.
        if (b"SMNU", key) not in resources:
            continue
        rows = behaviors(parse_strt(data))
        if rows:
            result[key] = rows
    return result
