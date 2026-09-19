# Manager-owned GOG helper adaptations

These MIT-licensed copies originate from the local
`majesty-gold-hd-remember-active-mods` and
`majesty-gold-hd-generic-visitor-lists` repositories as of 2026-09-19. Each copy
retains its original license. The Manager packages these copies so its required
helpers use the same audited Steam and GOG profiles as the native runtime.

Changes add an explicit GOG profile, its exact sites/imports/list owners, and
bounded hashes of helper callees. Existing Steam profiles, payload algorithms,
append/inert-section ownership, and restore ordering are retained. Visitor
selection now explicitly rejects unknown profiles rather than defaulting to
beta2. Remember Active Mods accepts an optional `PreferenceDirectory` for
isolated file tests; normal Manager use retains Windows LocalApplicationData.

The source lifecycle references are `docs/STOCK-LIFECYCLE.md` in the original
Remember Active Mods repository and `docs/research.md` and
`docs/custom-monster-icons.md` in the original Generic Visitor Lists repository.
The GOG address and ownership trace is in
[the Manager GOG audit](../docs/gog-support.md).

The seven optional executable utilities are copied from the corresponding
MIT-licensed packages in `majesty-gold-hd-qol-utilities/utilities` as of
2026-09-19. Each retains its LICENSE. Their GOG adaptations and stock ownership
trace are documented in [gog-qol.md](../docs/gog-qol.md). Packaging overlays all
nine owned executable helpers onto the complete utility suite, preserving Skip
Intro Videos and keeping the installed/restorer scripts on the same revision.
