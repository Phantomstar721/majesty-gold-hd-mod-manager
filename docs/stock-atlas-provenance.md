# Stock atlas provenance

An IMAG frame index belongs to the positional TILE table from the archive that
supplied that image. Original and expansion archives may reuse the same ordinal
for unrelated pictures. Combining their named image entries does not make all
those images consumers of the final expansion positional table.

The runtime-presenter dependency path previously copied a base-only stock IMAG
unchanged, then supplied expansion tiles at its indices. This corrupted the
stock spell atlas when a private information row required it: character-spell
frames displayed fragments of the main menu instead.

Composition now retains the last stock archive owning each required image.
Tile and external-palette dependencies resolve within that archive and its
earlier ancestors, not later archives. The original image directory, frame
ordering and renderer ABI remain unchanged. Only proven tile/palette references
are rewritten when their payload conflicts with an occupied output slot.

Conflicting dependencies are appended after the composed allocation; custom
images and existing tile slots are never overwritten. Shared copied payloads
are reused, and output allocation counts and image relocation reports reflect
the appended records. Missing dependencies and unsupported shapes fail closed.
No image-specific ID exception, native hook or runtime scanning is involved.

Regression coverage includes a base atlas and an expansion/private image
sharing a tile number with different pixels and palettes. An installed-resource
audit also compares every frame and external palette in the effective stock
interface image family (font glyph-table atlases use a different format).
These checks operate on in-memory archives, not the user's prepared profile.
