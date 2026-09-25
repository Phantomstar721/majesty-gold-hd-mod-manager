# Original-game and expansion GPL dependencies

## Art availability across datasets

The same availability rule applies to packaged art: an explicit IMAG record
absent from the base art ancestor must survive stock-relative pruning even if
it is identical to expansion stock. Original quests cannot inherit it from an
unloaded expansion archive. Sparse component analysis and final composition
both retain such records, using the existing typed TILE/palette dependency
relocation. This preserves menu icons and world frames without a per-building
exception. Base-present unchanged art remains eligible for ordinary pruning.

## Stock lifecycle

`Data/MajestyDatasetDefinitions.xml` loads `Bytecode.bcd` followed by
`MX_Compatibility.bcd` for the original-game dataset. The expansion inherits
that dataset and additionally loads `MX_Build`, `MX_Data`, `MX_Decision`, and
`MX_Task`, in that order. Original quests do not load those four projects.

GPL expression references are runtime bindings, not constants automatically
inlined by the compiler. A replacement function compiled from expansion source
can therefore compile successfully but dereference a missing expression when
loaded into an original quest. A captured integer-comparison fault confirmed
this with an expansion-only item identifier following a stock item branch.

## Composition policy

The generated Any-dataset patch must not assume that expansion bytecode exists.
After final source selection, dependency checking uses the six installed stock
project declarations and their explicitly listed sources:

- Copy referenced, base-absent stock expression definitions exactly, closing
  their expression dependencies. Never substitute guessed numbers.
- Preserve base definitions and explicit selected-mod definitions. Do not copy
  unused expansion expressions or override original-game values with expansion
  values merely because those values occur later in the stock source tree.
- Reject cycles and expressions requiring function execution.
- Copy referenced, base-absent stock functions literally and transitively close
  their function and expression dependencies. This includes function references
  assigned as callbacks, not only immediate calls. Register each function once
  before following its references, so recursive helpers terminate the traversal.
- Never copy an expansion replacement for a name already provided by the base
  dataset or selected mods. Missing or mismatched stock source still fails
  preparation with the dependency identified.
- Ignore comments/string contents. Unknown external names are not classified
  as missing stock dependencies: native VM and quest bindings also exist.

This is a static safety boundary, not a proof of all possible dynamic script
behavior. It does not infer dependencies hidden in runtime strings or prove
that an explicitly supplied implementation is safe. Resource availability and
unit-prototype availability remain the caller's responsibility, just as for
existing mod functions. The linker does not invent substitute units, strip
branches, install expansion datasets, or start imported quest functions.

The check runs during final GPL preparation, not gameplay or catalog scanning.
It adds no hooks, polling, or quest changes. Parsing is content-cached, does not
invoke the compiler, and does not recursively discover unrelated files. All
project/source inputs participate in the build fingerprint. A bounded,
process-local cache reuses the stock snapshot and symbol catalog across
selection changes. Warm lookups inspect file identities, sizes, timestamps,
and directory ancestry without rereading source or rehashing payloads. The two
description directories also receive a shallow name-list check because Windows
can defer directory timestamp updates. Project
edits, added/removed description files, optional-file presence changes, and
source edits invalidate the snapshot. Link/junction boundaries are not cached;
inputs changing during a refresh are rejected. A rejected build
does not publish an incomplete replacement package.

## Stock helper lifecycle audit

GPL function loading registers a callable definition; execution happens only
when an existing script calls it or assigns it to a thread. Imports preserve
the entire body, arguments, return type, ordering, and callback assignments.
No per-unit state is added by the linker and it owns no cleanup or cancellation.

The reproduction's transitive closure contains thirteen missing functions and
twenty-one missing expressions. The relevant stock lifecycles are:

| Stock helper family | Dispatch and state ownership |
| --- | --- |
| Palace lookup | Synchronous list query; returns a palace or null. No persistent state or thread. |
| Bazaar lookup, research filter and buyer intent | Called by existing purchasing scripts; returns costs/task names/filtered lists or updates the buyer's intent. No new purchasing lifecycle is started by importing definitions. |
| Fire resistance | Called by damage handling; checks the attribute before reading it, performs stock random check, returns boolean. |
| Goblin fortress hit/spawn | The existing damage branch dispatches for the fortress. The helper consumes its stored spawns and calls the stock spawn routine. Counter ownership and monster-cap checks are unchanged. |
| Hall visit check | Searches for existing completed halls; only after finding a target sets the existing target, intent, and ActiveScript. Existing Use_Building owns travel and completion. |
| Hunter setup and quest event/victory helpers | Called/assigned by the selected quest entry point. Merely defining them does not launch a quest, create units, or schedule threads. Native quest state and original thread cleanup remain unchanged. |

The original selected definitions remain byte-for-byte unchanged by dependency
closure. Every added helper matches the effective installed stock source in
dataset load order. This fixes the previously reported missing-function
rejections without a mod-specific allowlist or a new runtime mechanism.
