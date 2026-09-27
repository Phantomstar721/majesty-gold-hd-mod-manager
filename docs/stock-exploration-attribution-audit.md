# Persistent exploration attribution: native audit

2026-09-23 audit, extended 2026-09-25. Conditionally approved instrumentation
is implemented for default Steam, Steam beta2 and GOG. The original trace below
uses beta2 VAs; the cross-build section records the independently mapped RVAs.
Unknown or modified hook bodies fail closed. Live acceptance is a separate step.

## Stock reveal and attribution

`4EF47D..4EF482` installs unit callback `4470E0` through `5D7300`.
Coordinate update `5D6DF0` calls it with the actual unit at `5D6E27..5D6E2E`
after stock parent/flags checks and notifications. The callback retains EDI,
applies stock visibility/Description gates, computes center/radius through
`446FA0`, then resolves owner/shared mask at `447158..44718B`.

`4471A0` calls `5D9ED0(map, center, mask, radius)`. Its bounded circle reads
map+54 tiles, map+40 stride, 24-byte records, explored mask at tile+4.
The eight bytes at `5D9FFD` load old mask into ECX/EAX and OR the native mask
from `[esp+44h]`. The trampoline replays these instructions and preserves
registers. Original CMP at `5DA005` restores flags before the original write.
Dirty queuing `5DA00B..5DA051`, including bit31, remains unchanged.

The call-site wrapper supplies scoped thread-local context. Count only the
source owner's persistent bit changing 0 to 1; overlap follows stock execution
order, and sharing recipients earn no duplicate count. Context restoration
uses RAII. No GPL or heap allocation occurs inside the tile callback.
Direct callers `433458` (RevealArea), `5D72F0`, `5DB19D`, `6282B9`, and
whole-map reveal have no attributed source context. No second scan occurs.

## Recruitment and teleport

TeleportToPoint/TeleportToUnit resolve to `433170` / `4334D0`. Successful
placement calls `5D7520` at `4332F0` / `4336D0`, then `5D7460`, whose unit
virtual+9C at `5D74E8` reaches `5D6DF0`. Destination reveal is counted, not
intervening terrain. Private movement bypassing this path is not certified.

Recruitment `44DC90` creates through world virtual+64 at `44DDF6`, places at
`44DF27`, then invokes birth GPL at `44DF53..44DF6A`. Birth-only registration
would miss first reveal. However world construction `5B6950 -> virtual+68 ->
5B6810` calls unit virtual+10 at `5B691A` before returning the new unit.
That resolves to `5CF670 -> 55D410`: GPL agent creation `575170`, native
identity binding `575490` / `575420`, AE installation at `55D51D`.
Thus Manager bookkeeping can run after placement reveal, before birth;
consumer delivery waits until after the enclosing native update and birth.

## Persistence, ownership and cleanup

Source pending count, owner, queued flag and epoch use normal saved GPL
attributes; the root dirty list holds GPL references, not retained C++ pointers.
`IsValidGamePiece` (`5D3890 -> 56ED30`) resolves references against the live
registry and rejects deleted agents. Unit destruction `5CF4D0` marks deletion,
calls `5CF6C0 -> 55D580 -> 574A40`, then clears AE. Invalid entries are dropped.

Native setter `5CF320` compares/writes unit+80 then calls virtual+B8.
Gameplay SetUnitPlayerNumber (`432F00`) calls virtual+20 at `433030`.
All nine original setter virtual slots are wrapped; the existing building
research wrapper delegates invalidation before stock notifications. Direct
constructor call `442DA0` precedes agent binding. Owner changes clear pending
count and increment a saved epoch, so consumers can discard partial credit
even after A-to-B-to-A. Invalidation permits dispatcher existing-world states
3/7/8, including transfers outside the enclosing observation frame.

Dispatch detaches and snapshots the complete batch before any consumer runs.
Reward-triggered range increases enqueue a subsequent batch. Each consumer
entry rechecks source validity, owner and epoch. Integer overflow fails
explicitly. Consumers must remain synchronous and must not save or load.

## Reconstruction and shared hooks

`4261F0` applies pending state at `426200..426209`. State2 calls `42AAB0`
at `426234`; state3 calls `4278A0` at `42623D`. Loaded install `425C90`
schedules initialization; new and restored branches finalize at `42ACA8`
and request state3 at `42ACCC`. World-ready and update hooks are shared with
existing adapters, installed once. World-ready only sets a pending-check hint.

Counting requires state3, the enclosing native update, the current world and
a bound live agent. Initial preplaced terrain is baseline, not earned credit.
Serialization depth wraps central reader `5EC5D0` at all direct callers:
`5EC655`, `5C113B`, `5C1285` (including incremental reads). Saving also does
pointer conversion, so stream writer `5EBF70` is wrapped at vtable slots
`754434` and `762EFC`. Both counting and owner invalidation are suppressed
inside these RAII scopes. Metadata reads cannot leave a permanent gate closed.
State4/5 teardown clears the registry at `428E2E` and world at `428E5E`;
no native source pointer is retained across it.

## Verification and remaining acceptance

The installer validates executable, body hashes, exact displaced bytes,
evaluator calls and virtual targets. Generated GPL service bodies and single
definitions are validated; language fixtures compile with the stock compiler.
The GPL harness exercises pending/delivered state, ownership epochs, nested
reveal, invalid sources and overflow. Its saved-state clone is **not** a native
save-file round-trip test.

`Build-Runtime.ps1 -ExplorationTests` executes the actual x86 trampoline on
synthetic masks and checks register preservation, owner-bit counting, inactive
thread context and preservation of the original write boundary. A local
synthetic measurement was about 1.8 ns inactive / 5.1 ns observed per call.
This excludes GPL and stock work; it is not an in-game performance guarantee.

Live acceptance remains: fresh recruitment, teleport/revisits/shared vision,
reward-triggered sight expansion, repeated native save/load, ownership round
trips and active-game overhead. Repeat these checks for each supported build;
the default Steam/GOG port has not yet received an in-game acceptance run.

The discarded Begin/Count/End proposal is not exported. See the implemented
[event and package contract](source-exploration-events.md).

## First live failure: incorrect GPL arithmetic bound

The 2026-09-23 20:22:00 runtime trace resolved `MM_EO_Record` and returned
integer -2 for agent 6 / unit 23119, owner 0, 17 tiles. This is its explicit
overflow branch, not missing callback registration or failed native install.
The generated guard incorrectly used `2147483647 - Pending`. As already
documented in the kingdom-research audit, `GplInteger` binary operators use
signed fixed point with ten fractional bits: that bound converts to -1.
The first positive tile count therefore trips the guard even at Pending=0.

The service now bounds pending counts and epochs at 2097151, the positive
expression maximum. Native reveal input rejects larger values before GPL
conversion. A regression models the traced stock subtraction/comparison,
reproduces the original 17-tile failure, checks the corrected boundary, and
rejects oversized numeric literals in the generated service. The ordinary
Python GPL harness alone did not catch this because it uses Python arithmetic.
Users must regenerate their prepared GPL package with the corrected Manager;
replacing only the runtime DLL cannot change the faulty generated expression.

## Default Steam and GOG port (2026-09-25)

`runtime/ExplorationProfiles.h` is the canonical per-build evidence table.
All addresses in this table are RVAs, relative to image base `00400000`.

| Boundary | Default Steam | Steam beta2 | GOG |
| --- | --- | --- | --- |
| PE timestamp | `5897B72F` | `5A8A11D5` | `5BBB8DB8` |
| Source callback | `461D0` | `470E0` | `47000` |
| Native circle reveal | `1C4CF0` | `1D9ED0` | `1D9220` |
| Central reader | `1D72D0` | `1EC5D0` | `1EB920` |
| Stream writer | `1D6D90` | `1EBF70` | `1EB2C0` |
| Owner setter | `1BA380` | `1CF320` | `1CE670` |
| Agent binding | `148B10` | `15D410` | `15C710` |
| Game singleton getter | `25D00` | `26CD0` | `25F60` |
| Game singleton pointer | `3C0ABC` | `3DF574` | `3DF814` |
| World-root pointer | `3C544C` | `3E3FD4` | `3E426C` |
| State-2 call / initializer | `25264` / `28C20` | `26234` / `2AAB0` | `254C4` / `29CF0` |

Source callback, circle reveal, central reader, owner setter, and agent-binding
bodies match instruction-for-instruction after masking address operands. EDI
still holds the source, the reveal call remains at callback+`C0`, and the
14-byte tile write boundary at reveal+`12D` is identical. The displaced eight
bytes resume at +`135`; stack arguments, source fields and owner bit semantics
do not vary. No per-tile profile search is introduced.

RTTI identifies `GS_MapIOManager` and `GE_MapIOManager` writer virtuals at +8
in each build. GOG's writer matches beta2 structurally. Default Steam's writer
is 0x64 bytes rather than 0x62: its stream virtual is +20 rather than +24,
and the null-stream branch has its own epilogue. Both branches return an
integer and `ret 8`; the same chunk loop and two caller arguments are retained.
The wrapper calls the complete build-specific writer once; it does not copy
the differing internal virtual dispatch. This preserves pointer conversion,
early exits, errors, and depth cleanup. All three direct central-reader calls
and all nine owner-setter virtual slots were enumerated per executable.

The main-loop getter returns the singleton passed in ECX to each state
dispatcher. State lives at +0; dispatcher states 3/7/8 use existing-world
updates. Each state-2 initializer uses root+10 for the world, finalizes both
world containers through their native virtuals, clears +54 and requests state3
before returning. Default Steam has a larger initialization body (including
its multiplayer wait), so it is not treated as a relocated beta2 function.
The hook stays at the dispatcher call and runs only after the entire stock
initializer returns. Kingdom-research visual traversal never runs solely because
exploration is selected. Its [subsequent parity port](runtime-feature-parity.md)
preserves this shared hook on all three builds.

Installation checks exact FNV body hashes for all six observation routines
and the singleton getter, global-load operands, tile bytes, the source/read
calls, evaluator lifecycle calls, and original owner/writer virtual targets.
The shared world-ready adapter checks its per-build call target before patching.
The existing profiled update hook owns delivery timing. Python preflight,
composition and launch accept only identified supported PE profiles; unrelated
feature-specific guards remain independent of exploration selection.

Reproduce read-only evidence validation with
`tests/test_exploration_profiles.py`, setting
`MAJESTY_EXPLORATION_PUBLIC_EXE`, `MAJESTY_EXPLORATION_BETA2_EXE`, and
`MAJESTY_EXPLORATION_GOG_EXE` to the three executables. It checks the production
profile constants against actual PE bytes without loading or editing the game.
The local public support-test executable includes existing QOL patches and a
private Documents-folder literal; the verified observation bodies are not
those patched sites. Native trampoline fixtures and saved-GPL accounting
fixtures are also retained. Neither fixture substitutes for the native
save/load, ownership, teleport and recruitment acceptance run.
