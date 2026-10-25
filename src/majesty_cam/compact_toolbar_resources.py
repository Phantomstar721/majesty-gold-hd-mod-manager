"""Clone stock AP92 controls and their STRT hover bindings, entirely in memory."""
from dataclasses import replace
import struct
from .cam import CamSection, read_cam
from .private_recruitment import records, control_record
from .strt import parse_strt, StrtRecord, StrtTable


def extend_chrome_tile(data, width):
    """Extend the stock indexed raster's middle, retaining both gold endcaps.

    No resampling or palette conversion: existing columns remain byte-identical.
    TILE v1 dimensions/stride, centered anchor and embedded palette offset follow
    the existing stock raster contract used by the interface asset reader.
    """
    if len(data) < 26:
        raise ValueError("compact toolbar chrome tile is truncated")
    version, height, old_width, stride = struct.unpack_from("<4H", data)
    mode, palette = struct.unpack_from("<HI", data, 20)
    if (version, height, old_width, stride) != (1, 34, 590, 590):
        raise ValueError("compact toolbar chrome requires its stock indexed raster")
    if mode != 1 or palette != 26 + height * stride or len(data) != palette + 1032:
        raise ValueError("compact toolbar chrome palette layout changed")
    if not old_width <= width <= 32767:
        raise ValueError("compact toolbar chrome width is out of range")
    if struct.unpack_from("<hh", data, 10) != (old_width // 2, height // 2):
        raise ValueError("compact toolbar chrome anchor changed")
    extra = width - old_width
    cut = old_width // 2
    header = bytearray(data[:26])
    struct.pack_into("<HH", header, 4, width, width)
    struct.pack_into("<h", header, 10, width // 2)
    struct.pack_into("<I", header, 22, 26 + height * width)
    rows = []
    for y in range(height):
        row = data[26+y*stride:26+(y+1)*stride]
        # Repeat a central 25px stock stretch, away from either endcap.
        middle = row[cut-25:cut]
        rows.append(row[:cut] + (middle * ((extra+24)//25))[:extra] + row[cut:])
    return bytes(header) + b"".join(rows) + data[palette:]


def bind_toolbar_chrome(results, text_archive, registry):
    if not registry.toolbar_actions:
        return results
    from .art import parse_stock_imag_tile_references
    from .cam import CamEntry, pad_name
    panel = next(e for s in text_archive.sections if s.extension == b"SMNU"
                 for e in s.entries if e.name[:4] == b"AP92")
    width = struct.unpack_from("<I", panel.data, 16)[0]
    matches = [(i, e) for i, result in enumerate(results)
               for s in result.archive.sections if s.extension == b"IMAG"
               for e in s.entries if e.name[:4] == b"INDz"]
    if len(matches) != 1:
        raise ValueError("compact toolbar requires one effective stock chrome image")
    index, image = matches[0]
    result = results[index]
    tiles = next(s for s in result.archive.sections if s.extension == b"TILE")
    refs = [r for r in parse_stock_imag_tile_references(image.data,
            tile_count=len(tiles.entries), entry_name=image.name).references if r.set_id == 1012]
    if len(refs) != 1 or refs[0].direction or refs[0].frame:
        raise ValueError("compact toolbar chrome must retain its single stock frame")
    slot = len(tiles.entries)
    if slot >= 65535:
        raise ValueError("compact toolbar chrome exhausted TILE slots")
    tile = tiles.entries[refs[0].tile_index]
    new_tile = CamEntry(pad_name(struct.pack("<I", slot)), extend_chrome_tile(tile.data, width))
    blob = bytearray(image.data)
    struct.pack_into("<I", blob, refs[0].offset, refs[0].flag_bits | slot)
    new_image = replace(image, data=bytes(blob))
    sections = tuple(replace(s, entries=(*s.entries, new_tile)) if s is tiles else
        replace(s, entries=tuple(new_image if e is image else e for e in s.entries))
        if s.extension == b"IMAG" else s for s in result.archive.sections)
    report = replace(result.report, tile_allocation=replace(result.report.tile_allocation,
                     final_count=slot+1))
    updated = replace(result, archive=replace(result.archive, sections=sections), report=report)
    return (*results[:index], updated, *results[index+1:])


def extend_stock_bounds(payload, stock_payload, right):
    """Preserve stock token-2 geometry, including signed -1 centering fields.

    The generic sentinel splitter is not a property parser: -1 coordinates
    must not be mistaken for the end of the dialog header.
    """
    root = struct.unpack_from("<6I", payload)
    stock = struct.unpack_from("<6I", stock_payload)
    if stock != (1000, 2, 0xFFFFFFFF, 0xFFFFFFFF, 590, 34):
        raise ValueError("stock compact toolbar dialog geometry changed")
    if root[:2] != stock[:2] or root[5] != stock[5] or root[4] < stock[4]:
        raise ValueError("effective compact toolbar dialog geometry is incompatible")
    donor_rows = records(stock_payload)
    last_right = max(control_record(donor_rows, control)[2] +
                     control_record(donor_rows, control)[4]
                     for control in range(4401, 4423))
    width = max(root[4], right + stock[4] - last_right)
    rows = list(records(payload))
    background = control_record(rows, 1)
    stock_background = control_record(donor_rows, 1)
    if background[2:6] != (0, 0, root[4], root[5]) or stock_background[2:6] != (0, 0, 590, 34):
        raise ValueError("effective compact toolbar background geometry is incompatible")
    expanded = list(background)
    expanded[4] = width
    rows[rows.index(background)] = tuple(expanded)
    output = bytearray(b"".join(struct.pack(f"<{len(row)}I", *row) for row in rows))
    struct.pack_into("<I", output, 4 * 4, width)
    return bytes(output)


def append_toolbar(archive, game_path, registry, *, dataset="Majesty"):
    if not registry.toolbar_actions:
        return archive
    stock = read_cam(game_path / "Data/textdata.cam")
    if dataset not in ("Majesty", "MajestyExpansion"):
        raise ValueError("unsupported compact toolbar dataset")

    def entry(source, section):
        matches = [e for s in source.sections if s.extension == section
                   for e in s.entries if e.name[:4] == b"AP92"]
        if len(matches) > 1:
            raise ValueError("compact toolbar requires one effective AP92 resource")
        return matches[0] if matches else None

    stock_panel, stock_help = entry(stock,b"SMNU"), entry(stock,b"STRT")
    if stock_panel is None or stock_help is None:
        raise ValueError("stock compact toolbar resource is missing")
    scoped_stock = (read_cam(game_path / "DataMX/mx_textdata.cam")
                    if dataset == "MajestyExpansion" else stock)
    panel = entry(archive,b"SMNU") or entry(scoped_stock,b"SMNU") or stock_panel
    help_entry = entry(archive,b"STRT") or entry(scoped_stock,b"STRT") or stock_help
    current = list(records(panel.data))
    background = control_record(current, 1)
    if background[8:12] != (12, int.from_bytes(b"INDz", "little"), 13, 1012):
        raise ValueError("compact toolbar background uses an unsupported chrome binding")
    donor = control_record(records(stock_panel.data),4417)
    neighbor = control_record(records(stock_panel.data),4418)
    stride = neighbor[2]-donor[2]
    if donor[2:6] != (4,4,25,25) or stride != 25:
        raise ValueError("stock compact toolbar geometry changed")
    # Literal stock properties, not substring scans of an arbitrary widget.
    if donor[6:] != (0x21,0,0xA,2,0xA,0x10000,0xC,0x4E544E49,0xD,1001,
                     3,2,3,0x400,3,8,6,4417,0xFFFFFFFF):
        raise ValueError("stock compact toolbar button shape changed")
    table = parse_strt(help_entry.data)
    help_rows = list(table.records)
    used_help = {r.string_id for r in help_rows}
    used_controls = set()
    xs = []
    for record in current:
        if len(record)<7:continue
        for i in range(6,len(record)-1):
            if record[i]==6:
                used_controls.add(record[i+1])
                if 4401<=record[i+1]<=4500:xs.append(record[2]+record[4])
    if not xs:raise ValueError("effective compact toolbar has no stock spell row")
    # Reuse the immediately preceding stock group boundary: Sun Scorch ends
    # at534 and Winged Feet starts at537. Intra-group cells keep their stride.
    prior_group_last = control_record(records(stock_panel.data), 4410)
    final_group_first = control_record(records(stock_panel.data), 4407)
    group_gap = final_group_first[2] - (prior_group_last[2] + prior_group_last[4])
    if not 0 <= group_gap < stride:
        raise ValueError("stock compact toolbar group boundary is invalid")
    # Keep every dataset's stock controls (including expansion's compressed
    # Sorcerer cells and Abode overlays). Private full-size cells start outside
    # the stock enclosure, not inside the last compressed group.
    x=max(struct.unpack_from("<I", panel.data, 16)[0], max(xs)+group_gap)
    for toolbar in registry.toolbar_actions:
        matches=[a for a in registry.sovereign_target_actions
                 if (a.panel_key,a.action_key)==(toolbar.panel_key,toolbar.action_key)]
        if len(matches)!=1:raise ValueError("compact toolbar action reference is ambiguous")
        control=matches[0].private_control_id
        if control in used_controls:
            raise ValueError("compact toolbar command collides with an existing AP92 control")
        used_controls.add(control)
        help_id=max(used_help,default=-1)+1
        used_help.add(help_id)
        help_rows.append(StrtRecord(help_id,toolbar.hover_text.encode("cp1252")))
        row=list(donor)
        row[2]=x;row[7]=help_id
        row[13]=int.from_bytes(toolbar.icon_id.encode("ascii"),"little")
        row[15]=toolbar.icon_set;row[23]=control
        current.insert(len(current)-1,tuple(row))
        x+=stride
    smnu=b"".join(struct.pack(f"<{len(row)}I",*row) for row in current)
    smnu=extend_stock_bounds(smnu, stock_panel.data, x-stride+donor[4])
    replacements={b"SMNU":replace(panel,data=smnu),
                  b"STRT":replace(help_entry,data=StrtTable(table.version,tuple(help_rows)).to_bytes())}
    sections=[]
    for section in archive.sections:
        if section.extension not in replacements:
            sections.append(section);continue
        replacement=replacements.pop(section.extension)
        entries=[e for e in section.entries if e.name[:4]!=b"AP92"]
        entries.append(replacement)
        sections.append(replace(section,entries=tuple(entries)))
    for extension,replacement in replacements.items():
        sections.append(CamSection(extension, (replacement,)))
    return replace(archive,sections=tuple(sections))
