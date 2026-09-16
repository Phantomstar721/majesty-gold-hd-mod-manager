# Stock-derived occupant action panels

`stock.mx04-mx05-occupant-action-panel.v1` reuses the expansion Mausoleum's
MX04 → MX05 lifecycle. Its package fields are specified in the
[authoring contract](manager-merge-contract.md#supported-typed-runtime-features).
It does not identify a particular guild, Workshop item, UUID, or unit type.

## Stock lifecycle

1. MX04's `0x1F44` command calls the stock dialog opener with `(MX05, 0)`.
   A package's opener makes that same call with its manager-resolved child ID.
   The factory aliases the child controller class to MX05 while retaining
   the package-owned streamed menu/string resources and building context.
   The parent retains its declared cataloged stock primary-building class. The
   runtime verifies its exact public/beta vtable and preserves that class's
   audited 11-, 13-, 14-, or 17-entry boundary.
2. MX05 allocates `0x4C` bytes and constructs the normal list controller. It
   sets list mode `1`, binds the current player with the stock zero secondary
   filter, installs the ordinary list callback, and performs stock setup. The
   shared setup invokes virtual slot 14 before slot 1 tail-calls virtual slot 10
   as its final native presenter. Private occupant-action and live-agent-list
   instances retain both stock presentation paths; the Manager adds no action
   controls and performs no synthetic first-open UI write.
3. MX05's population virtual reads relation index `2` from the parent agent's
   relation collection at `+0xA4`: the building's generic `Occupants` list.
   It copies its agents into the list-controller-owned vector at `+0x34`.
   There is no hero/title filter. The shared row callback and painter are the
   same path extended by Generic Visitor Lists, including icon/name/level.
4. List selection uses native control `0x1388`. No selection disables
   `0x138B` and clears the price. Otherwise stock evaluates the GPL cost
   function on the selected agent, compares it with the player's treasury,
   and displays the quote in `0x1F46` with native affordability styling.
5. Action control `0x138B` obtains that agent's handle (`+0x70`), calls the
   cost function again, and submits command `0x15` with four 32-bit words:
   `(command, parent building handle, selected agent handle, quoted price)`.
   The stock packet constructor stores the words unchanged; serialization
   and deserialization copy all four words without narrowing the command.
   The manager substitutes only a private command discriminator here.
6. The native simulation queue executes the packet later. The private command
   selects its immutable registry record, then enters the unchanged stock
   `0x15` branch. This resolves the selected agent, validates its stock agent
   interface, obtains its player's treasury, checks the quoted amount, and
   deducts it. The GPL invocation still receives exactly the selected agent.
   Only its function-name string is substituted. Callback selection is scoped
   to this execution, not to a borrowed UI pointer or the last-opened panel.
7. Stock MX05 receives the normal list-change notification `0x09435358` and
   invokes its shared list/cost refresh virtual. Back uses the native parent
   selection/dialog lookup. Other list controls and drawing remain unchanged.
8. Close/replacement/destruction use the existing stock dialog owner and
   scalar-deleting destructor, including vector cleanup and delete flags.
   The manager clears its borrowed UI reference at that boundary. A queued
   command remains governed by the native simulation lifecycle after the UI
   closes. No additional timers, polling, unit markers, or per-unit tasks exist.

The stock GPL reference is `SDK/OriginalQuests/GPLMx/TaskModules/Buildings/`
`Mausoleum.gpl`: `Mausoleum_Resurrect_Cost(agent)` returns an integer and
`Mausoleum_Resurrect_Begin(agent)` owns the occupant removal/unhide/effect
sequence. Resurrection completion belongs to the stock effector callback,
not the panel. Other packages supply their own separately traced GPL action;
the runtime does not force resurrection or any other unit behavior.

## Independently verified executable sites

All addresses below are RVAs, not file offsets. The runtime checks executable
profile and call targets before writing any of these hooks.

| Site | Public 1.5.2.24 | beta2 1.5.2.28 |
|---|---:|---:|
| Cost symbol string-constructor call | `0xBBDDD` | `0xBC81D` |
| MX05 queued-command submission call | `0xBC14F` | `0xBCB8F` |
| MX05 post-submit shared-control call | `0xBC15A` | `0xBCB9A` |
| MX05 general shared-control call | `0xBC171` | `0xBCBB1` |
| Shared control handler | `0x98170` | `0x995A0` |
| `0x1388` row-click focus branch | `0x981A9` | `0x995D9` |
| `0x138B` post-action focus branch | `0x981E8` | `0x99618` |
| Building-command executor | `0xC4DA0` | `0xC57E0` |
| Action symbol string-constructor call | `0xC55F1` | `0xC6031` |
| Native narrow-string constructor | `0x227A80` | `0x23A220` |
| MX05 vtable (15 entries) | `0x33EAC4` | `0x3577AC` |
| List population virtual | `0xBC340` | `0xBCD80` |
| Shared list setup | `0x98EA0` | `0x99510` |
| Shared list refresh | `0x97E20` | `0x98640` |
| Shared list callback | `0x98C60` | `0x992D0` |
| Shared row painter | `0x98360` | `0x98990` |

Stock cost/action names are passed through unchanged unless the relevant
private UI/command record is active. The original MX05 vtable is not modified.
Private instances copy its exact 15 entries and register only the existing
manager destructor-cleanup boundary. There is no replacement list renderer.
An independent live-agent-list recipe may keep its child open after an action
or prevent a row click from transferring world/tracking focus to its live-agent
identity. Those narrow policies are not available to occupant-action panels and
do not alter their stock lifecycle.

## Manager wire format

Profiles without occupant panels retain canonical MMCR v2 bytes. When panels
are present, MMCR v3 adds a tenth count and a final occupant section. Each
record contains a length-prefixed panel key, parent and child dialog FourCCs,
opener command, allocated action command, length-prefixed cost and action GPL
symbols, then the declared parent controller FourCC. Numeric fields are
little-endian uint32. Keys/symbols remain bounded to 64 ASCII bytes.

The manager sorts owner-qualified panel keys and assigns action commands
`0x10000 + index`; these belong to the native building-command discriminator
namespace, not the menu-control/AP99 descriptor namespace. Reordering the same
selected packages does not change allocation. Removing a package removes its
records and callbacks from that composition. Existing MMCR bounds and the
32-total-panel limit apply across all panel families. The native parser accepts
v2 and v3, rejects duplicate private ownership and noncanonical action IDs, and
does not install this route at all without occupant records.

## Validation

- `test_occupant_action_panels.py`: strict schema, callback signatures, required
  controls, collision rejection, legacy coexistence, two unrelated owners,
  reordered/removable packages, and wire corruption/truncation.
- `Test-StockControllerRegistry.ps1`: compiled native v2/v3 parser coverage.
- `Test-OccupantActionRuntime.ps1`: actual x86 runtime code with stub stock
  endpoints; verifies queued identity after UI close/switch, stock passthrough,
  nested execution, exact packet arguments, callback names, and UI cleanup.
- `test_occupant_runtime_profiles.py`: read-only checks of both executable
  call targets, vtables, Occupants binding, and shared visitor painter. Supply
  local paths through `MAJESTY_PUBLIC_EXE` and `MAJESTY_BETA2_EXE`.

In-game acceptance should cover an empty list, multiple occupant types,
selection changes, unaffordable/affordable actions, exact gold deduction,
callback effects, Back/reopen, a different building/panel, save/reload, and a
stock Mausoleum. Automated route tests do not substitute for that gameplay test.
