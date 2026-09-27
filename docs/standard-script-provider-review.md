# Standard script preservation: pre-release review

Reviewed 2026-09-27 against checkpoint `e4ed3ec` and the uncommitted provider
prototype. This is an internal engineering review, not a release announcement.
The canonical test executable has not been rebuilt with this prototype.

## Conclusion

The existing problem is real: a load-last generated script can overwrite an
earlier Standard mod's replacement of the same function. Source-aware
reconciliation is useful generically; adding a separate option for every potion,
hero tree, or other behavior is not necessary to solve that source overlap.

The current prototype is not suitable to ship. It also does not solve the
reported expansion-scoped case through the production path. Recommending a
companion Mod before evaluating the native scope boundary and integration costs
was premature. Neither a companion nor a new runtime loader is selected.

## Confirmed findings

### 1. Selection changes leave stale script inputs — high severity

`manager/controller.py::_refresh_standard_plan` replaces Standard IDs and issues,
but not the new provider entries, signature, or prepared fingerprint. Standard
checkboxes and conflict-winner changes use this fast path.

Calling the actual method with in-memory catalog/plan objects reproduced both:

- Deselecting a provider removes its active ID but retains its script entry.
- Selecting a provider adds its active ID but leaves script entries empty.

The pre-publication check hashes `plan.standard_script_entries`, so checking the
same stale entries again does not detect this inconsistency. Consequences include
overwriting a newly selected provider, retaining a deselected provider's scripts,
or composing with a different winner than the game's active order.

Required correction: make script inputs and their identity follow the same
effective Standard selection/order on every plan-update path, while retaining
the existing cheap selection refresh for unaffected mods.

### 2. Standard reconciliation runs after relevant checks — high severity

`compose.py::prepare_final_gpl_resources` calls `standard_scripts.preserve` after
`merge_gpl_resources` has completed callback integration, spell/source-context
discovery, private activity-text auditing, pruning, and dataset dependency closure.
Standard definitions can consequently change the code those operations examined.
The full set of operations is not repeated on the final reconciled functions.

Required correction: make effective Standard definitions available before the
relevant existing transformations and validate the actual final output. Reuse
one composition pipeline, rather than adding a second late merge pipeline.
Syntactically independent edits alone do not prove gameplay compatibility.

### 3. Dataset scope is unresolved — high severity

The production function rejects every provider containing a non-`Any` GPL load,
before determining overlap. The installed expansion-only source fixture therefore
cannot use this prototype in normal Prepare. Its low-level potion fixture test
filters inputs itself and calls `preserve`, bypassing that production rejection.

Native executable inspection confirms that scope is functional, not a display
label. The active resource collector includes a Mod only when its base type
matches the requested quest type or is `Any`. The Mod type reader consults
Dataset index zero. In beta2 the source-resource reader also selects Dataset zero;
additional Dataset siblings are not an established conditional loading solution.

Verified native reference points (RVAs; image base `0x400000`):

| Executable | Mod type wrapper | Dataset/base reader | Resource-filter first type call |
| --- | --- | --- | --- |
| Steam beta2, timestamp `5A8A11D5` | `135BB0` | `0FA050` | `13A8E0` |
| Steam public, timestamp `5897B72F` | `1212F0` | `0F7EA0` | `126020` |
| GOG, timestamp `5BBB8DB8` | `135140` | `0FA6B0` | `139BE0` |

Each filter compares the requested type, then `Any` (`0x20594E41`), before
collecting resources. Beta2's source-resource reader is RVA `0FF140`, with the
Dataset-zero lookup at `0FF1A7`/`0FF1A9`. This is static evidence, not an in-game
acceptance test or a complete new-loading-mechanism audit.

Reference executable SHA-256 values used during inspection:

- Beta2 installed (locally patched): `e15cf0d8b6150f1b60ae6dce9f7cafae920d231b5c7aeac1d2f4be9c2519030b`
- Public local fixture: `d21ba8312433e3e8f784b71943bdc38ddde7590e57abfb29ef347330cc77612d`
- GOG pristine fixture: `65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792`

Do not flatten expansion-only behavior into `Any`. The existing dataset
dependency closure supplies missing helpers; it does not select quest-specific
versions of shared functions. Separate native Mod identities would preserve the
filter boundary but require selection/order and save-identity handling. A single
identity with custom runtime dispatch is not an existing proven substitute. The
full lifecycle and cost of a scoped output must be evaluated before choosing it.

### 4. Avoidable input work and overly broad rejection — medium severity

A measured cold read of the installed large Standard script fixture took about
0.50 seconds, parsed its manifest four times, collected 79 input paths, and read
583 definitions. A fresh source/bytecode compiler proof took about 1.94 seconds.
Warm calls were approximately 0.002 seconds each. These are single local
measurements, not performance guarantees; the caches are process-local.

`create_build_plan` reads all selected Standard inputs whenever Merge content is
prepared, before establishing relevant overlap. `read` reloads the package in
both the cache input supplier and value loader. Existing catalog symbol evidence
is not used to narrow this work. Source recovery can recursively search for
project files, increasing the cost when explicit manifest sources are missing.

`preserve` also requests verification of compiled-only providers before knowing
whether they overlap any generated definition. Unknown overlap is not a proven
conflict. Safety must remain conservative, but diagnosis must distinguish missing
evidence from confirmed competing edits and avoid unrelated work where overlap
can be ruled out using existing evidence.

Required correction: reuse scan-cached package/symbol evidence; load once; prove
only relevant inputs; keep exact invalidation when selections or files change.
Do not remove source/bytecode verification merely to make a benchmark faster.

### 5. Unnecessary output and incomplete coverage — medium severity

When generated code is identical to the native winner, `preserve` still emits it.
It also emits the native winner when the generated definition was merely a stock
fallback. This unnecessarily expands the generated profile's ownership. Omit
redundant definitions where the audited load/link lifecycle permits it; retain
only what actual Manager transformations and dependencies require.

The draft tests exercise isolated reconciliation and compiler filename proof.
They do not establish production selection refresh, scope-correct loading,
cross-quest transitions, or final callback integration. Some assertions codify
current limitations (blanket scoped rejection and redundant native emission).

## Minimum justified direction

1. Keep Standard mods independently loadable. Their existing manifest Source and
   Target declarations already identify editable scripts; no new copy of the
   original mod or per-function registration list is needed for those inputs.
2. Reuse the existing effective native order, cached symbol evidence, source
   parsing, and instruction merger. Load only potentially affected providers.
3. Reconcile before dependent transformations, preserving the native winner and
   adding only required Manager changes. Report irreconcilable edits precisely.
4. Resolve scoped output only after proving its complete native lifecycle and
   evaluating save identities. Do not build both alternatives speculatively.
5. Cover selection/deselection/order changes, matching and missing source,
   base/expansion behavior, final hook checks, and cold/warm cost. Verify each
   supported executable; distinguish static evidence from user playtesting.

This review does not approve a companion Mod, runtime polling, per-unit state,
or separate potion/death/healing compatibility frameworks.

## Follow-up corrections, 2026-09-27

The findings above describe the original prototype. The subsequent user-requested
source corrections are:

- Standard selection, deselection, conflict winners and order now update provider
  entries, signature and the combined fingerprint using the cached Merge identity.
  Publication also rejects inconsistent active/provider ID lists explicitly.
- Native scripts enter `merge_gpl_resources` before callback transformations,
  discovery and final auditing. Effective native fallbacks are supplied to feature
  code; there is no post-validation `preserve` pass. Stock anchors remain stock
  evidence, rather than substituting native overrides as proof of stock behavior.
- Shared parsing is reused between catalog and composition. A selection snapshot
  loads each manifest once, hashes declared files, and does not parse source or
  run the compiler. This integration does not recursively discover projects.
  The same local fixture measured 0.0421 s cold and 0.0023 s warm, versus roughly
  0.50 s cold before. Compiler proof is still required when native code is used;
  no claim is made that this necessary first-use cost disappeared.
- Unchanged native definitions are pruned; dependency closure consults native
  providers before importing an expansion helper. Scoped providers are rejected
  only when an affected symbol actually requires different outputs. Merely
  selecting an unrelated scoped provider no longer rejects the build.
- Compiled-only inputs are not rejected up front. Unknown ownership is still a
  safety limitation when a generated definition may overlap: the error identifies
  the symbol and requests matching manifest sources. No unverified binary decoder
  or assumption that source-less bytecode is harmless was added.
- Source enumeration now follows native Dataset zero; ignored sibling Datasets
  do not create false inputs or missing-file requirements.
- Coverage now exercises the real controller refresh, source mutation and parser
  call count, pipeline ordering, private hero participant callbacks, required
  bytecode proof, duplicate pruning, and dataset-aware dependency behavior.
  The installed potion-source fixture goes through `prepare_final_gpl_resources`,
  explicitly checking the unresolved `Any` restriction and a separate expansion
  script composition. This does not build or publish a user profile.

This checkpoint preceded scoped publication. The subsequent user-authorized
[scope implementation](mod-dataset-scope-plan.md) supersedes that boundary; its
implementation notes distinguish source/fixture verification from the remaining
in-game acceptance.
