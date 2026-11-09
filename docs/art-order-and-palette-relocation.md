# Art directory order and final-payload allocation

Animation set directories preserve authored traversal order. Physical body
boundaries come from the next greater body offset, not the next directory row.
The custom and stock frame readers and both set splitters use this rule.
Duplicate offsets, directory overlap and out-of-record offsets remain errors.
No directory rows or frame references are reordered during parsing.

TILE allocation must follow SPLT allocation and reference rewriting. Two TILE
payloads may compare equal before their external palette IDs are rewritten but
compare unequal afterward. Sharing their original slot would then produce an
unresolved placement collision. Allocation now compares the finalized TILE
payloads before rewriting IMAG references, retaining the existing reference
proof and low-16 capacity checks. This is independent of mod identity and of
the game's executable profile; no native runtime changes are involved.

Regression fixtures cover reordered sets, duplicate-offset rejection, initially
identical tiles with divergent palettes in both owner orders, and sparse
ID-keyed TILE/SPLT slot 20000 beside a prefix provider. The installed MK test
CAM, Menagerie, and installed guild CAMs were also exercised in memory in both
owner orders without creating or updating a merged package.

Limit: the current installed MK/Menagerie pair did not reproduce the author's
reported slot-0 error even before the change. The final-payload allocation flaw
is independently reproduced by the synthetic fixture; it is not established as
the cause of that specific report. No in-game acceptance or release packaging
is claimed here.
