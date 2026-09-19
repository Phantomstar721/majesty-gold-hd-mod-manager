# Stock-value equipment (local beta2 trial)

`stock.equipment.v1` registers a private weapon or armor identity while keeping
Majesty's stock buying, research, ranks, bonuses, numeric display, and save
attributes. This is a beta2 1.5.2.28 test feature, not a claim of public-branch
or completed in-game validation. Unverified executables fail closed.

Add one record per equipment identity to schema-3 `runtime_features`:

```json
{
  "type": "stock.equipment.v1",
  "feature_key": "field-blade",
  "slot": "weapon",
  "name_table": "ZN01",
  "image_id": "ZI01",
  "image_set": 1004,
  "hero_ids": ["ZH01"]
}
```

- `feature_key`: stable lowercase key, beginning with a letter, then letters,
  digits or hyphens; at most 64 characters. Never reuse a removed key for a
  different saved identity. Identity derives from this key and the package UUID,
  not its display name, selection order, or another mod's presence. A hash
  collision is an error, never a reason to silently reassign an existing ID.
- `slot`: `weapon` or `armor`. A character can have one assignment per slot.
- `hero_ids`: 1–256 distinct package-owned `Unit/Character` FourCCs. Their
  `Game/WeaponBasicDamage` or `ArmorBasicDamage` remains the sole base-value
  source. Include a normal stock `AllowedWeapon`/`AllowedArmor` field; the
  Manager replaces that field in the generated copy with its registered enum.
  No new spell-bonus API or extra base-value field is required.
- `name_table`: private CAM STRT FourCC, not stock EN01–EN15. Supply 4–64
  nonempty entries with IDs 0 through N−1, ordered by structural rank. Each
  name may use at most 128 bytes. Stock appends the numeric bonus display and
  clamps names above the supplied count to the final entry.
- `image_id` and `image_set`: private IMAG FourCC and unlayered set ID in the
  package's stock-interface-derived art CAM. Clone stock INBw/1004 or INBa/1000:
  a coherent Original/version-3 or MX/version-4 image header and set layout;
  one direction and four frames; four native 23×23,
  type-1 TILEs with embedded palettes. Preserve the stock set body; replace
  only its frame TILE references and artwork. This is not a PNG path.
  The Manager relocates the art first, then clones the destination's stock
  equipment set layout and substitutes those four TILE references under the
  private identity. Original sets contain 116 bytes; MX sets contain 124 bytes.
  Mixing either set body with the other container version is invalid.
  Do not author replacements for
  INBw/INBa yourself. Equipment names and image keys must not be supplied by a
  second selected package.

The native four-frame image returns to frame **0** at structural ranks above
3. It does not clamp or discard the character's actual bonuses. Additional
names can describe those higher ranks, but this contract does not add image
frames, enchantment-specific artwork, prices, research gates, or arbitrary
per-tier bonuses. Those are different behavior changes, not stock values.

Ship the declared CAMs and character Descriptions through the normal package
manifest. Ship no private DLL or Manager-generated registry. Prepare through
the Manager, then use the Manager to launch; directly enabling a source package
does not install the native registrations. Keep the same prepared mod set for
saved games. This does not provide migration for removed equipment or changed
package identities.

Weapon bonus for an explicitly intended GPL consumer is already available as
`$GetAttribute(agent, #ATTRIB_Weapon_Struct_Bonus) +
$GetAttribute(agent, #ATTRIB_Weapon_Magic_Bonus)`. Using this in a spell is a mod
decision; the Manager never applies it globally. Base damage, coatings, poison,
and confirmed-hit effects are not changed by registering equipment.

Before releasing a package, exercise both slots, shop and enchantment updates,
above-shop ranks, save/reload with an unchanged profile, and return-to-menu /
second-game resource reconstruction. See the [stock audit](stock-custom-equipment-audit.md)
for native ownership and cleanup evidence.
