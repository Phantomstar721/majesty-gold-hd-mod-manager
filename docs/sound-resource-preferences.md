# Sound conflicts and author IDs

Different DSND or WAVE records with the same native four-byte key now enter
the existing preferred-mod review. One mod-pair choice applies across sound,
XML and script conflicts. The chosen complete sound record wins; unrelated
records remain. Identical payloads, unchanged stock copies and earlier records
overridden by the same component do not produce spurious choices. Cancelling
review does not publish a partial profile. The existing preference persistence
also retains sound choices. Reports separate sound decisions from XML decisions.

This is resource composition shared by Public, beta2 and GOG, not a native
runtime hook. It does not automatically privatize sound IDs. Every caller of
the colliding ID sees the winner, which may change the losing mod's audio.

## Avoiding accidental collisions

CAM record labels are 20 bytes, but the named resource merge/native identity
uses the first four bytes. A descriptive suffix, different CAM filename or
different Workshop title does not give the resource a separate namespace.
DSND (sound definitions) and WAVE (audio resources) are separate registries;
authors should inventory both.

For new private sounds, choose a distinctive four-character family prefix/key
scheme, check it against stock resources and commonly combined packages, and
reserve enough suffix space for the whole family. For example, a distinctive
three-character family plus a one-character sequence reduces collisions versus
generic two-letter keys. No example prefix is globally reserved or guaranteed
unique. Keep an inventory of allocated IDs in the source repository.

Renaming must update the actual native key and every dependent reference,
including sound-definition references to WAVE keys and authored consumers of
the sound-definition ID. Changing only the filename or descriptive label is
insufficient. Keep intentional stock overrides at their stock IDs. The Manager
does not guess which references belong to an independently renamed resource.
