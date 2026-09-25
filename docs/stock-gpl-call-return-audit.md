# Stock GPL call return ABI

2026-09-23, Steam beta2 static trace and disposable compiler fixtures.

## External occupant/list action

The native command executor substitutes the action name at `4C6031`, creates
an evaluator through `5797B0`, adds the native subject at `4C6065`, then
executes at `4C606E -> 5798F0`. Base evaluator constructor `579670` seeds its
result list with integer zero at `5796B6..5796BF -> 592850`. Integer assignment
`59A5D0` requests source virtual+60 (integer conversion), matching the captured
boolean-to-int exception. This happens even though the command caller does not
subsequently use the value.

The Manager's published occupant/list action contract is boolean. Preserve it
by generating a private integer-returning GPL adapter which calls the statically
named boolean callback exactly once and explicitly returns 1 or 0. The generated
controller registry points to the adapter, not the original callback. Cost,
payment, queuing, subject selection and stock command execution remain unchanged.
Both the adapter's literal body and the original callback's boolean signature
are checked in generated-package validation. No native VM patch is involved.

Existing prepared packages must be regenerated to acquire this adapter. The
feature is implemented in source; an older test executable/profile is not
updated by these edits alone.

## Dynamic function-value calls

Disposable stock-compiler fixtures in `local/dynamic-return-fixture` compare
direct return, comparison to False, assignment into a boolean local, and
explicit initialization of that local before assignment. All compile opcode
0x26 with the same undefined/null result operand (serialized type 0x0B).
The boolean local declaration is serialized type 0x06, but its assignment
follows the dynamic call and does not type the call's temporary.

The observed runtime NULL-assignment failure is consistent with that output.
At `56AAA0`, assignment to a NULL destination rejects a non-NULL source; the
throw originates at `56AACA` and returns to `56AACF`. Changing the local alone
is therefore not a supported fix. The fixture reader parses this limited
instruction stream for comparison, not a general-purpose BCD decoder.

A static named call uses stock linking against a known function signature.
Following explicit user approval, the metadata-driven composition contract
is implemented in [typed-provider-dispatch.md](typed-provider-dispatch.md).
It preserves caller missing/invalid guards and returns False defensively for
unexpected unmatched functions, while validating selected source bindings.
No interpreter patch or mod-identity-based policy is used.
