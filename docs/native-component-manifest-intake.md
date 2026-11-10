# Native alpha component intake diagnosis

2026-11-09; requested through Mod Compatibility chat
`01a1b6a1-6424-78c1-97e2-0117e1938b04`. Investigation only. No Manager profile,
game process, package deployment, native hook or beta/Workshop output changed.

## Current finding

The game never registered the local native guild component. Its absence from
the build menu precedes building availability checks and panel construction.
Its projected GUID being on disk did not prove native registration/activation.

Read-only capture used the existing `read_public_hero.Process` mechanism, only
QUERY_LIMITED_INFORMATION|VM_READ. PID46700 image is the Public alpha EXE,
SHA256 `3cea8305f11370658b544986bc6602b0ac837ef1eacabfbb3b6ac9f57e6e5410`.
The loaded PE header was pinned to that exact image. The Public profile's
installed and Active sentinels and node/GUID fields are independently documented
in Remember Active Mods `docs/STOCK-LIFECYCLE.md` and the currently validated
`runtime/LargeModList.h/.inl`; no beta address was carried into Public.
Capture bounded both lists at256, checked backlinks/stable anchors and Active
membership in installed pointers, and read the alpha-owned .mpst filename.
It did not scan actors or call game functions. It is not an atomic snapshot.

Private receipt: `local/panel-engine-alpha/native-guild-mod-registry.json`.
The target GUID `5B96369F-2723-5DE9-9B95-30677D73744A` is absent from both
installed and Active. All eight other projected GUIDs are Active, including
all three generated components. The actual .mpst preference filename is the
correct alpha-local path. Thus neither projection isolation nor a prerequisite
is the demonstrated failing boundary. Original author component is registered.

## Serialization difference and supported repair candidate

The adaptation's manifest begins with an XML declaration containing
`encoding='utf-8'`. Its source builder explicitly uses `xml_declaration=True`.
The author's manifest and the generated Manager manifest have no declaration.
All34 distinct cached mod manifests without prologs occur in the captured
native installed registry; all3 with encoding prologs do not. This census is
correlation, not a new execution trace of the native parser.

Existing primary `research/docs/preference-xml.md` recovers the shared CyXml
file/buffer/document chain 6A3570->6A33C0->6A3320 on modified beta2. Its encoding
scanner returns AL1 for utf-8 and the caller's JNE6A1DD2 enters the XML error
path. Single/double quote delimiters are supported; this is not a quote-style
bug, nor proof that every XML declaration fails. Version-only declarations
are a separate accepted path. That map alone is not a Public/GOG address or
whole-loader proof. Current Public registration evidence and the exact
serializer-added declaration support removing only the declaration as the
next bounded repair, matching the author's established manifest shape.

Review-only candidate and byte/tree receipt:
`local/panel-engine-alpha/native-manifest-preview`. Only the leading XML
declaration/newline is removed; the complete remaining bytes and parsed tree,
GUID, Dataset, paths, descriptions, scripts and artwork stay unchanged. The
candidate is not deployed. The package owner must fix its own builder to emit
declaration-free UTF-8 without BOM, retain an explicit serialized-byte check,
and validate/deploy under the user's approved workflow. No unit-enable hook,
scope Any rewrite, BDEP insertion or panel-engine patch addresses this intake
failure. A fresh native catalogue after the authorized next restart must
confirm that the corrected GUID is installed/Active; no live refresh is assumed.

## Evidence consultation and limits

Graph commit `f2644580d33ad98703361cd8fc88c825068161ef`, README and
`mechanic.module-load-order` qualified source/order records consulted. Shared
map20261 and existing `dataset-application.md`, `dataset-composition.md`,
`catalog-predicate.md`, `kingdom-availability.md`, `unit-prerequisites.md`,
native mod-catalogue family19315 and XML input/declaration/name/value maps were
read. The native catalogue C recovery leaves helper/ABI/loading limits intact.
Missing BDEP permits only the mapped expression predicate; it does not establish
every build-menu gate. No actor callback, factory, cleanup, VM or error-runtime
implementation was reopened. The old Documents err.log is from October13 and
cannot establish the current quest or native resource-load sequence.

## Delivery boundary

Automatic approval review rejected sending the concrete package-owner repair
request to Mod Compatibility, stating that recipient/package-change permission
was not clear beyond the prior Witch Hunter coordination approval. No message
was delivered, alternate route attempted or owner repository changed. Explicit
user permission for that recipient's package correction/deployment is needed
before resending. The review-only candidate and unaffected diagnostics are
complete and available for review here.

The user subsequently answered **"Yes, send it and update the local package"**
to the exact recipient/builder/local-package question in this canonical chat.
The same scoped repair was then delivered successfully through
`mcp__codex_app__send_message_to_thread`; returned recipient ID
`01a1b6a1-6424-78c1-97e2-0117e1938b04`. This supersedes the pending-permission
status above. Recipient owns the builder, serialization regression and
manifest-only local deployment; receiving-side byte verification remains here.

## Local correction received

The owner completed builder/regression and manifest-only deployment. Deployed
manifest SHA256 is
`9f8f58eeedf85e2e6e86a0e2e8eb35d1653af7403ade1f07b5d189b698662d8b`, exactly
matching the review candidate. Independently compared every gameplay CAM/BCD,
Descriptions/Strings XML and the two GPL/DAT sources against the immutable
author snapshot; bytes match. Owner's `manifest-header-fix-receipt.json` records
all non-manifest hashes, sizes and mtimes unchanged in canonical/dist and
Documents roots. Builder uses `xml_declaration=False`; its disposable
`tests/test_native_manifest.py` covers the serialized-byte rule and LF/CRLF
formatting alternatives, without relaxing actual deployment body preservation.
Receiving receipt: `local/panel-engine-alpha/native-guild-deployment-verification.json`.

No Manager code or application update was needed for this package repair. Live
registration remains pending a user-operated fresh launch. The Standard-input
fingerprint includes its manifest, so Rescan followed by the user's Prepare is
the appropriate combined-profile refresh before that launch. No agent rebuilds
the user's merged output or performs a live catalogue reload.
