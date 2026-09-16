# Stock-derived building open/closed toggle

`stock.mx22-building-open-toggle.v1` clones only the Embassy's persistent
open/closed state and paired-control presentation. In both supported Majesty
executables, MX22 commands `0x22AB` and `0x22AC` write
`ATTRIB_EmbassyActiveFlag`; the presenter hides the action matching the current
state, shows the opposite action, and sends enable message `0x0A` to it.

The generic recipe uses private command IDs and the declared custom building's
resolved dialog. It repeats that presentation after the parent's stock setup,
event, and ordinary command handlers. State remains on the building, so panel
replacement and reopening naturally read the same value.

The Embassy command also submits order `0x16`, which creates or cancels
`GS_EmbassyRecruitOrder`. That behavior is not part of a generic building
toggle and is deliberately omitted. Package GPL may read the stock attribute
when deciding whether its own service is available.

The manager validates a coherent pair of literal stock-shaped open and close
controls in the package-owned parent SMNU. A package may use MX22's full-width
presentation, AP39's exact half-width action presentation, or AP10's exact
93-by-26 action-button presentation. Only the documented package-owned fields
may differ. The AP39 variant retains its stock `INBb` set `0x3F8`, selector
`0x52`, font, colors, opcodes, and terminator. The AP10 variant retains the
literal `INBb` token, 93-by-26 geometry, font, colors, opcodes, and record
boundary while allowing a package-owned image set. Validation also requires
distinct non-stock commands, a cataloged stock primary-building parent, and
global parent/command ownership. The runtime selects that parent's exact
audited 11-, 13-, 14-, or 17-entry stock vtable in each supported executable;
it does not treat unrecognized classes as AP10. MMCR v4 stores only the
qualified key, resolved parent dialog, commands, and controller base. No
package UUID or building name is hard-coded in the runtime.

Public `1.5.2.24` uses command handler RVA `0x000B9540` and presenter RVA
`0x000B95A0`; beta2 `1.5.2.28` uses `0x000B9F80` and `0x000B9FE0`.
Read-only executable-profile tests verify their shared command and presenter
instruction shapes.
