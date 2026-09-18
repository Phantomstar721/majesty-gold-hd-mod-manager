# Contributing new runtime feature support

Most compatible mods should not need a DLL change. Majesty's CAM resources and
GPL scripts remain the first choice, followed by the reusable stock-behavior
features already supported by the Mod Manager. A mod package can use those
documented features by declaring their data; it does not need package-specific
code in the manager.

If a mod needs native behavior that the manager does not yet support, contribute
that behavior to the Mod Manager through a GitHub pull request. Once accepted,
it becomes a reusable feature that any compatible mod can declare. It must not
be tied to one Workshop item, mod UUID, building, or author.

## Use supported data-only recipes first

Schema-v3 packages place supported declarations in the top-level
`mod-definition.json` `runtime_features` array. The current parser accepts
exactly these feature types:

- `stock.name-generator.v1`;
- `stock.ap78-enchantment-row.v1`;
- `stock.ap10-ap69-secondary-panel.v1`;
- `stock.mx09-ap41-reward-panel.v1`;
- `stock.mx04-mx05-occupant-action-panel.v1`;
- `stock.mx22-building-open-toggle.v1`;
- `stock.hero-quest-lifecycle.v1`;
- `stock.gplmx-purchase-equipment-tail.v1`;
- `stock.gplmx-purchase-bazaar-tail.v1`;
- `stock.ap41-fl00-hostile-monster-flag.v1`;
- `stock.ap22-resource-meter.v1`;
- `stock.ap99-research-row.v1`;
- `stock.ap17-upgrade-research-gate.v1`;
- `stock.ap52-private-recruitment.v1` ([three-choice guild contract](stock-ap52-private-recruitment.md));
- `stock.ap24-timed-rage-action.v1`;
- `stock.ap24-rage-command-action.v1`; and
- `stock.ap69-sovereign-target-action.v1`.

The [Merge mod authoring guide](manager-merge-contract.md#supported-typed-runtime-features)
documents every exact field and relationship. The parser-checked
[complete schema-v3 example](examples/mod-definition-v3-all-features.json)
shows the placement of every recipe, including both `stock_target_mode` and
`stock_executor_mode`. Use only the records your package actually needs and
replace every illustrative package-owned ID with one proved by your shipped
CAM, Descriptions, panel controls, and GPL sources. Do not replace a field
named `*_template_control_id` with a private ID: those fields select bounded
stock Majesty descriptors, and the authoring guide lists the exact templates
and metadata accepted by each current recipe version.

For the current AP69 sovereign-target recipe, `stock_executor_mode` is exactly
the traced `Sp14` lifecycle. The complete case-sensitive `Sp**` namespace is
reserved for stock sovereign modes, so a package's `private_mode` must use a
different namespace. Supporting another stock executor family requires a
reviewed runtime-feature pull request with its stock lifecycle proof.

These declarations are bounded data, not code. The manager validates them,
resolves package-local logical keys and panel identities, rejects collisions,
and writes manager-owned MMFR/MMCR files. A Workshop package does not ship or
name those binary registries itself.

Version 3 also does not contain a custom-building `dialog_id` field. Do not
choose a manager dialog FourCC and do not reserve a `CGxx` ID. The manager finds
the source panel already referenced by each declared Building Description and
its package-owned `SMNU`/`STRT`, then allocates and rewrites the final internal
ID. The controller recipe's `source_dialog_id` has a narrower purpose: when a
mod authors an optional secondary panel, that field identifies its existing
package-owned SMNU/STRT pair so the manager can resolve and relocate it too.

## Start with stock Majesty

Before adding native code, check the options in this order:

1. Express the feature through existing CAM resources.
2. Express gameplay behavior through GPL using Majesty's normal dispatch and
   callback systems.
3. Use an existing documented Mod Manager feature with different package-owned
   IDs, resources, and parameters.
4. Add native runtime support only when the first three options cannot reproduce
   the required stock behavior.

A native proposal must identify the closest stock Majesty mechanism. Trace its
complete lifecycle before implementing it:

- construction and registration;
- dispatch and state ownership;
- timing and callbacks;
- cancellation and interrupted paths;
- cleanup and destruction; and
- panel, selection, and other UI refresh behavior.

The implementation should copy that lifecycle and change only what is necessary
to make it safely reusable for package-owned content. If there is no stock
analogue, explain that clearly in the pull request before proposing a new
mechanism.

## Package declarations are data, not executable patches

A package may declare a supported, versioned feature and supply the namespaced
IDs and resources that feature requires. The manager parses and validates that
declaration, resolves conflicts, and produces a trusted merged registry for the
runtime.

If the desired behavior cannot be represented by one of the exact documented
records, the package cannot invent another type or embed native instructions.
Reusable native/DLL support must first be added to this repository through a
reviewed pull request; packages may use it only after a manager release
documents and implements the new typed recipe.

Packages must never supply or request:

- DLLs, object code, or machine code;
- executable addresses, offsets, signatures, or patch bytes;
- arbitrary memory reads or writes;
- PowerShell, Python, command lines, or external process execution; or
- a general-purpose native hook scripting language.

Allowing any of those would make a Workshop package equivalent to unreviewed
executable code. Unknown feature types, malformed declarations, ambiguous stock
bindings, and unsupported executable versions must fail closed: the manager
must explain that the mod cannot be combined and must not guess or partially
enable it.

## Pull request requirements

A pull request for a new runtime feature should include all of the following.

### Reusable feature contract

- Give the feature a stable, versioned, behavior-based name.
- Define the smallest typed package data needed to configure it.
- Keep the implementation independent of mod UUIDs, Workshop IDs, author names,
  and any bundled or compatibility-adapted mod.
- Support any number of valid declarations unless the traced stock mechanism has
  a documented limit.
- Define deterministic ordering, ownership, duplicate handling, and collision
  rules when several selected mods use the feature.
- Document how existing feature versions remain compatible if the contract later
  changes.

### Stock and executable analysis

- Document the closest stock analogue and its full lifecycle: construction,
  dispatch, ownership, timing, callbacks, cancellation, cleanup, and UI refresh.
- Identify every native hook site and why it is necessary rather than using CAM
  or GPL.
- Implement and validate the feature for both supported executable profiles:
  the public version and the `beta2` Steam Multiplayer Support version.
- Fingerprint supported sites and reject unknown or ambiguous binaries.
- Preserve unrelated stock behavior when the feature is absent.

### Manager and runtime implementation

- Add strict parsing and validation for the typed declaration.
- Validate every referenced package resource before Build and again before
  Launch.
- Emit only the deterministic data the trusted runtime needs.
- Make activation depend on the validated generated profile, not merely on a mod
  name or installed Workshop item.
- Reject unsupported revisions and conflicts with a clear author-facing error.
- Update the public package contract and include a minimal declaration example.

### Tests

Include tests covering:

- accepted and rejected parser inputs;
- deterministic merged output and manifest/runtime decoding;
- multiple unrelated mods using the feature at the same time;
- duplicate IDs, resource collisions, incompatible declarations, and malformed
  data;
- both the public and `beta2` executable profiles;
- repeated Build, Launch, save/load, return-to-menu, and reload lifecycles;
- cancellation, cleanup, and UI refresh paths from the stock analogue; and
- launches and merged profiles that do not request the feature.

Runtime changes also need compiled x86 tests where applicable. A focused test
for one example mod is useful, but it does not replace UUID-agnostic and
multi-mod coverage.

## What a mod author ships after support is accepted

After the reusable feature is merged and released, a mod author ships only the
normal mod package and its documented feature declaration. The package does not
ship a private runtime or ask players to install another DLL. The Mod Manager
validates the declaration and enables its own reviewed implementation when that
mod is selected.

See the [Merge mod authoring guide](manager-merge-contract.md) for the package
format. To propose implementation support, open a
[pull request](https://github.com/Phantomstar721/majesty-gold-hd-mod-manager/pulls)
against the public repository.
