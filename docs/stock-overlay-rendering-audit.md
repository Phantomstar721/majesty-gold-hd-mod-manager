# Stock attached-overlay rendering audit

## Scope and authority

Static trace of Steam beta2 MajestyHD.exe, PE timestamp `0x5A8A11D5`, image base
`0x00400000`. Addresses below are virtual addresses for that executable, not
portable hook sites. This audit adds no hook or runtime behavior.

Resource authority is `SDK/OriginalQuests/Data/M_Overlays.xml` entry
`super_charge_effector`, and `Data/maindata.cam` IMAG `WRF1super_charge_e`.
The stock IMAG is 604 bytes, SHA-256
`57fb612a14df922fab9633edca411a7c51d23e7ba84ef34fd3b381a44f5e7bb7`.
Do not infer rendering flags from a preview decoder that only extracts pixels.

## Ownership and visual attachment are different

`0x005DE840` creates the child. At `0x005DE908..0x005DE912` it inserts it
into the parent's `+0xA4` attached-object container through `0x005BE330`.
The child stores the parent unit ID at `+0x84`. Stock Check/GetEffector and
attached-object destruction continue to own lookup and cleanup; see the
[research lifecycle audit](stock-kingdom-research-audit.md).

Creation then calls virtual `+0x128`, `0x005DE610`, with attachment ID zero
and no explicit position. In the Overlay branch (`0x005DE6A7..0x005DE6D2`),
zero selects the descriptor's `OverlayDesc_Engine+0xA0`; that field defaults
to zero (`0x0061ED03`). If still zero, native code substitutes **1**.

For a normal 2D parent, the image layer's 3D-object query returns null and
`0x005DE6EF` branches to the stock attachment lookup at `0x005DE65F`.
The parent's virtual `+0xDC`, `0x005DC430`, reads IMAG **set 400** (`0x190`),
direction zero. Attachment ID 1 selects point zero through `0x00699000`:
the first rectangle's left/top pair. Point five supplies the ground-projection
reference. `0x005DC521..0x005DC5B5` converts these image coordinates into a
world offset with the stock camera projection and adds the parent position.
This metadata is distinct from the body's TILE hotspot and frame offsets.

`0x005DE750..0x005DE780` subtracts the parent's world origin, preserves the
stock one-fixed-point-unit depth bias, and stores the child's relative position
through `0x005D7580`. Subsequent parent-relative position reads use that offset.
The 3D-object branch instead uses the parent origin; missing attachment metadata
uses the stock fallback. Neither exception makes the normal 2D path root-based.

Author an effect's registration relative to the actual attachment, not merely
the center of its source sheet or the body's TILE origin. Retain native
projection/rounding and lifecycle; no positioning watcher is needed.

## One clock, two streams, explicit visibility

WRF1 set 64 has one direction, 30 frames and two streams. The direction has
zero X/Y offsets; all 60 frame-offset pairs are zero. Set flags are `0x100`.

The world renderer loads the image layer's current frame at `0x005E9582` and
keeps it at stack `+0x94`. Each stream uses that same saved frame
(`0x005E95B3..0x005E95C1`). Lookup `0x006A77F0` computes
`table + 8 * (stream * frame_count + frame)`. The loop increments only the
stream index (`0x005E9892..0x005E98A5`), not a second animation clock.

| Full reference bit | High-half value | Native meaning |
| --- | --- | --- |
| `0x20000000` | `0x2000` | Requested horizontal orientation; calls `0x00649F90`. |
| `0x40000000` | `0x4000` | Hidden stream/frame; skip this draw. **Not vertical flip.** |

The hide branch is `0x005E95C3..0x005E95D0 -> 0x005E9892`.
The horizontal-orientation call is `0x005E9774..0x005E9782`.
Bounds calculation also honors these flags (`0x00622290`).

Stock stream zero is visible for all 30 frames. Stream one is hidden for
zero-based frames 0 through 6; frame 7 requests horizontal flip, frame 8 does
not, and frames 9 through 29 request horizontal flip. Splitting an authored
complete picture between both streams therefore removes part of that picture
during the hidden frames. Preserve the IMAG visibility/playback structure and
author appropriate payloads. For a single complete animation, the always-visible
stream can carry it and the companion stream can contain transparent payloads.
Do not remove native hide flags as a generic merge correction.

## Stock frame advancement and timing

### Select the correct native path

The native subtype catalog registers **Overlay = 4** at
`0x005B51A2..0x005B51BE` and **ParticleSystem = 5** at
`0x005B51D0..0x005B51EC`. Do not mistake the type-5 branches for ordinary
overlays: `0x005DD667..0x005DD6BA` constructs a separate particle animator
only for ParticleSystem, and `0x006227F5..0x006227FF` skips ordinary
OrderAnimate startup only for that subtype. WRF1 follows the type-4 path.

For `CreateEffector(..., 1, "Infinite")`, the GPL wrapper `0x005D4610`
passes the duration and infinite-lifetime flag to native creation
`0x005DE840`; these arguments are not a frame interval. After attaching the
child, creation calls `0x006227F0`. That helper tries birth set 80, then active
set 64. WRF1 has only set 64, so it selects that set through `0x005D14F0`
and starts `OrderAnimate` through `0x005D1370`, order-processor virtual
`+0x18` (`0x005D1250`). The same path starts the finite-duration stock spell.

Set selection initializes the image part's frame to zero
(`0x005DDBB9`). The normal order builder installs frame step **+1** at
`0x005D12FB`, with order flags `0x50` (advance frame and loop) and no finite
repeat count for the active-set call. Order flags and IMAG set flags are
different fields: IMAG **`0x100` selects the first image-part layer**
(`0x005DD9C0`, `0x005DDB80..0x005DDB8D`), not ping-pong, random playback,
or a frame interval. The two WRF1 streams belong to that same image part.

### Sequence, loop and holds

`OrderAnimate::Execute` (`0x005D0F60`) reads the current frame from
`part+0x24`, adds `order+0x44`, and subtracts the frame count at the upper
boundary (`0x005D10CF..0x005D1112`). Thus WRF1 plays:

`0, 1, 2, ... 28, 29, 0, 1, ...`

The generic order can execute an explicitly negative step, but neither its
normal builder nor this creation path supplies one. There is no automatic
reversal, random frame choice, endpoint duplication, or ping-pong branch on
this path. Frame-marker handling can notify a callback but does not change
the step or add a hold; WRF1's frame-offset/marker words are all zero, and
the active-set startup supplies no animation callback.

### Cadence is simulation-time based

The order builder obtains its interval through the created unit's virtual
`+0x154` (`0x00448990`), which calls `0x005CF110`. That getter uses
`IMAG set -> timing record -> +0x08` when nonzero, otherwise **100 ms**.
WRF1's version-4 set timing fields at whole-file offsets
`0x34..0x44` are all zero. The set loader (`0x00699AA0`,
`0x006988E0`) therefore leaves the timing record null. There is also no
direction timing record (`u16` at `0x74` is zero). The native result is
the **100 simulation-ms default**, not an authored per-frame speed table.

`0x00448990` adjusts this interval to the simulation tick `T` read from
`[0x007E3E58]+0x20`: when `100 >= T`, it rounds to the nearest tick using
`floor((100 + floor(T/2)) / T) * T`; otherwise it leaves 100 unchanged.
The result is clamped to at least 1. Consequently 10 frames/second and a
3-second 30-frame loop are nominal values, not a promise of exact wall-clock
timing. For example, a 40-ms simulation tick gives a 120-ms interval.

Enqueue `0x006138F0` initializes the order's start/delay. The scheduler
`0x00612200` dispatches it once when the simulation clock's unsigned elapsed
time reaches that delay. After one frame step, `0x005D11EF..0x005D11FC`
resets the start to the current clock and reuses the same interval. It does
not catch up by skipping several frame indices. Late dispatch can prolong
a displayed frame, and rendering need not show every simulation update;
neither behavior reverses the native sequence. Clock `0x007E3FDC` advances
by the simulation tick in the running-state branch at
`0x00427A4D..0x00427A68`, rather than independently following display refresh.

An authored loop should therefore have coherent forward phases and a clean
29-to-0 seam at this relatively low cadence. Apparent rotation reversal can
still come from the authored phases or perceptual aliasing of repeated shapes;
this static trace does not establish which explains a particular playtest.
It supplies no basis for a renderer patch, a second timer, or clearing stock
flags. No live frame trace or new artwork acceptance is claimed here.

## TILE header and horizontal registration

The version-3 TILE loader at `0x006AC160` reads a 26-byte header. Relevant fields:

| On-disk offset | Native sprite field | Meaning on this path |
| --- | --- | --- |
| `+0x00` | `+0x08` | Storage type; 3 selects the row/run format. |
| `+0x02`, `+0x04` | `+0x0C`, `+0x10` | Height, width. |
| `+0x08` | `+0x14` | Rendering/storage flags, **not disposable metadata**. |
| `+0x0A`, `+0x0C` | `+0x18`, `+0x1C` | Signed X/Y hotspot. |
| `+0x0E` | `+0x20` | Default draw mode; the value 8 here is not pixel bit depth. |
| `+0x16` | Palette lookup argument | External palette ID when applicable. |

Header flag `0x20` selects the external-palette path when no embedded palette
is present (`0x006AC361..0x006AC3B3`). Low flag bits select indexed versus
other pixel encodings (`0x006ABD20`, `0x00649D9A`).

Flag **`0x10` records the payload's current horizontal orientation**.
`0x00649F90` compares this state with the requested IMAG orientation and only
flips when they differ. The version-3 flipper `0x00649D60` reverses each row,
toggles `0x10`, and assigns `hotspot_x = width - hotspot_x`
(`0x00649F1D..0x00649F29`). The Y hotspot is unchanged. Pixel coordinates
reflect as `width - 1 - x`, but hotspot coordinates reflect as **`width - x`**.
Do not apply the pixel-index formula to the hotspot.

The renderer adds native direction/frame offsets and calls the blitter at
`0x005E9787..0x005E97DF`. Blitter `0x00649580` subtracts the resulting TILE
hotspot from the anchor (`0x006495B6..0x006495D3`), accounting for zoom.

Header bits **`0x1F00` carry a draw-mode parameter**, rather than independent
placement or mirror flags. Default-style setup at `0x006865DD..0x00686636`
reads TILE `+0x0E`. For mode 8 it extracts `(flags >> 8) & 0x1F` and subtracts
10 when that value is nonzero. Thus `0x0C30` supplies parameter 2 and
`0x0030` supplies parameter 0; both also carry the horizontal-state bit.
Mode 5 interprets the same field differently (subtract 1, clamp 0..8).
This trace establishes dispatch and parameter values, not a universal visual
name such as "shadow" or "compression" for those bits.

When encoding entirely new ordinary indexed rows, write a coherent header for
those rows and the intended rendering mode; do not copy frame-dependent
`0x30`/`0x0C30` values from unrelated stock pixels. For a baseline `0x20`
header and an IMAG frame requesting horizontal flip, pre-mirroring new art
requires the native hotspot reflection `width - hotspot_x` if the intended
on-screen orientation is to remain unchanged. Newly encoded art can instead
truthfully declare its stored orientation, but its pixels, hotspot and header
must agree. Stock headers remain valid for their original stock payloads.

## Manager boundary

`art._rewrite_parsed_imag_entries` changes only the low-16 TILE index and retains
`reference.flag_bits`. Palette relocation changes the TILE palette reference,
not its flags, hotspot, drawing mode or pixels. The active-effector descriptor
remains the stock clone. No defect in these relocation operations was identified
by this trace; globally clearing header or frame flags would damage valid art.

This corrects the former documentation claim that the default overlay is
visually root-attached. It does not change the descriptor contract, install a
renderer patch, or claim live visual acceptance of newly authored artwork.
