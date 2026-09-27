# Potion observer: additive stock title registration

The stock `Shapeshift_Potion_Effect` owns the dead-caster guard, timed
effectors, inventory consumption, spell forgetting, form selection and stat
application. `Shapeshift_Potion_End` reverts the unit, selects the corresponding
stat reversal and clamps HP. The potion-consumed observer remains after the
successful stock body; it does not run on the dead-caster return.

Observer validation accepts appended literal titles in an existing stock
`title == "..." || title == "..."` disjunction only when application and expiry
contain the same additions. Existing title order, predicates, application
values, consumption, expiry values and all other stock statements remain
literal. This proof may coexist with the separately audited consume-only early
branches. No package name or private class name is recognized by the validator.

The expiry source is read from the same stock source file already needed for
potion observation. It is validation evidence, not a new generated callback or
runtime hook. This change has no executable-version-specific addresses or
per-frame work. It does not implement a general potion policy schema, persist
spell visibility, or repair save files.
