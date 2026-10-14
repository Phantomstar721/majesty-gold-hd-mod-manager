# CAM Container Format

Validated container reference for Majesty Gold HD `*.cam` archives.

## Container

Validated game and SDK samples begin with:

```text
43 59 4C 42 50 43 20 20 01 00 01 00
```

ASCII plus version bytes:

```text
CYLBPC  \x01\x00\x01\x00
```

Container integer fields are little-endian unsigned 32-bit values.

## File Header

```text
0x00  12 bytes  fixed magic/version
0x0C   4 bytes  section count
0x10   4 bytes  content header length
0x14   8 * N    section directory entries
```

Each section directory entry:

```text
4 bytes  extension, e.g. WAVE, IMAG, TILE, SPLT, CUT[space]
4 bytes  absolute offset of this section's content-header block
```

## Content Header

Each section header appears sequentially:

```text
4 bytes       entry count
4 bytes       section padding/flags
28 * entries  entry headers
```

Each entry header:

```text
20 bytes  fixed-width raw entry name, usually null-padded
4 bytes   absolute data offset
4 bytes   data size
```

Important: the 4-byte section padding field is not always zero in real game CAMs.
Preserve it when unpacking and repacking.

For numeric TILE/SPLT lookup, section flag bit 0 selects the ordinal shortcut.
Without it, the first four bytes of the TOC name are a little-endian resource
ID; these IDs need not equal record positions or start at zero. Duplicate IDs
resolve to the last TOC entry. IMAG and PALT named resources are not numeric
tables and must not undergo this conversion.

The art composer converts ID-keyed tables to a bounded dense slot view before
ancestry comparison, dependency validation and collision relocation. Missing
IDs remain empty, without fabricated stock-lineage names. The container reader
and writer preserve the original TOC and flags; they do not normalize files.
Existing ordinal tables retain their interpretation even if their stored IDs
differ. Output remains in the existing dense art format, with IMAG-to-TILE and
TILE-to-SPLT references relocated together when necessary.

Native numeric lookup reference: research `docs/resource-acquire-contract.md`,
entry selection/identity (ordinal shortcut versus reverse ID search). This
change adds no executable patch or runtime hook. Sparse TILE IDs are bounded
to 0..65534 (65535 is the no-frame sentinel). SPLT keys are full DWORDs,
including printable FourCC values. High SPLT keys are allocated compact slots
after stock and authored numeric slots, with matching TILE references rewritten
at the documented external-palette field. A shared mapping covers all CAMs in
one component. The number of output palette slots is bounded, not the numeric
value of a source palette key. An unreferenced key does not create an alias at
its physical TOC position.

## Content

Entry data is raw bytes. In ordinary archives, content is stored sequentially in section
order and entry order, but readers should slice by absolute offset and size.

## Known Section Types

- `WAVE`: WAV audio files.
- `DSDP`: sound phase definitions in runtime sound description archives.
- `DSND`: sound descriptions in runtime sound description archives.
- `DSDG`: sound groups in runtime sound description archives.
- `IMAG`: image/animation descriptors.
- `TILE`: sprite frame pixel data or terrain tile data, depending on archive.
- `SPLT`: palette data.
- `CUT `: small fixed-size opaque resource in `maindata.cam`.

## Reader/writer validation

A container-safe implementation must:

1. Read all SDK example CAMs.
2. Unpack them with a manifest.
3. Repack them byte-for-byte when unchanged.
4. Repack after replacing one WAVE entry.
5. Load through a test quest or mod instead of replacing base game files.
