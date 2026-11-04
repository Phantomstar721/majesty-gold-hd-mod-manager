# Native targeted-missile interception

`stock.projectile-interception.v1` declares a two-agent Boolean GPL provider and
classifies projectile callbacks. It operates at the actual stock terminal missile
impact, not by adding guards to individual damage scripts. This interface is
implemented in the shared runtime. Offline profile verification and live
gameplay acceptance remain separate evidence.

Required declaration fields:

- `type`: `stock.projectile-interception.v1`
- `feature_key`: unique feature identifier
- `callback_symbol`: package-authored `function Decide(agent Source, agent Target) is boolean`
- `direct_projectile_callbacks`: included hit callbacks
- `physical_projectile_callbacks`: excluded physical callbacks
- `area_or_periodic_projectile_callbacks`: excluded area/periodic callbacks
- `other_exempt_projectile_callbacks`: excluded return/cosmetic/other callbacks

Callback names cannot appear in multiple classifications. Unknown carriers stay
on the original game path. A matching callback alone is insufficient: effective
projectile descriptor, ID, native script shape and actual terminal dispatch must
also agree. No per-projectile source replacement or per-unit polling is emitted.

The generated ownership proof protects the declared Boolean provider, which
must exist in both effective game datasets. Classifying a hit callback does not
claim ownership of its script body. Ordinary stock and mod hit scripts keep
native load precedence, even if they also appear in generated output. Native
API names and explicitly required observer/placement callbacks remain protected
when those separate capabilities are selected. A required callback missing from
either effective dataset is rejected during preparation. Updating the Manager
requires Prepare Again to regenerate this ownership information; a DLL swap
alone does not change an existing proof.

True absorbs the **entire** hit callback, including any secondary effect it would
have created, then uses stock missile completion/removal. False preserves the
captured original game override, including Magic Mirror. Existing area effects
are not retroactively cancelled. Physical damage policy is a separate feature.

Providers execute synchronously, Source then Target, and must remain bounded.
They may record their own cooldown and create callback-free cosmetic feedback;
they must not destroy or replace the current projectile, dispatch order or world.
Providers are ordered by their generated binding identity, run once each, and
stop at the first true result. A failed/invalid invocation is not a false result
and cannot safely be retried after side effects.

The Manager derives `manager.projectile-interception.v1` plus the shared loaded
script/world service. Mods do not supply native addresses, executable hashes or
runtime binaries. Output evidence is generated from current prepared inputs;
there are no pinned whole-mod source fingerprints.

Native admission supports default Steam 1.5.2.24, Steam beta2 1.5.2.28 and
GOG 1.5.2.28 through their verified profiles and consumed-code checks. An
unrelated executable change does not by itself invalidate this capability;
changes to required native code still fail admission.
