# Mod Manager runtime capability manifest

The injected runtime no longer infers package features from the presence of an
activity-text registry. The Mod Manager writes an explicit capability manifest
for every launch and publishes its absolute path through
`MAJESTY_MOD_MANAGER_CAPABILITIES`.

That environment variable is the launcher's authoritative manager marker. The
launcher starts Majesty suspended and releases it only after the DLL validates
the complete manifest, validates the selected public or beta2 executable
profile, installs only the declared hook groups, and signals the existing ready
event. A missing file, relative or non-canonical path, malformed record,
unsupported capability, profile mismatch, or failed required install terminates
the suspended process before a game can load. Injecting the DLL with no MMCP
environment variable installs no optional hook.

## MMCP v1

All integers are little-endian.

```text
4 bytes  magic "MMCP"
u32      schema version (1)
u32      capability count (0..64)
repeat count times:
  u32    capability byte length (1..128)
  bytes  lowercase ASCII capability name
```

Names use the same dotted, lowercase segments accepted by manager package
definitions. Records must be strictly increasing by their raw ASCII bytes, so
duplicates are invalid. The parser rejects trailing bytes and files larger than
64 KiB. The runtime also rejects a well-formed capability it does not support;
an older DLL therefore cannot silently run a package that needs a newer hook.

## Capability-to-hook ownership

| Capability | Runtime behavior |
|---|---|
| `expanded-building-slots.cg-prefix` | Validates and installs only the generic stock unknown-dialog `CG` prefix fallback. |
| `freestyle-cam-rebind.v1` | Installs only the generic Freestyle CAM lifecycle repair. |
| `private-activity-text-registry.v1` | Requires a valid, non-empty MMTX file and installs only the shared stock activity-text resolver extension. |
| `generic-visitor-lists.v1` | Accepted marker for the external CAM data patch; installs no executable hook. |
| `alchemist.cgbrewing-secondary-controller` | Installs the Laboratory's AP10/AP99 research, Vigor, reagent-spell, Rage, dialog, secondary-controller, game-update, and window-lifecycle stock clones. |
| `alchemist.ap78-private-oil-rows` | Installs only the scoped AP78 private oil-row extension. |
| `alchemist.nm18-name-generator` | Installs only the private NM18 extension at the stock name-registry completion boundary. |
| `phantom.nm19-name-generator` | Installs only the private NM19 extension at the same stock name-registry completion boundary. |

A Haunt-only or otherwise generic profile cannot enter an Alchemist installer:
the Alchemist calls exist only inside their respective capability branches.
Conversely, selecting Alchemist declares its three independent capabilities,
so each stock-cloned group remains separately validated and fail-closed.

The MMCP parser has a standalone C++ test covering empty, Haunt-only, combined,
unknown, unsorted, duplicate, truncated, and trailing-byte manifests.
`Test-RuntimeBuild.ps1` additionally extracts `InitializeRuntime` and proves
that every optional installer call occurs exactly once and only inside the
expected capability guard.
