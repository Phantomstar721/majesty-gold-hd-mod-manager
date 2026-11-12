# Updated native engine support

The updated WE|1 data contract remains backwards compatible. Ordinary native
packages with paired SMNU/STRT behavior records remain Standard mods. They do
not need a Manager definition, renamed source files, or a compatibility copy.
Only loaded records and source proven to reproduce the loaded bytecode supply
implicit patch requirements. Ordinary text and unused examples do not.
Selected-content scans can prove the original loaded source project directly,
so native function dependencies are also detected for Classic Launch and
Standard-only setups that do not require Prepare. Catalog admission itself
does not run a compiler. Proof and dependency results are cached until their
tracked inputs change.

The updated data vocabulary includes background and picture binding, selected
text and hints, attribute value sources, scripted rows, hero spell/effect/item
rows, configurable row dimensions, title binding and spell/effect row changes.
Typed relocation distinguishes control IDs, image keys, callbacks, attributes,
spell/effect codes and image sets; it does not replace matching prose.
GPL string window references are a separate boundary. If an owner's panel is
renamed, a proven native `SF_SetWindow` call targeting the old ID is rejected;
computed or escaped targets are also rejected when that owner's namespace
changes and their destination cannot be proved. Unrelated owners, unrenamed
literal targets, comments and authored functions with the same name are left
alone. No arbitrary GPL string replacement is performed.

These additions require Manager Window Engine revision 3. Revision 2 provided
the existing private-handler presentation handoff and is not an upstream release
number. Original records continue to require only revision 1. Updated native
Script Functions require revision 2 for `SF_SetWindow`, `SF_ResetWindow` and
`SF_UnexploredArea`; `SF_MapAction` still requires revision 1. Installed older
patches cannot satisfy a newer requirement merely by sharing its service ID.

Both optional Quality of Life patches support guarded Default Steam 1.5.2.24,
Steam beta2 1.5.2.28 and GOG 1.5.2.28 profiles. Updating either patch preserves
the other patch's installed revision and active state. Known older bundles are
retained only for verified transactional upgrade/restoration. Installation is
still explicit. No patch is installed by scanning or changing selections.

The new SDK sources and linker have separate exact pins. Existing legacy source
and binding reports remain reproducible. New opaque API targets are tied to
stock clients on each fixture, and native virtual slots are measured rather
than copied between versions. GOG's text and stream-message slots differ from
Steam's. The registration chain retains the accepted CPU register/flags frame.
The original MapAction part remains byte-identical inside the extended module.

The existing presentation handoff, bounded class-table copying, live-agent
resolver and stock cleanup owner remain in use. No additional gameplay handler,
actor registry, timer, diagnostic polling or author-specific integration is
introduced. Native code is never inferred from a plausible live value.

Packaging includes only the module index and its indexed runtime bundles,
including reviewed upgrade inputs. Generated C++, objects and private proof
receipts are build material and are not application or Workshop content.

Verification separates exact fixture/code/data checks, source compiler proof,
provider-double lifecycle tests, in-memory executable install/remove tests and
actual gameplay. The former do not establish in-game acceptance. A package's
original dataset and quest restrictions remain its own; engine support does not
make unsupported quest modes supported.

## Supported executable coverage

| Executable | Window Engine | Script Functions | Verification scope |
| --- | --- | --- | --- |
| Default Steam 1.5.2.24 | Revision 3 | Revision 2 | Exact native fixture, bindings, install/remove and upgrade checks |
| Steam beta2 1.5.2.28 | Revision 3 | Revision 2 | Exact native fixture, bindings, install/remove and upgrade checks |
| GOG 1.5.2.28 | Revision 3 | Revision 2 | Exact native fixture, GOG-specific UI slots, install/remove and upgrade checks |

The packaged development checks cover these profiles, the original Standard
package readers and the existing managed-panel handoff. Local receipts are under
`local/sdk-update-20261111` and `local/regression`; they are private build evidence,
not distributed runtime files. The user's local in-game test was reported working
on November 11, 2026. That report does not establish separate playtests on all
three executables.

The updated 0.3.14 release candidate includes the corrected GOG text/message
bindings with these SDK modules. It replaces the earlier held Workshop stage;
cleaning that older stage's generated build files alone did not provide the
binding correction.
