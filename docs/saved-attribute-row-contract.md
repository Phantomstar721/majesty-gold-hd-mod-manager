# Saved fitting presentation row

The reusable recipe is `stock.ap78-saved-attribute-row.v1`. It requires MMFR10
and the existing derived `stock.ap78-info-row.v1` runtime capability. Older MMFR
formats and existing passive/spell/effect recipes retain their encoding.

```json
{
  "type": "stock.ap78-saved-attribute-row.v1",
  "feature_key": "private-owned-fitting",
  "attribute_symbol": "Private_Fitting",
  "display_text": "Owned fitting",
  "tooltip_text": "Description of the fitting actually carried.",
  "image_id": "PF01",
  "image_set": 1019
}
```

These are the exact fields. Attribute names must be GPL identifiers of 1..64
ASCII bytes. Feature keys use the existing lowercase/hyphen key grammar.
Display/tooltip text and private 24x24 IMAG/TILE ownership follow the existing
AP78 information-row rules. A private stock-derived placeholder image is allowed.
There is no subject ID, unlock level, condition callback or gameplay grant.

At each stock learned-list refresh the adapter resolves the current selected
hero anew, rejects dead/removing/zero-HP units, resolves its current saved GPL
agent, checks deleted state, and invokes stock HasAttribute. Missing returns
false before the required getter is invoked. Existing values display only when
the concrete GPL type tag is integer 1 and its signed payload is greater than 0.
Zero, negative, boolean, float, missing, unknown or deleted values produce no row.
Stock heroes and private heroes are equally eligible; no private-character
ownership declaration is fabricated. Reopening/loading reads authoritative saved
state again. A consumed dose at 0 disappears on the next ordinary stock refresh.

The existing AP78 native append, image copy, tooltip and row/string cleanup own
presentation. No attribute insertion/write, GPL callback, inventory item, fake
learned spell, effector, timer or cached selected-agent pointer is introduced.

## Verified native boundary

Public Steam / beta2 / GOG required getters:
`5616A0 /5777D0 /576AD0`; separate HasAttribute:
`5617B0 /5778E0 /576BE0` (VAs, base 400000). Existence is a thiscall taking one
borrowed native-string pointer and returning bool in AL, RET 4. It calls the stock
find operation and compares its returned iterator with the property-map sentinel.
The lower-bound/find helpers only traverse/compare existing nodes; no insert,
value acquisition or callback occurs. The required getter is reached only on a
hit, with the same saved agent and borrowed key; no gameplay callback intervenes.
The key's narrow string flags are 0 and its immutable registry text outlives the
synchronous lookup. The temporary native 16-byte agent reference is constructed
and destroyed in the stock order. Its +0C cache is local, never written into hero
state. Integer constructors/type stores and read-payload getters were checked
independently using the actual GplInteger RTTI/vtable in all three profiles.

`runtime/SavedAttributeProfiles.h` guards the component/reference, lookup,
existence/required getter and integer-layout boundaries alongside existing full
AP78 profile guards. Unknown profiles or changed bytes decline installation.
Bounded disassembly and identities are in
`artifacts/saved-attribute-profile-evidence.json` and `artifacts/optional-*.asm`.
These are offline static/fixture evidence, not native gameplay acceptance.
