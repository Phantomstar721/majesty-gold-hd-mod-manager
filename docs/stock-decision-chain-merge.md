# Stock decision-chain source reconciliation

Implemented 2026-09-27 following approval for generic source-level priority
reconciliation. This changes Prepare's source comparison, not the game's AI
scheduler, native mod order or runtime DLL.

## Stock mechanism and lifecycle

Reference: the installed `SDK/OriginalQuests/GPL/DecisionTrees` and
`GPLMx/DecisionTrees` trees, including the original and expansion stock
`Priestess_tree` definitions. They express an ordered decision list as literal
nested `if` statements. An action query must return false before the next query
executes. If a query succeeds, the remaining checks and final fallback are
skipped. These calls are not independent predicates which can be sorted freely.

The stock function's initial thought/intent work executes before that chain.
Its terminal body sets the fallback intent, unit counter and active script only
after every check fails. Action queries and the existing active-script system
continue to own action selection, timing, state changes, cancellation and cleanup.
The transformation preserves the prefix and terminal body through the existing
instruction merger; it adds no callback service, per-unit data, timer, UI update,
watcher or runtime cleanup. Compiled output uses the same native conditional
instructions as ordinary authored GPL.

This common language transformation serves Steam public 1.5.2.24, Steam beta2
1.5.2.28 and GOG 1.5.2.28 without executable-specific branches or new addresses.
The original/expansion source comparison is exercised against installed Steam
and GOG SDK trees and stock compilers in disposable, single-function fixtures.
The native BCD loading boundary is documented in [the all-version audit](stock-bcd-ownership.md).
These source/compiler checks are not an in-game acceptance claim.

## Identity, order and ambiguity

Previously, adding a guard changed every deeper node's nesting depth. The
structural merger could compare a library query to a rest query and incorrectly
report competing edits to one condition. The correction is bounded to contiguous
no-else guard chains requiring realignment. Existing same-depth condition and
body edits keep their existing merge path.

1. Extract ordered condition heads and the terminal body without modifying them.
2. Identify unique, exactly matching stock conditions across each side, regardless
   of position. Match a changed condition only when a single original and single
   replacement occupy the same gap between known stock anchors. Predicate tokens
   remain atomic; no inference of equivalent calls or argument meanings is made.
3. Require every stock identity to remain identifiable exactly once. Removals,
   repeated checks and ambiguous multi-check replacements are not resolved by
   this alignment path.
4. Retain the sole explicit change to the stock order. Multiple identical changed
   orders agree; different changed orders require a conflict decision. No mod
   name, input order or arbitrary topological sort supplies priority.
5. Merge independent condition replacements by identity. Apply an inserted run
   only when its surrounding stock identities remain adjacent in the chosen
   order. Identical runs in the same gap are emitted once; different runs in the
   same gap, moved-apart boundaries and duplicated final conditions are rejected.
6. Merge the original terminal body with the existing instruction rules, then
   reconstruct literal nested `if` nodes. Parse the rendered function again and
   require an exact structural round-trip before stock compilation.

Unsupported alignment is reported as unresolved, not as proof that the mods'
gameplay could never be made compatible. General statement movement, `else`
ownership, loop ownership and unresolved instruction conflicts retain their
existing protections. There are no mod IDs or gameplay callback exceptions.

## Equivalent return/else layouts

The original and expansion stock `Potion_Check` functions in
`DecisionTrees/Modules/Purchase_Equipment.gpl` and `mx_Purchase_Equipment.gpl`
provide the reference. They reject a full inventory or insufficient funds,
filter the supplied shop list, then return false when no candidate remains.
Their `else` performs the intelligence roll and, on success, sets the visiting
task, target and purchasing intent before returning true. Otherwise the function
returns false. Existing task scripts still own travel, purchasing, timing,
cancellation and cleanup; this source comparison adds no runtime lifecycle.

Writing that `else` immediately after the returning branch changes no execution
path: a rejected candidate exits the function before the following code. The
merger aligns those two layouts only when a unique, identical condition exists
at the same lexical scope in every input, its true branch ends in a direct
`return` in every input, and the inputs actually differ in `else` layout. The
condition, true-branch instructions, return expression, false-path instructions
and their order remain intact. Ordinary instruction merging then resolves edits
within those equivalent paths. An actual deletion competing with an edit is
still a conflict, as are incompatible return values or ambiguous instruction
anchors. Removal or conditionalization of the terminating return alongside the
layout change is a conflict; calls, loops, `break` and nested conditional returns are not assumed
to terminate the function. Nothing moves across an enclosing loop or branch.

The reference functions and isolated compilation fixtures cover the installed
Steam and GOG SDKs, original and expansion datasets, using the same GPL language
mechanism on all three supported executable profiles. These fixtures do not
prepare a user profile or claim in-game acceptance.

## Dataset ancestry and cost

Source-backed Standard definitions are authored inputs too. Their reconciliation
with Merge sources now uses the same common SDK source ancestor as Merge-to-Merge
comparison. A base quest's native stock function may omit expansion-era checks;
that does not make it the ancestor from which those authored functions were
written. Native fallback lookup and dependency availability remain scoped to the
actual quest type. Stock-valued copies yield to the eligible native mod, and
comparison ancestors are not emitted as fallback content.

The code runs only during divergent function reconciliation, with bounded source
nesting and existing input snapshots. It adds no discovery work, extra directory
scan, compiler proof pass, runtime computation or persistent cache. Plan schema
13 invalidates pre-correction preparation results.
