# Version-5 frame remapping correction

The native version-5 reader consumes a 24-byte direction header, not the
version-4 20-byte header. Direction-end anchoring is wrong when event data
follows the frames. This caused coordinates and event words to be interpreted
as TILE references, while actual art dependencies were lost.

## Serialized contract

Header: signed XY words; stream/frame counts at +4/+6; rectangle mask DWORD
+8; auxiliary mask DWORD +12; timing-presence WORD +16; group count WORD +18;
event mask DWORD +20. Each rectangle bit consumes eight bytes. Each auxiliary
bit consumes a DWORD count followed by count eight-byte entries. Each frame
group consumes a DWORD tag followed by streams*frames eight-byte pairs.
Pairs contain signed XY at +0 and reference/flags at +4. Optional timing is
20 bytes; each event-mask bit consumes a DWORD count and count 32-byte records.
Native seeks honor directory offsets, so gaps between bodies are preserved.
The Manager supports the observed one-group shape and rejects unsupported
groups rather than falling back to backward guessing. No resource IDs or mod
names select the parser. All non-reference bytes are preserved.

## Primary evidence, 2026-10-13

Research references: imag-frame-placement.md, imag-group-selection.md and
imag-direction-timing.md in the research repository. Their v4 evidence did
not establish v5. Graph README at f2644580d33ad98703361cd8fc88c825068161ef
explicitly excludes native consumer layouts; no applicable node was found.

Read-only bounded disassembly of modified-beta2 E15CF0D8...19030B:
67D8C1 dispatches v5 to699CC0;699E7A calls6A79C0. The latter reads24 bytes,
calls6A6B50 for masks,6A6CE0 for frame groups,6A78A0 for timing, then6A6DD0
for events.6A6DD0 tests the header+20 mask and calls6A82C0; that reads a
count, loops records through6A7E80, which reads32 bytes. Auxiliary6A8A10
reads a count and loops eight-byte records. Existing group/pair readers are
the same as v4, including6EAFF0's XY/reference field rearrangement.

Exact-byte matching excluding relative CALL displacements locates the same
direction/event-mask/event-record instruction bodies on all three fixtures:

| Profile SHA256 | Direction | Event mask | Event record |
|---|---|---|---|
|255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4|692430|691840|6928F0|
|05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82|6A79C0|6A6DD0|6A7E80|
|65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792|6A6EB0|6A62C0|6A7370|

These are static file-format observations, not native playback or complete
allocation/cleanup lifecycle claims. No runtime hooks or executable writes.

## Regression witness

The installed MKART_hi.CAM contains exactly nine affected named IMAG records
and29 unaffected records. BBT1 sub240 begins at2244; direction2312; pair
start2340; first TILE DWORD2344 is20269. Its21 frame pairs end2508;
the event count and32-byte event end2544. The old parser starts at2376,
misreading coordinate DWORD2380 and event data through2540.

Comparing dependencies using the production sparse-slot preference identifies
exactly the15 lost TILE IDs reported by the author:20029,20030,20037,20038,
20228,20229,20239,20240,20250,20262,20263,20268,20269,20304,20305.
The author's250 rewritten words/18 imported stock tiles depend on their
specific combination/allocation and are not independently asserted here.

The previous art tests reused the same parser to find dependencies and validate
rewrites. They could therefore agree on the wrong fields. test_imag_v5 uses
independently authored offset expectations and whole-record byte comparison,
including rectangles, auxiliary records, timing, event tails and body gaps.
It is mandatory in both release and development regression gates.

Read-only in-memory composition witness: Workshop3819398211/Data/MKART_hi.CAM,
SHA256409d871b1e108dc000be4e79b43f677e2c7b53f47974ee0b77cdf23a30d704b3.
The resulting BBT1 TILE words at2344..2504 match the independently pinned
source sequence (ten20269, eleven20270) through the allocator mapping.
Every corresponding XY DWORD and the2508..2544 event bytes are unchanged.
All15 formerly missing TILE payloads are retained byte-for-byte. In this
single-provider case their IDs remain unchanged, so the relocation dictionary
is empty; absence from that dictionary does not mean a missing dependency.
Actual-guild art checks additionally exercise their combined allocation path.
