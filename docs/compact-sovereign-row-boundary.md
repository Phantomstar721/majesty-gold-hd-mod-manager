# Compact sovereign row: implementation boundary

Requested by Witch Hunter owner 01a107cf-02e2-7613-ab18-c597756ccd8c under
explicit user approval. No runtime/declaration implementation is admitted yet.

The existing AP69 paid action is scoped to an active secondary building panel.
ResolvePrivateSpellDescriptor returns null without that context, and the
resolver hook bypasses private descriptors outside that panel. Stock compact
refresh does not construct private controls: it enumerates existing 4401..4500
controls and requires valid descriptors. Therefore exporting the existing
private control ID alone is insufficient and unsafe.

Keep the existing action/payment/target callback unchanged. A future generic
toolbar declaration should reference the existing action key rather than
duplicate its 500-gold price, target mode or callback. Its separate visibility
requirement is current-player completed stage3 of the declared building family.
AP69 level2 eligibility remains unchanged. Map-bar source resolution must
provide a qualifying exact source to the existing queued-action validation;
do not use the currently selected building or silently lower toolbar eligibility.

Required guild inputs after native contract confirmation: existing action key,
building-family identity, completed-stage3 requirement, approved compact spell
icon and hover-help resource. Control allocation, layout and source selection
belong to the shared Manager contract. This is input inventory, not a usable
schema; do not author a dummy feature or overlay against it.

Evidence: research shared-map.md, spell-ui.md, spell-ui-refresh.md and
spell-ui-notifications.md (modified-beta2 scope only); Manager
docs/paid-source-target-contract.md and ResolvePrivateSpellDescriptor.
Graph README/ mechanic.sovereign-spell-cheat-switches relevance check:
native consumer layouts omitted; static cheat readings do not fill this gap.
Graph baseline previously consulted f2644580d33ad98703361cd8fc88c825068161ef.
Missing exact boundary and profile scope recorded in research intake
20261015-manager-compact-sovereign-row.md. No merged profile changes.

## Independent bounded trace, October 15

Used guild private/breach-sovereign-bar-inputs-v1/inputs.json and the pinned
modified-beta2 image above. Repeatable read-only tool:
local/inspect_compact_spell.py. No Research message or native execution.

- 4BD330..4BD51F does not enumerate arbitrary spell descriptors. It queries
  fixed family 00714241, updates control251C, reads attributes535341/505341
  and compares a simulation-clock word. Its mutation/actor callees were not
  followed. It cannot be reused as a generic availability refresh callback.
- 4BD62A..4BD664 inspects two fixed setup values and conditionally hides
  control2580, then tails into the known bulk refresh. It does not append rows.
- AP92 is explicitly compared at4BD0BA in a controller/panel positioning loop.
  The loop opens/registers existing panels and computes bounds, then sends a
  separate UI message for AP92. AP93 had no literal reference in this image;
  absence of a literal is not proof it is unused.
- 445750's existing family query does have source-output semantics: clears the
  optional output, filters player ownership, calls actor virtual+90 and requires
  its return below3, reads01425041, matches the low24-bit family, computes stage
  from type's final ASCII digit and decrements if02425041 is zero. Only a
  strictly greater stage replaces the result/output pointer. Thus ties retain
  the first encountered candidate; there is no need to invent nearest-building
  selection. This is static instruction evidence, not complete lifetime proof.

The actor virtual+90 predicate was NOT followed into excluded callbacks.
It need not be reconstructed to call the stock family query unchanged. The
earlier characterization of this opaque callback as an implementation blocker
was too broad; the caller/output contract is the relevant boundary.

## Follow-up: literal stock query and compact caller linkage

Read-only tool local/audit_compact_profiles.py and its generated
local/compact-ui-profile-evidence.json bind all three pristine executable
hashes to independently identified compact vtables, hover/command handlers,
setup/event entries and family-query candidates. A byte prefix alone matched
four Public handlers and was rejected; the evidence additionally requires
stock resolver calls, compact command entry shape, vtable linkage and direct
calls to each profile's already verified sovereign-click helper. These are
navigation/ABI checks, not full lifecycle or runtime acceptance.

|Profile|Compact table VA|Command VA|Family query VA|
|---|---|---|---|
|Public|73EB04|4BC770|444840|
|Pristine beta2|7577EC|4BD1B0|445750|
|GOG|756944|4BD7B0|445670|

On the traced beta2 caller, compact slot+0C accepts commands1131..114C via a
fixed switch and invokes the same4AED10 helper as existing AP69. Private IDs
need generic dispatch; appending SMNU alone cannot make them cast. Hover slot+08
first calls its base handler, resolves the descriptor and conditionally calls
4ACF10. That helper consumes the price and building family/required-stage
descriptor; generic hover text cannot be inferred from the icon alone.

Stock query output can be consumed immediately on the UI/game thread: extract
the full source ID and pass it through existing paid ID/world/owner validation
at submission and execution. Do not retain the borrowed pointer between events.
No new source ownership or actor callback implementation is required. A toolbar
origin also needs its separate level3 requirement to survive targeting/queueing;
the existing action.requiredLevel2 alone cannot enforce that distinction.

Historical pre-capture gap (superseded by the bounded decision below): which existing notification guarantees a compact refresh
when the final qualifying building is completed, lost or changes owner. Known
02435358 and09425041 delivery is proven, but building-event causality is not;
the clock handler does not supply it. UI-only tracing does not establish actor
producer causality. Do not claim immediate disappearance from a UI handler test,
or substitute polling. A bounded user-operated event observation could establish
the existing signal without opening excluded actor implementation; gameplay and
such an observation session require separate approval under the current scope.

No new runtime feature schema has been admitted or deployed. Native resource
append/reflow and hover integration also remain implementation work, not proof
that a stock registration API supports arbitrary additional commands.

## V2 capture decision: stock refresh is sufficient to proceed

Preserved evidence: `local/compact-toolbar-diagnostic-v2/capture-20261015T011351Z.log`,
SHA256 `2DB705C83C55654C3AEA9F8AF180FA1CB356BE0CAFFFE729D578ED329BF4AA71`.
The Public 1.5.2.24 capture contains 58 EVENT rows, including 15 with
`stock_refresh=1`. The replacement AP92 controller `0F470850` attached at
110 ms and detached at 24032 ms; its last refresh notification was at 20328 ms.
There was no NOT-ARMED, record-limit or time-limit stop. The user reports
completing level 3 and destroying the Chapterhouse within this session.

`stock_refresh=1` is a classification of a delivered attribute after forwarding
the original handler, not a separate probe inside the native refresh callee.
The guarded handler evidence establishes that `02435358` and `09425041` take
that branch. All 15 observed refresh entries here use `02435358`; neither exact
actor producers nor the timestamps of the user's two actions were captured.

Decision: implement private toolbar availability by calling the unchanged stock
current-player family/stage query after stock setup and after those existing
stock refresh notifications. This is sufficient evidence to proceed with the
event-driven integration; no polling, clock refresh, invented actor callback or
additional diagnostic reproduction is required to settle that design choice.
This does not prove all ownership-change paths or live acceptance on beta2/GOG.
Those remain feature acceptance cases, not a reason to reconstruct the opaque
stock actor predicate. The graph baseline and cited primary sources above are
unchanged; the new evidence is this scoped Public runtime observation.

### Concrete shared-contract implementation boundary

The next Manager schema must reference an existing action by panel/action key
and add a toolbar-origin family/minimum-completed-stage, icon and help binding.
It must not duplicate payment, target mode, callback or effect declarations.
Manager owns collision-free private controls, AP92 resource/layout integration,
private descriptor resolution outside AP69, and explicit command/hover dispatch.
The stock fixed switch cannot dispatch arbitrary private IDs by itself.

Re-evaluate the stock family query on setup/refresh and again when dispatching
the private command. Consume its borrowed source immediately as a full actor ID;
do not cache the pointer. A missing qualifying source makes the toolbar entry
unavailable. Preserve the toolbar-origin minimum stage through targeting and
queued execution as well as the existing identity/world/owner checks. Do not
reuse action.requiredLevel alone: the current AP69 action remains level 2 while
the toolbar origin requires level 3. Selecting another building is not a source.

For the supplied guild inputs, this means reference `whp.chapter-spells` /
`breach-the-den`, family `WCH`, completed stage 3 and approved `WBic` set 1015;
reuse the existing 500-gold action and its callback unchanged. This is the
implementation contract, not an admitted manifest declaration yet. Remaining
work is schema/registry transport of origin eligibility, actual control layout,
hover and dispatch implementation, plus three-profile guarded verification.
No new guild artwork, callback or further evidence capture is needed now.

Normal runtime currently restored and independently hash-checked:
`263A9E6DE4B546DCFB686BC63F13EF81457F56B5C132F387E97E993850295C82`.

## Author contract implemented separately from native admission

`src/majesty_cam/compact_sovereign_toolbar.py` now parses and binds this exact
candidate shape against the same package's existing panel/action objects:

```json
{
  "type": "stock.ap92-sovereign-toolbar-action.v1",
  "panel_key": "whp.chapter-spells",
  "action_key": "breach-the-den",
  "required_level": 3,
  "icon_id": "WBic",
  "icon_set": 1015,
  "hover_text": "Breach the Den — 500 gold. Encourages your heroes to attack a chosen lair for 3 minutes. Your heroes deal full weapon damage to it."
}
```

The binding retains the original action object, derives family from its panel,
rejects ambiguous/missing references and rejects a weaker toolbar level. Price,
callback, target mode, family and command IDs cannot be redefined in this input.
Text is checked against the game's Windows-1252 representation. The production
package parser still rejects this type: do not deploy it as a supported feature
until the resource/runtime route is complete. The focused fixture is
`tests/test_compact_sovereign_toolbar.py`; it also asserts this admission guard.
This is not queue transport or a live toolbar implementation.

### Precise remaining native boundary

Rechecked the existing pinned UI trace, without following actor/factory/cleanup
callees. `4BD520..4BD58E` refreshes existing controls then subscribes a particular
stock family source; it does not insert controls or reflow private buttons.
`4BCFF3..4BD0F8` obtains/sets the outer panel rectangle and sends the AP92-specific
message; that is not evidence for child-control insertion or visibility-driven
compaction. The mapped stock row call disables the action and hides its
`action+2000` companion; it does not itself remove/reposition the action.
The mapped hover route resolves stock building/descriptor data, not arbitrary
author hover text. Thus merely appending SMNU bytes and calling that row would
not prove the requested disappearing entry or correct hover binding.

The remaining source evidence required is the stock AP92 child layout/visibility
and help-resource route, including its exact control properties and all-profile
callers. The existing intake already includes this boundary; no duplicate or
Research message is needed. Native deployment stays held at that boundary rather
than substituting an overlay, polling, or guessed control mutation. Separately,
queued toolbar-origin stage transport remains implementation work: the existing
eight-word paid payload has no origin field and must not be silently reinterpreted.

## Build repair and deployment hold

The current source now carries toolbar origin in a separately tagged 7F32,
36-byte command, leaving the existing 7F31/32-byte command unchanged. MMCR25
carries the toolbar reference; source admission and in-memory resource assembly
accept the frozen guild candidate. These supersede the earlier parser/transport
status above, not the outstanding layout boundary.

The x86 lifecycle fixture initially failed compilation because its fastcall
ECX/unused-EDX adapters were assigned directly to thiscall function pointers.
Explicit ABI adapter casts now match the existing runtime thunk convention.
The next fixture failure exposed inherited test inputs: the execution-only
donor had command ID zero and a level-3 building. The toolbar fixture now uses
nonzero control 31248 and explicitly sets level 2 for the queued rejection
case; zero cannot exercise toolbar-origin eligibility. No production gate was
removed to accommodate these failures.

Deployment remains held on AP92's enclosing dialog geometry. The appended
control occupies x587..612, y4..29. The stock header has no explicit rectangle.
The verified outer repositioner 4BCF60..4BD0F8 preserves the existing width;
it does not prove growth from an appended control. panel-clip.md establishes
that ordinary owner drawing intersects the owner rectangle before drawing
children. scaled-layout.md separates control hit bounds from image bounds.
smnu-buffer-lifetime.md leaves control finalizers unreviewed. Therefore neither
successful parsing nor a cloned child proves visible, correctly clipped layout.
The exact missing contract is how AP92 derives/recomputes its owner extent and
lays out a newly visible/hidden row member, for all three profiles. Do not ship
the append-only resource as verified layout or substitute guessed geometry.

Evidence consultation retained graph commit
f2644580d33ad98703361cd8fc88c825068161ef and node
mechanic.sovereign-spell-cheat-switches, source
research_game_debug_evidence_native_semantics_20260912_findings_json,
/readings/5 (static read only; no native consumer-layout evidence).
The existing compact-row intake covers this gap and remains unsent under the
no-further-Research-handoffs restriction.

### Extent boundary resolved from literal stock header

The preceding no-header-rectangle claim was incorrect: `records()` splits on
every FFFFFFFF word, including signed coordinate values. The raw AP92 prefix
is `(1000,2,-1,-1,590,34,...)`. Do not interpret its first split fragment as a
complete header. The stock root has an explicit 590x34 rectangle; background
control 1 is also 590x34. Last stock button ends at587, retaining a3-pixel right
margin. One appended25-pixel button therefore requires615x34 on both owners;
two require640x34. Existing positions, centering coordinates, properties and
stock buttons remain unchanged. Hiding the private button uses the normal
visibility helper; this is a fixed-slot stock toolbar, not invented compaction.

Offline pristine-beta2 UI chain: 4B4870 calls64DE70 to acquire SMNU;64D330
constructs the ordinary dialog and calls virtualB8 (6655E0) before control
parsing. Root token2 branch66564B..665699 reads the four geometry values and
writes x/y/h/w; (-1,-1) requests alignment9. 666930 aligns the existing extent;
4BCF60..4BD0F8 later preserves its width when relocating the compact row.
The normal owner clip therefore includes the expanded resource rectangle.
Control675020 finalization preserves ordinary25x25 dimensions absent the
image-size flags; existing image and hit-rectangle contracts remain unchanged.
No new runtime geometry hook, controller or child-finalizer replacement is used.

`extend_stock_bounds` reads the typed root prefix directly, expands root and
background together, derives the margin from stock controls, and rejects an
incompatible effective background instead of silently changing it. Fixtures
cover signed centering, one/two additional slots and unchanged stock controls.
`test_compact_toolbar_profiles` guards the root geometry writer and existing
production vtable/setup/event evidence against all three exact executable
identities. The geometry writer file offsets are Public24F611,
beta2264A71,GOG264EF1; the corresponding RVAs are250211,265671,265AF1.
These are static resource/call-chain checks, not live UI acceptance.

## Always-visible presentation correction (October 14 user revision)

The earlier hide-on-loss behavior is superseded. Refresh always presents the
private cell and sends the ordinary disable message when its source is absent.
Submission and queued validation retain the distinct toolbar level3 requirement;
the original building-panel action remains level2 and its cost remains500.

Stock INTN1001 confirms direction-based normal/pressed/disabled states0/1/2,
with hover adding6 (control-gates.md and button-image.md). The guild supplies
a separate toolbar image, preserving its existing building-panel image.
The schema is unchanged: author base hover text should omit the price/requirement
suffix, which the native helper now appends in the game's language.

Exact compact hover callers on Public/beta2/GOG invoke helpers at RVA
AC620/ACF10/AD4C0. All240 bytes are guarded independently. These helpers first
inspect the real control's disabled state. Unavailable resolves
family | ((requiredLevel+'0')<<24) and formats that Description display name
with stock string B5; available formats price with string1D. A stack-local
five-word help descriptor supplies family/toolbar stage/price without changing
the action descriptor. Stock SDK M_Buildings.xml ABT3's display Description
includes 'Level 3'; custom stage descriptions must likewise supply meaningful
display names. No invented tooltip formatter or game-state query was added.

Actual stock art inspected through the extractor: interfacedata.cam INDz1012
references TILE509, a590x34 indexed version1 raster with embedded palette.
The gold border is in that raster, not a separately repositioned control.
Expanding only SMNU bounds did not expand the border. Composition now requests
the normal effective stock INDz dependency, extends the raster's central25px
span, preserves left/right ends and original palette, and appends one private
TILE in the same reconciled art domain. Only set1012's typed TILE field changes;
other sets and prior tiles are untouched. Width comes from actual final AP92
geometry, with the existing3px right margin and25px cell stride.

Evidence tools: local/audit_compact_profiles.py (exact three image hashes and
helper linkage), local/verify_toolbar_chrome.py (in-memory stock reconciliation
and rendered chrome), local/verify_toolbar_candidate.py (actual guild package
admission, in-memory resources and art; supports packaged-module loading).
Focused native tests cover visible unavailable state, stock help forwarding,
stage/ownership/loss checks and original payment; resource tests cover endcap,
palette, anchor and unrelated-art preservation. Live appearance/hover on all
three builds remains a user acceptance check, not claimed from offline tests.
Graph commit/source qualifications remain those recorded above. No new actor
research, polling, diagnostics or profile construction is part of this revision.

### October 15: stock group separation

Actual stock AP92 positions: Sun Scorch4410 x509 width25 ends534;
Winged Feet4407 begins537; Wind Storm4408 x562 width25 ends587.
The Helia-to-Lunord separator is therefore3px. The first private group now
gets that exact gap, derived from these stock records: first private x590,
right615, enclosing root/background/chrome width618. Additional private cells
retain25px stride. No runtime, eligibility or hover changes. The existing
endcap-preserving raster extension consumes the new final width unchanged.
Graph f2644580d33ad98703361cd8fc88c825068161ef and shared-map reconsulted;
this correction uses the stock resource geometry, not a new native mapping.

### October 15: retain the expansion toolbar dataset

The first implementation checked only base AP92. Its Any-load replacement
overwrote expansion AP92, removing Sorcerer controls4423..4428 and Abode
overlays9500/9600. This was a resource-scope error, not evidence of a native
refresh or clock failure. Primary evidence: installed Data/textdata.cam and
DataMX/mx_textdata.cam SMNU/STRT AP92. Expansion retains its original compressed
cells, IX93 images, flags, IDs, help rows and both overlays without edits.

Composition now emits an AP92-only MajestyExpansion CAM through the existing
native dataset-filtered Mod record. The common base toolbar and scoped expansion
toolbar both append the full-size private cell at590,4 and share the618x34 chrome.
Only root/background widths change in stock records. Existing preferred AP92
resources remain authoritative. The generated bundle reader admits only the
scope-owned toolbar filename and exactly AP92 SMNU/STRT, not arbitrary scoped
CAM payloads. A resource-only patch does not invent a GPL output; observer
validation counts actual compiled outputs, not unrelated resource-only records.

Regression coverage exercises merge_text_resources against both actual stock
datasets, compares every original spell/Abode control and help row, and covers
resource-only manifest loading plus malformed scoped CAM rejection. No native
addresses or runtime behavior changed. Graph f2644580d33ad98703361cd8fc88c825068161ef,
mechanic.sovereign-spell-cheat-switches (source
research_game_debug_evidence_native_semantics_20260912_findings_json /readings/5)
and research shared-map/control-gates were consulted. Their static spell-dispatch
evidence does not establish the resource layout; actual stock CAMs do. Live
appearance and spell activation remain user acceptance, independently of the
three executable-profile checks.
