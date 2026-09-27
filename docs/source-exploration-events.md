# Source-attributed terrain reveal

Implemented profiles: default Steam 1.5.2.24, Steam beta2 1.5.2.28, and GOG
1.5.2.28. Each has separately verified native addresses and fail-closed hook
validation. Default Steam and GOG still need live acceptance runs, including
native save/load; static executable verification is not a gameplay certification.
Manager owns observation and delivery, not eligibility or rewards.

Example version-3 `mod-definition.json` (replace the UUID):

```json
{
  "schema_version": 3,
  "mod_id": "{YOUR-STABLE-UUID}",
  "internal_name": "ExampleObservation",
  "display_name": "Example Observation",
  "custom_buildings": [],
  "runtime_features": [{
    "type": "stock.gameplay-event-observer.v1",
    "feature_key": "terrain-credit",
    "event": "source-terrain-revealed",
    "callback_symbol": "Example_TerrainRevealed"
  }]
}
```

Supply one `.mmxml` with matching UUID, `Dataset base="Any"`, and a GPL load
with compiled `Target` and every ordered GPL/DAT `Source`. No CAM, art,
Descriptions or dummy resource is required. This actual native dependency
routes the package to Merge; ordinary GPL-only packages stay Standard.
Manager derives `manager.source-exploration.v1`; do not assert it in metadata.
This feature requires Manager preparation and its runtime launcher, not merely
selecting a standalone mod in the stock game.

```gpl
function Example_TerrainRevealed(agent Source, integer Owner,
                                integer NewlyRevealedTiles, integer Epoch)
declare
begin
    // Consumer-owned eligibility and saved accounting.
end
```

The callback has no return value. Source can be any eligible stock revealing
unit, not only heroes. Owner is its credited player (0..7). Tiles is positive
and counts that owner's persistent bits actually changing from zero to one.
Revisits and sharing recipients do not multiply credit. Stock unit movement
activities and successful teleport arrivals are included; direct RevealArea,
whole-map reveal and initial world reconstruction are excluded.

Delivery follows the native update, including birth initialization, never the
map loop. Each consumer gets the same snapshot unless source validity, owner
or epoch changes before its delivery. Callbacks must be bounded, non-yielding,
and must not save/load, delete, retask or transfer the source. Stock reward
calls are permitted; resulting sight increases queue another batch instead
of delivering recursively.

Consumers own saved eligibility, reward remainder, owner and epoch. When
owner **or epoch** changes, discard previous partial credit before adding
the new batch. Owner alone misses an away-and-back transfer. Manager adds no
XP formula, threshold or reward balance.

Pending events and epochs use saved GPL attributes. Delivered events are
removed before synchronous callbacks. Restored pending events are considered
on the first eligible update; loading terrain itself generates none.
Invalid/deleted sources are discarded. Overflow and absent generated service
are errors, not zero counts.

Pending counts and ownership epochs are bounded at 2,097,151, the largest
positive integer representable by GPL's signed 22.10 expression operators.
They are not bounded at the wider native integer-storage maximum: using that
maximum in a GPL comparison/subtraction wraps and rejects even a first small
reveal. Native input validation rejects a larger reveal before passing it to
GPL. The pending limit is per source between deliveries, not lifetime terrain.

No observation hooks install without a selected declaration. When enabled,
work is constant per changed native tile plus GPL bookkeeping per reveal and
consumer work per queued source. No map scan, timer, polling controller or
terrain-history cache is introduced. `MM_EO_*` and `MM_Exploration*_v1` are
Manager internals, not mod APIs. See the [native audit](stock-exploration-attribution-audit.md)
for evidence and outstanding live acceptance checks.
