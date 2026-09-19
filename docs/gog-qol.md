# GOG quality-of-life utility audit

All ten Manager utilities support GOG Gold HD 1.5.2.28. The seven optional
executable utilities are Manager-owned adaptations of the MIT-licensed scripts
in the QoL suite. Steam profiles and payload behavior are retained. GOG uses
explicit addresses, stock PE-section checks, exact owned-byte checks, and bounded
SHA-256 guards of the stock routines. Unknown code is rejected before writes.

## Stock lifecycle and addresses

Addresses below are virtual addresses in the stock image at `0x400000`.
The original lifecycle references are the respective helper repositories'
`docs/STOCK-LIFECYCLE.md`, `docs/STOCK-TRACE.md`, `docs/stock-trace.md`, or
`docs/research.md`. These ports retain those mechanisms and their ordering.

| Utility | GOG stock boundary | Behavior and ownership |
| --- | --- | --- |
| Downloadable Quests Shortcut | Quest rebuild `0x478BB0`; icon callback operand `0x478E96`; click comparison operand `0x479819` | The stock compass control 5000 uses callback `0x477BE0`; the Freestyle label retains `0x477CE0`. Only the callback operand, control comparison, and owned APdb fields change. GOG's callback vtable slot is `+0x74`. Native dispatch, menu construction, destruction and navigation remain stock. |
| Quest Map Drag | Input projection `0x4795C4 -> 0x45FC10`; displaced loads `0x4795C9`; continuation `0x4795D1` | The existing utility preserves registers, queries stock GetKeyState at `0x74D4C8` and cursor thunk `0x649CA0 -> 0x649C00`, and modifies the same scroll locals `+0x48/+0x24`. Bounds remain `+0x78/+0x7C/+0x80/+0x84`. Button-up or leaving bounds clears the drag marker synchronously. No callback or heap object is added. |
| Unlock All Quests | Eligibility `0x51DA40`; dispatch `0x479809`; visibility immediate `0x4790CD`; confirmed-reset continuation `0x479994` | The original eligibility SEH prologue is retained, with handler `0x717F58` and stock continuation `0x51DA47`. The existing session flag enables the native `ret 4` true result. Click and confirmed reset call the stock rebuild `0x478BB0` with unchanged arguments and cleanup. Cancellation never reaches the reset hook. Victory/save data is unchanged. |
| Suppress All Message Flags | GPL handler `0x432670` calls constructor `0x44A4C0` | The same void constructor returns before creating MSGF/ARE1, attaching actions, playing the sound or targeting the mini-camera. The caller ignores its return and owns stack cleanup. Reward flags and quest conditions remain stock. |
| Remember Game Speed | Slider `0x46C138`; slower/faster `0x465443/0x4654E5`; restore `0x4D9E25/0x4DA829`; copies `0x46B224/0x46B369`; construction `0x47C2FB/0x429E32/0x429E45` | Existing wrappers replay each stock write, synchronously read/write the four-byte preference, and use the original speed owners: global `0x7D3304` and GetGame `0x4D88E0` field `+0x98`. Native UI-event ordering and speed validation are retained. No timer/thread is introduced. |
| Remember Camera Zoom | Constructor call `0x5F2356`; virtual slots `0x762218/0x753930`; setter `0x5F1FA0` | The constructor's default 1.0 argument is replaced only by a valid stored float. Both virtual setters save and tail-call the same stock setter exactly once. It retains camera fields, projection and UI-refresh ownership. Missing/invalid preferences preserve the stock default. |
| Lower Tracking Window | Handler `0x46ADF0`; tooltip dispatcher `0x46B760`; selected-state owner `0x425F60 +0x48` | The existing private control `0x7F01` uses stock Track artwork and assigns the selected object to slot 2 through manager `0x7E0048`, `0x455D10 -> 0x459410`. Native assignment unregisters/registers target observers, updates captions and redraws; native invalidation/destruction clears them. The tooltip uses stock string copy `0x63CC40` and the third dispatcher argument. Other actions retain displaced stock prologues. |

Speed and zoom retain the stock CRT imports: fopen `0x74D458`, fread
`0x74D45C`, fwrite `0x74D460`, fclose `0x74D46C`. Each open is closed on the
existing synchronous path. Test-only `PreferenceDirectory` arguments allow
isolated preference files; normal use keeps LocalApplicationData/MajestyHD.

## GOG cave and section ownership

The GOG `.text` virtual size is `0x34BEFD`, raw pointer `0x400`, raw size
`0x34C000`. Its zero tail is only file `0x34C2FD..0x34C3FF`. Quest Map Drag
owns `0x34C300..0x34C3AC` (`0xAD` bytes). There is insufficient room for both
Steam-sized payloads, so Unlock All Quests uses an appended `.muqk` section:
`0x200` raw bytes, `0x100` virtual bytes, executable/readable, with the literal
`0xD6` payload and relocated external operands. Internal branches, stack
slots, instructions and reset/cancellation behavior are unchanged.

The `.muqk` lifecycle follows the other existing utility sections: validate an
exact header and complete payload, append at aligned ends, reuse an exact inert
section, clear only owned bytes when a later section exists, and truncate only
when it is last. Unexpected headers, overlap, nonzero payload padding and
partial hook sets fail before mutation. Other helpers retain their RVAs.

The process-local drag state uses `0x82B0A0..0x82B0B3`; the unlock flag uses
`0x82B0B4`. These are in the loader-zeroed alignment tail of GOG's writable
`.data`: declared data ends at `0x82B08C`, and the next section starts at
`0x82C000`. They do not overlap declared stock data or each other. Their
lifetimes remain the original utility lifetimes: synchronous button/bounds
reset, explicit Reset Quests, and process exit.

## Shared UI files and verification

The shortcut changes only its APdb rectangle/tokens and removes/reinstates its
owned button record. Unlock changes only its STRT label. Lower Tracking changes
only its APMK control. Existing archive offset/size updates and scoped backup
checks are retained, including restoration into the current archive rather
than replacing another utility's edits with an old full-file backup.

`scripts/audit_gog_qol.py` reproduces the shipped body guards and
`gog-qol-audit.json` from the pinned pristine image. Exact hook fields are
checked separately so these utilities can coexist. `tests/Test-GogQol.ps1`
uses disposable executable/UI copies for both installation orders, repeated
installation, dry runs, reverse restoration, inert-section reuse, and changed
callee rejection. The all-installed fixtures also exercise the native Manager
profile guards. These checks do not substitute for gameplay acceptance.
