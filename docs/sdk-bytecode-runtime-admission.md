# SDK bytecode runtime admission

## Failure and path selection

The October 15 reporting-user diagnostic first rejects SDK/OriginalQuests/
DataMX/MX_Task.bcd (SHA256
19bca1c34d15fb22606d8232bbd7981c2c1c6ba1591bf61ccb0259db05aec4bf).
The failure is `optional-protected-definition-not-shadowed`, Acid_Bolt_Hit,
before any baseline completes. Registration subsequently rejects the latched
fault. This is not evidence of a projectile-impact crash.

Public executable SHA256
255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4:
command parsing at VA402957 compares `-gpldebug` and sets byte7C0694.
Initialization at VA4EE645 reads `UseGPLDebugger` and also sets that byte for
a nonzero value. VA4EE776 branches on it; the enabled branch constructs
OriginalQuests/Data and OriginalQuests/DataMX from the SDK root, replacing
bytecode roots. Dataset XML uses MajestyBytecodeDataPath and
MajestyExpansionBytecodeDataPath for the six BCDs. No setting was changed.
The remote log proves the resolved SDK file, not whether a command-line flag,
saved preference, or explicit resource declaration selected it.

## Correction

`PackageProof::Find` recognizes reviewed SDK byte identities as the matching
baseline index, only when the proof contains the complete corresponding
retail baseline. This applies to both admitted retail families. Paths never
grant trust. Unknown digests, mixed baseline proofs, load ordering, ownership,
failed native loads, and generated-output digest checks remain enforced.
No BCD, preference, or merged profile is rewritten. No new native addresses,
hooks, scans, or gameplay behavior are added.

The installed Steam and GOG retail/SDK pairs were compared with the existing
strict structural codec, with byte-exact decode/re-encode. All six pairs in
each family have equal instruction operands/opcodes/auxiliary words, symbol
tables and DAT tables. Source/line debug metadata differs. This is equivalence
of these exact archives, not a rule that every file under SDK is trustworthy.

## Reproduction and verification

`scripts/compare_sdk_baselines.py <game-root> <research>/scripts/gpl-wire-codec.py`
performs the read-only structural comparison. Both installed storefront roots
were used. It does not build a profile or execute GPL.

`scripts/Build-Runtime.ps1 -OutputRoot local/sdk-baseline-validation
-RegistrationTests -RegistrationDiagnostic` exercises NativeRegistrationLifecycleTests
against Public, pristine beta2 and GOG executable fixtures. Set MAJESTY_PUBLIC_EXE,
MAJESTY_BETA2_EXE, MAJESTY_GOG_EXE to the exact fixtures and MAJESTY_BCD_GAME,
MAJESTY_BCD_GOG_GAME to the installed Steam/GOG roots. Each executable profile
replays both families, both retail and SDK paths through the actual Bcd hook,
real file hashing and definition parsing. The original game loader is a stub;
no game code is run. Both baseline sequences permit subsequent shared and
scoped output completion. Unknown hashes and a modified baseline proof reject.
Existing ownership/registration/failure fixtures remain included.

These are offline checks, not live quest acceptance. The sandbox's reserved
address layout prevented the fixed-image fixture process from starting; the
same data-only fixtures were run outside that sandbox. Runtime build output
and the verification log are under local/sdk-baseline-validation, not deployed.

Standalone reporter package: local/Registration Diagnostic v4 (same Manager
application files as v3; only the runtime and two instruction files differ).
Archive: local/Majesty-Mod-Manager-SDK-Script-Fix-v4.zip, SHA256
e81fc1ed919cb1e61ac5047a667461b0466be27724430b9a87463afb83d61dd0.
Runtime SHA256 cd68a2bcd309c634083c2adf63cc66f4cea406081d7404a95276459dfcfc360f.
Archive runtime bytes were compared with the fixture-built DLL; no logs or
dumps are included. No existing installation or merged profile was updated.

## Consulted evidence

Knowledge graph commit f2644580d33ad98703361cd8fc88c825068161ef, README:
the public projection excludes native loading/provider contracts; it cannot
establish this boundary. Research shared-map links dataset-composition.md
(path-token resolver, qualified modified-beta2 scope) and
sdk-bytecode-identities-20261011.md (raw identity only). Local
stock-bcd-ownership.md supplies the existing three-profile BCD reader contract.
Public path-switch evidence above was independently read from the exact
executable; no actor/factory/callback/cleanup research was reopened.
