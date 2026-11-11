# Alpha panel resource contract correction

2026-11-10. The installed alpha guild's WSHR SMNU retained native MX05 control
8006 / 0x1F46 at record11, size0xA8, but its migration changed the rectangle
from `(115,222,39,16)` to `(0,0,0,0)`. Canonical pre-alpha resources retained
the stock rectangle. The builder explicitly requested that zero-size change.
The error was a guild resource regression; Manager validation was correct.
The engine presentation handoff does not replace the existing MX05 action/price
handler or authorize removing its mandatory controls.

The earlier parity check allowed SMNU/STRT edits and checked LABEL directives,
but never exercised text-resource materialization. Admission and GPL/compiler
checks also did not reach that stage. Thus their coverage did not justify the
earlier ready-to-test handoff. Do not treat resource-diff parity as successful
composition.

`scripts/verify_panel_resource_contracts.py` now reads an actual package, resolves
building/controller ownership, checks authored controller/toggle/recruitment
controls, discovers private activity strings and invokes production
`merge_text_resources` entirely in memory. It uses the actual Public, beta2 and
GOG fixture identities and respective installed stock data. No package/profile
destination is supplied or created. The existing handoff parity checker calls
this check too. Alpha regression gates include
`test_panel_engine_resource_contracts`; its negative case collapses this native
price rectangle in an in-memory inventory and requires rejection.

Primary evidence: stock DataMX/mx_textdata.cam SMNU/MX05, original and deployed
guild CAMs, `prepare_panel_engine_migration.py`, production compose validators,
and the existing quest-board presenter addressing0x1F46. KG commit
f2644580d33ad98703361cd8fc88c825068161ef, evidence nodes
`evidence.dialog_panel_controls_20261008` and
`evidence.phantomstar_mods_panel_techniques_20261009` were consulted with their
source/scope qualifications. Existing research shared-map checkpoint21424 and
the mapped MX05/employment contracts were reviewed. No new native mapping or
runtime mechanism is needed; no validator was relaxed.

Private receipts: `local/panel-engine-host/mx05-current-shapes.json` and
`panel-resource-contracts.json`. Offline resource composition does not establish
loaded-game hiring, research or save/load acceptance.
