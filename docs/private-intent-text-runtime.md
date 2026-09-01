# Manager-owned activity text

## Why this runtime route exists

Majesty stores activity text (`AITX`) in one positional table. Active Mods and
quests can each load a complete copy of that table, so a quest row and a mod row
with the same number describe different things even though the executable sees
only one integer. Editing or duplicating every quest is not a scalable fix.

The runtime therefore gives manager-built GPL a private positive ID range and
intercepts only IDs explicitly present in a manager-supplied registry. Every
other value executes Majesty's complete stock resolver through a trampoline.
The hook is installed only when MMCP declares
`private-activity-text-registry.v1` and MMTX is valid and non-empty.

## Stock lifecycle traced in both Steam branches

`$SpecifyIntent` stores the expression value unchanged in
`#ATTRIB_AIIntentionString` (`0x1E565041`):

| Site | Public 1.5.2.24 | beta2 1.5.2.28 |
|---|---:|---:|
| `$SpecifyIntent` handler | `0x0042EE30` | `0x0042FD90` |
| Shared AITX resolver | `0x00508480` (RVA `0x00108480`) | `0x0050A650` (RVA `0x0010A650`) |
| Resolver entry guard | `56 E8 6A 6A 05 00` | `56 E8 DA A9 06 00` |
| AITX table provider | RVA `0x0015EEF0` | RVA `0x00175030` |
| Stock string assignment | RVA `0x00228350` | RVA `0x0023AAF0` |

The resolver's unchanged successful path is:

1. Save `ESI` and acquire the stock resource owner.
2. Read its loaded AITX table pointer at `+0x28`.
3. Look up `(table, -1, intent_id)`.
4. If a row exists and the caller supplied a destination, assign it with
   Majesty's stock 12-byte string-view copy routine.
5. Return true. A missing row follows the stock diagnostic/fallback calls.

The private path copies step 4 literally and returns the same success result.
The trampoline recreates the relocated provider call, then resumes at the first
unchanged stock instruction. It retains stock lookup, fallback logging, stack
ownership, and return behavior for all non-manager IDs.

The one resolver covers all currently supported stock consumers:

| Consumer | Public call | beta2 call | Lifecycle |
|---|---:|---:|---|
| Hero activity panel | `0x0049875B` | `0x00498D8B` | Reads `#ATTRIB_AIIntentionString`, then resolves it while repainting the row. |
| `$LocalChatMessage` | `0x0042DF5B` | `0x0042EEBB` | Resolves its numeric AITX argument immediately. |
| `$MessageFlag` presenter | `0x0045BE96` | `0x0045CEC6` | The GPL handler first stores the numeric ID in the stock `MSGF` lifecycle; the stock flag presenter resolves that stored ID here. |

`tests/Test-IntentTextRuntimeProfiles.ps1` verifies these calls independently
against a public and a beta2 executable fixture. `Test-DualRuntimeProfiles.ps1`
also guards the resolver entry bytes in both complete runtime profiles.

## Registry protocol

The manager writes `Data/MMMIntentText.bin` in its generated package and, when
private text is required, starts the launcher with
`MAJESTY_MOD_MANAGER_INTENT_REGISTRY` set to that file's exact absolute path.
Every manager launch also supplies the MMCP file through
`MAJESTY_MOD_MANAGER_CAPABILITIES`; that manifest is the authoritative launch
marker. The launcher creates a private readiness event and publishes its name
through `MAJESTY_BUILDING_RUNTIME_READY_EVENT`.
Majesty's main thread remains suspended until the DLL has validated the file,
matched the executable profile, installed the private resolver when needed, and
successfully completed every other required static executable patch. Only then
does the DLL signal that event. A failure in the registry, profile, resolver, or
any required pre-window runtime install shows a clear error and terminates the
new process instead of resuming a partially patched game.

The stock-controller window-procedure lifecycle hook is the one deliberate
post-signal exception: Majesty's suspended stock main thread must run before
its top-level window exists. When the canonical
`stock.controller-recipes.v1` capability is derived from a non-empty MMCR
registry, the DLL waits for that stock-created window immediately after
releasing the barrier and installs the subclass. If it cannot do so, it reports
the failure and terminates the process. A legacy Alchemist package reaches the
same path only after the manager translates its v1/v2 alias into generic MMCR
records.

The deterministic little-endian `MMTX` version 1 format is:

```text
4 bytes   ASCII magic MMTX
u32       schema version (1)
u32       record count
repeat record count times:
  u32     private intent ID
  u32     Windows-1252 byte length
  bytes   text, without a NUL terminator
```

IDs are strictly increasing and unique in `0x60000000..0x6FFFFFFF`. Text must
be non-empty, contain no NUL, and use defined Windows-1252 bytes. The parser
rejects truncation, trailing bytes, duplicates, unsupported versions, excessive
sizes, and out-of-range IDs. Declaring the private-text capability with a
missing, invalid, or zero-record registry stops runtime initialization before
Majesty resumes. Without that capability the resolver is neither validated nor
modified, regardless of a stale MMTX environment variable.

The registry is parsed once before installation and remains immutable for the
process lifetime. There is no timer, watcher, polling loop, replacement text
table, quest scan, or quest mutation. Majesty continues to own when text is
requested and when each UI consumer refreshes.
