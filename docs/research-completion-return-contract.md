# Research completion callback return contract

## November 9 alpha crash

The Public alpha dump `MajestyHD.PanelEngineAlpha.exe.49408.dmp` has SHA256
`c0f4fd4988f0384850b5050cb6fbb5d3d2a51d36cf6c342fbd36f14a36fd9cbf`.
It faults at 004DFE6F while dereferencing the null result of the research
descriptor resolver. The captured native code agrees with the saved crash
executable. The resolver argument remaining at ESP-4 is zero. The stack's
return position points into the Manager research bridge's stock passthrough
call, with event reason 2 and context 15EBF398. This is bounded call-site
evidence, not a complete symbolic stack unwind or heap lifetime proof.

The matching log records completion of research 7604 immediately beforehand.
The prepared controller registry identifies that command as Silver Salts in
the Workshop family. The recently constructed native guild has a different
context (15EBF800); construction timing alone did not identify the cause.

## Stock contract and correction

The stock order dispatcher consumes the callback's entire return word. Zero
permits completion/removal; a nonzero result retains the order. The research
callback returns zero on its normal completion and cancellation paths. The
Manager declared both its stock function pointer and bridge as returning void.
Private completion logging could therefore leave an unrelated value in EAX,
retaining an order after stock had cleared its current research command. The
dump is consistent with that order being delivered again with command zero.

Both callback declarations now return uint32_t. Passthrough and private stock
completion preserve the callee's result across Manager cleanup and logging.
Handled kingdom/repeatable actions return the stock normal result, zero.
No descriptor bypass, replacement order lifecycle or polling was added.

## Evidence and regression boundary

Consulted knowledge graph commit
`f2644580d33ad98703361cd8fc88c825068161ef`, nodes
`engine_property.attrib_currentresearchitem` and `mechanic.order-catalogue`,
especially `semantics.completion_events` sourced from
`research_game_debug_evidence_order_catalogue_20260921_findings_json`.
The graph's modified-beta2 scope is retained. Primary existing references:
research `docs/shared-map.md`, `docs/building-research.md`,
`docs/research-notifications.md`, and
`local/decompiled/building-research-verify/4e0430.c`.
Manager guarded completion RVAs are DFE20 (Public), E0430 (beta2), E0B70
(GOG). The existing executable-fixture test now checks each zero-result/common
return epilogue, including RET. No new address mapping was introduced.

`QueuedResearchChecks.inl` checks the callback type, consumes completion and
removal return values in an order-dispatch fixture, and checks that a nonzero
stock test result survives private completion logging and passthrough. Existing
cases cover cancellation, repeatable actions, descriptor restoration and warm
registration. Alpha packaging now requires the native feature fixtures rather
than only compiling the runtime. These checks do not substitute for live game
acceptance on any of the three versions.

Pre-correction runtime object retained privately at
`local/panel-engine-alpha/research-crash-20261109/MajestyModManagerRuntime.pre-return-fix.obj`,
SHA256 `8b33aa9208338b1fd8d92f5a2dd436137f3e70c7cbeb0790270ef931997b7224`.
The guild owner's preserved crash artifacts remain under
`majesty-gold-hd-flamey-adventurers-guild-alpha/diagnostics/construction-complete-20261109`.
