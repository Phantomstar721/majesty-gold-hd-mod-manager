# Message flag controls

Available in Manager 0.3.11 on Steam Default 1.5.2.24, Steam beta2 1.5.2.28,
and GOG 1.5.2.28. The optional declaration is `stock.message-flag-controls.v1`.
Older Managers reject the unknown declaration. It is not enabled merely by
installing the Manager; selected content must declare it.

Minimal `mod-definition.json`:

```json
{
  "schema_version": 3,
  "mod_id": "{51f3f0db-81ab-42b4-9ace-aba863de9917}",
  "internal_name": "MessageFlagControls",
  "display_name": "Message Flag Controls",
  "custom_buildings": [],
  "runtime_features": [{"type": "stock.message-flag-controls.v1"}]
}
```

The standard Mod manifest uses the matching UUID and
`<DataConfiguration><Dataset base="Any"><Load/></Dataset></DataConfiguration>`.
These two files are sufficient. No dummy CAM, BCD, GPL, resource IDs, native
addresses, or compatibility substitution is needed. The Manager categorizes the
declared native dependency as Merge, derives MMFR v13 flag256 and the corresponding
MMCP capability, and verifies their agreement at runtime. Duplicate identical
declarations share one implementation.

The in-quest APMK controls sit immediately left of Options. The stock status-text
region shrinks to reserve their space. The selected resolution layout and existing
control recipes are retained, including Lower Tracking Window's command and hover
handlers. `Flags ON` means messages are allowed; `Flags OFF` means suppression is
active. Clicking the toggle persists the new state; enabling suppression also
clears current MSGF units. `Clear flags` queues stock dismissal commands without
changing suppression. Reward flags are excluded by kind. These controls do not
change gold, gameplay bounties, or saved-game serialization.

Global preference: `%LOCALAPPDATA%\MajestyHD\MessageFlagControls.dat` (default:
messages allowed). Preference write failure leaves the toggle unchanged and logs
the failure. There is no per-frame scan: dismissal takes one read-only snapshot
only when a clear is requested, then re-resolves IDs before submitting stock
commands. New messages are gated at stock creation. Existing message flags loaded
from a save are not automatically removed; the user explicitly excluded that work.

Supported profiles: Steam Public1.5.2.24, Steam beta2 1.5.2.28, GOG1.5.2.28. Each
uses its own guarded stock stream/controller/command sites. This contract does not
claim in-game acceptance before the user's playtest.

Test through `dist/Majesty Mod Manager/Majesty Mod Manager.exe`: select the mod,
Prepare, launch a quest, trigger messages, toggle suppression and clear messages
independently, then return to the menu and enter another quest. Restart the game
to check preference persistence. Check that Options, Lower Tracking Window, and
player reward flags still operate normally. The user owns Prepare and gameplay.
