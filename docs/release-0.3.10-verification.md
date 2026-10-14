# Focused production candidate 0.3.10

## Final candidate checkpoint

The final candidate includes grouped Standard load-order review with cycle
rejection, shared sound preferences, authored image-table ordering, tile
allocation after palette relocation, and generic periodic damage-call routing.
The source and packaged gates ran before Workshop staging. The user subsequently
confirmed Prepare completed with the reported combination. This is not a claim
of live gameplay acceptance on every executable profile. The upload is staged,
not published. See `art-order-and-palette-relocation.md`,
`sound-resource-preferences.md`, and `regression-gates.md` for the contracts.

## Earlier verification history

Base: bb0a30e (production 0.3.9), not the dirty development checkout.
Standard/Standard and Standard/Merge script review, player-facing pair choices,
dataset scoping, cache invalidation and three-profile runtime support are retained.

Additional runtime-source changes: none. Additional Python behavior changes:
timed-v4 image reference relocation, leading-dot decimal tokenization, and
generic XML building override admission, dataset-scoped output and shared
mod-pair preferences. Their regression modules are mandatory in
verify_release_parity.py. See xml-mod-preferences.md for the XML contract.

Resource-dependent regression fixtures accept MAJESTY_STOCK_ROOT separately
from executable fixtures; executable byte checks still use their exact profiles.
This avoids treating an executable-only fixture as a complete installed game.

Evidence: local/release-candidate-tests.log, local/release-0310-build.log and
dist/release-parity.json. Broad regression skips are not profile acceptance;
the mandatory release matrix separately rejects missing/skipped profile checks.
Live gameplay acceptance is not established by those offline checks.

The installed Bards Workshop-directory copy is explicitly a development test
deployment (guild docs/damage-contribution-migration-2026-10-05.md and its
artifacts/workshop-test-deployment-receipt.json), not evidence of published
requirements. Its newer damage/interception declarations and the local Witch
test package remain paired with the development Manager. Do not replace that
test Manager with this focused production candidate or advertise those features.

No merged profile is prepared by release verification. No game preferences,
installed runtime, subscribed package or canonical development output is changed.

XML follow-up evidence: local/xml-release-regression.log,
local/xml-authored-fixture.log, local/xml-native-components.log and
local/xml-release-build.log. The authored-input check uses the installed
Standard building document with three synthetic overrides and exercises both
winner choices. It is not the other author's unsupplied patch, which is optional
additional reproduction evidence, not a requirement of this generic solution.
The XML regression and mandatory three-profile build gates completed before
refreshing Workshop staging. Publication remains a separate user action.

Sparse numeric-art follow-up: the art import boundary normalizes ID-keyed
TILE/SPLT TOCs before comparison; ordinal-flagged and named tables retain their
interpretation. The raw CAM codec remains lossless. The mandatory
test_sparse_art_ids module covers high/out-of-order IDs, duplicate-ID priority,
empty gaps, ordinal flags, allocation bounds and two-provider frame/palette
relocation through actual import and composition. Missing dependencies remain
errors, including stock-palette fallback when no private palette was emitted.
Evidence logs: local/sparse-art-regression.log and local/sparse-art-build.log.
No runtime source changes or new live-game acceptance are claimed. The author's
reported in-game sparse-ID experiment is external evidence, not our own run.

Real-package follow-up: the initial synthetic sparse-ID coverage omitted full
DWORD SPLT keys. This caused the Adventurers Guild archive to be rejected even
though its extra palette key was valid. Numeric key magnitude is no longer an
allocation size: full keys are compacted with reference rewrites, shared across
component CAMs. No printable-name heuristic or guild exception is used.

`scripts/verify_shipped_art.py` is now a required release-build gate using
`release/art-regression-packages.json`. It reads actual package manifests/CAMs,
records hashes, and runs both each package and their combined art through the
real importer/composer in memory. It does not Prepare a user profile or claim
GPL/runtime/gameplay validation. Missing production packages or art failures
block release. The production matrix includes Adventurers, Alchemist, Bards,
both Phantom distributions, Royal Menagerie and the legacy Troubadour package.

The explicitly excluded development Witch Hunter package is also inspected and
its failures are retained in the report, but it is not a production dependency.
Its flag-0 TILE tables use printable names while frames refer to ordinals;
this separate archive-authoring mismatch was sent to its owning guild thread
01a107cf-02e2-7613-ab18-c597756ccd8c for correction. No Manager exception or
silent ordinal fallback has been added. Exact findings and source hashes are
in `local/shipped-art-regression.json`.
