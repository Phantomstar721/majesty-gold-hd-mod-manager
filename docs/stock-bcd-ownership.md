# Compiled Standard script ownership

Static trace and disposable compiler fixtures, 2026-09-27. This is a read-only
Prepare-time file check, not a VM extension or a decompiler.

## Native reference and lifecycle

The dataset loader resolves a manifest GPL target and sends it to the BCD file
loader. That loader opens the stream, enters its root serialization block, reads
the compilation-error flag, then loads instructions, symbol tables and DAT
records in that order. Names in the symbol maps describe supplied definitions;
function calls, quoted strings and source-filename diagnostics are not entries
in those maps. The native loader owns registration, linking and subsequent
execution. The Manager leaves the Standard BCD and its native load position
unchanged, emitting only source-backed definitions it actually needs to combine.

There are no callbacks, per-unit state, timers, cancellation handlers or UI
refresh behavior to clone for a read-only file index. The index is released with
its bounded input snapshot; it has no runtime lifetime or cleanup obligation in
the game. Existing file-identity and plan checks guard changes during preparation.

The following reader bodies match across all supported profiles after masking
address operands and relative branch destinations. The audit also checks the
loader's calls to the three readers and block helpers in their original order.
These are VAs at image base `0x400000`, not injected hooks.

| Reader | Steam public 1.5.2.24 | Steam beta2 1.5.2.28 | GOG 1.5.2.28 |
| --- | --- | --- | --- |
| BCD file | `548E40` | `55D740` | `55CA40` |
| Block start | `603C10` | `618F50` | `6182A0` |
| Block end | `603C50` | `618F90` | `6182E0` |
| Instruction table | `55C8A0` | `5729E0` | `571CE0` |
| Symbol tables | `579F90` | `5900B0` | `58F3B0` |
| DAT table | `56A310` | `580430` | `57F730` |

Reproduce with `scripts/audit_bcd_ownership.py <beta2> <public> <gog>` using the
shared pefile/capstone environment. The inspected fixtures have SHA-256:

- Public: `d21ba8312433e3e8f784b71943bdc38ddde7590e57abfb29ef347330cc77612d`
- Beta2: `05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82`
- GOG: `65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792`

The Steam fixtures contain previously documented unrelated QOL patches; this
comparison establishes the listed reader bodies, not whole-file pristine status.

## Indexed format

All integers are little-endian 32-bit values. The initial word is file length
minus four. The root block starts at offset four and contains:

1. A block size (including its own header/footer) and version `0xFFFFFFFF`.
2. The compilation-error flag, required to be zero for this check.
3. A version-zero instruction block, skipped using its declared size.
4. A version-one symbol block with three counted maps: prototypes, functions,
   then expressions. Each map entry is a NUL-terminated identifier and a framed
   version-one signature/local-type record. Expression names include `#`.
5. A version-one DAT block: count, then NUL-terminated record names and framed
   version-one records.
6. The root footer. Every block footer is the pair `0, 0xFFFFFFFF`.

The parser bounds every read by its enclosing block, validates sizes, supported
versions, terminators, counts, identifier forms, duplicates and exact table/file
consumption. Unknown or damaged tables do not become an empty ownership set.
It deliberately does not interpret executable instructions, local types, DAT
values or arbitrary strings. It is not a general bytecode validity checker.

`tests/fixtures/bcd-ownership` contains original synthetic GPL/DAT input and a
hex-encoded stock-compiler result. Compile in a disposable directory with
`Gplbcc.exe -in Fixture.gplproj -out Fixture.bcd -stdout`. The fixture proves
that an external function call is not claimed, while unused and used constants,
a function, an agent prototype and a DAT record are all indexed. The same reader
also indexed the six installed native BCD archives and selected Standard targets.

## Manager behavior

The existing snapshot already reads target bytes for fingerprinting; retain
those bytes and lazily index them only when composition asks about a definition.
Reuse each target index across the original and expansion passes. Selection and
conflict-preview updates perform no BCD indexing, compiler invocation or extra
filesystem traversal.

Look for the native winner in reverse selected-package and GPL-target order,
within the stock first-Dataset scope. A later known winner makes an earlier
opaque target irrelevant. Once an actual winning definition is found:

- If it has matching declared source, verify only that target against the
  compiler, then use the existing source reconciliation.
- If source is absent or incomplete, report that exact definition, provider and
  target as requiring source for combination. This is not a claim that the
  gameplay changes are inherently incompatible.
- If it is absent, continue to the earlier provider or stock unchanged.

Participant registrations use the same effective ownership check, so a later
compiled-only target cannot silently replace a registered tree. No mod IDs,
function-name exceptions, dummy resources or new mod-side metadata are involved.
Static format and isolated composition checks do not constitute in-game acceptance.
