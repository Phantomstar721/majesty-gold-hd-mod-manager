# Focused production candidate 0.3.10

Base: bb0a30e (production 0.3.9), not the dirty development checkout.
Standard/Standard and Standard/Merge script review, player-facing pair choices,
dataset scoping, cache invalidation and three-profile runtime support are retained.

Additional runtime-source changes: none. Additional Python behavior changes:
timed-v4 image reference relocation and leading-dot decimal tokenization only.
Their regression modules are mandatory in verify_release_parity.py.

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
