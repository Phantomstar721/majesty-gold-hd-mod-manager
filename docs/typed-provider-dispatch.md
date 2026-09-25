# Typed boolean provider dispatch

Optional composition declarations avoid the stock compiler's untyped result
temporary for calls through a function-valued attribute. This service generates
ordinary GPL, not a VM hook, runtime scan, polling service or mod-specific policy.
Both parties retain ownership of their gameplay behavior.

## Provider declaration

Add to a version-3 definition's `runtime_features`:

```json
{
  "type": "stock.typed-boolean-provider.v1",
  "feature_key": "support_provider",
  "attribute": "ExampleSupportEligible",
  "parameter_types": ["agent", "agent"],
  "callback_symbol": "Example_Support_Eligible"
}
```

The callback must be exactly one package-owned function with that parameter
order and `is boolean`. Keep the existing literal function binding in its
DAT record or GPL assignment/AddAttribute call. Do not add a native capability.

## Consumer declaration and call

```json
{
  "type": "stock.typed-boolean-dispatch.v1",
  "feature_key": "support_dispatch",
  "attribute": "ExampleSupportEligible",
  "parameter_types": ["agent", "agent"],
  "dispatch_symbol": "Example_Dispatch_Support"
}
```

Do not author the generated function. Keep the consumer's HasAttribute and
validfunction checks and all missing/invalid-provider defaults. Replace only
the valid dynamic invocation with:

```gpl
$Example_Dispatch_Support(Hero's "ExampleSupportEligible", Hero, Target)
```

Generated signature: `(function Provider, agent Arg0, agent Arg1) is boolean`.
For each selected declared provider, Manager emits stock function comparison
`Provider == $Callback`, followed by a static `$Callback(Arg0, Arg1)` call.
The actual provider result is returned unchanged. An unexpected unmatched
function returns False defensively; this is not a replacement for consumer
missing-provider policy. No arbitrary dynamic call is attempted.

The attribute name is the contract key. It is not a hardcoded list: other
boolean contracts can declare different attributes and 1..8 parameters drawn
from `agent`, `string`, `integer`, `boolean`, `location`, and `list`.
All declarations for one attribute must agree on the ordered signature.

Preparation rejects duplicate/cross-package callback ownership, signature
disagreements, generated-symbol collisions, and recognized literal attribute
installations pointing to undeclared providers. Computed targets at those
sites are rejected rather than guessed. DAT initializers, GPL attribute
assignments and AddAttribute function initializers are checked across selected
source packages, even those without declarations. Providers must use literal
attribute names and direct function-symbol bindings; runtime-computed names or
restored state from a different mod selection cannot be exhaustively inferred
from source declarations.

Stock function comparison is already used by stock spell/follower code, such
as `mx_Spells.gpl`'s ActiveScript/BackScript checks against `$use_building_safe`.
Static calls use the named function's normal stock linking path. Compiler-only
fixtures establish that assignment to a typed local does **not** repair a
dynamic call temporary; see [the return-ABI audit](stock-gpl-call-return-audit.md).

This is source-composition support, not new save state or native installation.
Updated consumer/provider packages and a rebuilt Manager are required before
the user prepares a new combined package. No existing user profile is rewritten
as part of implementing or testing this service.
