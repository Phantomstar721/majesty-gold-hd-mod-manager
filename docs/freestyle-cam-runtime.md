# Freestyle custom-CAM runtime

Majesty Mod Manager includes native support for loading compatible custom CAM
content in Freestyle mode across repeated games in the same Majesty process.
The implementation is derived in part from the MIT-licensed
[`Iximi-Ixus/freestyle-cam-sidecar`](https://github.com/Iximi-Ixus/freestyle-cam-sidecar).
Its retained license is available at
[`licenses/FREESTYLE-CAM-SIDECAR.txt`](../licenses/FREESTYLE-CAM-SIDECAR.txt).

## Stock lifecycle

Majesty rebuilds several CAM-backed resource registries while accepting a
Freestyle configuration. Persistent IMAG handles can outlive the registry to
which they were originally bound. Before each proven stock registry use, the
runtime verifies the cached registry and, when necessary, reacquires the
current resource through Majesty's own resource-manager call shape:

- resource type `IMAG`;
- the handle's existing four-character resource ID;
- stock flags `0x80000000`; and
- the stock seven-argument acquisition call.

The refreshed registry is written back to the existing handle before Majesty
continues its unchanged lookup. Nested acquisition of the same resource is
coalesced so its active handles receive the same current registry.

The runtime also preserves the measured stock wrapper lifecycle: valid
assignment performs AddRef, Release, and store in stock order; valid teardown
continues through the original release call. A wrapper is rejected only when
its interface no longer resolves to the executable Majesty methods used by the
stock dispatch.

## Supported executable profiles

Every address is independently identified and byte-checked for both supported
Steam executables. The runtime never derives one profile from a blanket offset.

| Lifecycle site | Public 1.5.2.24 RVA | beta2 1.5.2.28 RVA |
| --- | ---: | ---: |
| Handle use: Random/shared | `0x271FD0` | `0x287430` |
| Handle use: named construction | `0x272030` | `0x287490` |
| Handle frame walk | `0x2728C0` | `0x287D20` |
| Handle grid draw | `0x272450` | `0x2878B0` |
| Grid prescan | `0x27258C` | `0x2879EC` |
| Wrapper cache getter | `0x25C810` | `0x271C70` |
| Load-UI owner destructor | `0x26F1E1` | `0x284641` |
| Stock wrapper assignment | `0x26C740` | `0x281BA0` |
| Release thunk | `0x246950` | `0x25BDB0` |
| Load-UI vtable+8 release 1 | `0x2BDF0A` | `0x2D349A` |
| Load-UI vtable+8 release 2 | `0x2BDF2A` | `0x2D34BA` |
| Resource-manager singleton load | `0x226AC1` | `0x246641` |
| Resource-manager singleton | `0x3C8818` | `0x3E7518` |

Initialization validates the complete selected profile before writing any
hook. If installation cannot complete, every write from that hook group is
rolled back in reverse order and Majesty is not launched with a partial
Freestyle patch.
