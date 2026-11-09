# Bounded support reporting

The normal runtime retains first-fault registration/load evidence instead of
requiring a diagnostic build. The shared observer records the first rejected
boundary/thread, owner-safe load state, expected bytecode hashes and a 16-entry
load history. Both release and development retain the same bounded evidence without
enabling continuous attack tracing.

Runtime logs rotate at 1 MiB (current plus two backups). The logger retains
128 recent rows in fixed memory and pins the first fault into a separate
256 KiB-capped file, also with two backups. Further ordinary activity cannot
overwrite that fault within the process. Later failures preserve the previous
two fault files. Each row is bounded to 1023 bytes, stamped with process/thread
IDs. Existing oversized legacy files are not part of the new writer's growth
budget; the exporter explicitly lists and omits oversized inputs.

Before launch, three bounded snapshots retain Manager version, DLL/game hashes,
active IDs/names and prepared-report identity. Current identities in exports
are labelled separately from those launch-time identities. Manager task
tracebacks retain the two latest errors. All evidence is best effort: access
failures cannot prevent normal launching or replace the original failure.

Save Support Report exports only this allowlist plus the current composition
report (labelled current). Individual limits and an 8 MiB input budget apply;
unavailable/oversized files are listed in REPORT.json. No saves, mod binaries,
full memory dumps, directory scans or uploads. Paths and mod names may contain
personal information; the UI discloses this and the user chooses the ZIP path.

This does not retrospectively diagnose the October29 restart. The old release
never wrote its first fault. Nor does a bounded log guarantee recovery from
unhandled native faults, deadlocks, power loss, access failure or force-kill.
Generic minidumps are not installed by this change; the existing private
full-memory crash experiment remains separate and disabled by default.

Evidence/relevance: Knowledge Graph README at
f2644580d33ad98703361cd8fc88c825068161ef and research shared-map checkpoint14018
were consulted. The graph excludes the relevant native registration contract;
existing docs/sdk-bytecode-runtime-admission.md/source fixture boundaries apply.
This change concerns Manager-owned reporting/storage, not new game mechanisms,
addresses, cleanup, registration policy or gameplay behavior. Checks cover
bounded retention, first-fault survival through rotations, allowlist/size
handling, source nonmutation, and the normal release registration fault paths
on Public, beta2 and GOG fixtures. Live acceptance is separate.

Registration success summaries stop after eight attempts; a failed attempt is
always recorded, including late restarts. This does not weaken rejection rules.
