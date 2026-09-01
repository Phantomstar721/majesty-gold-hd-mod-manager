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
