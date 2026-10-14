# XML overrides and shared mod preferences

Existing building Descriptions are not declarations of new custom buildings.
Catalog admission defers an undeclared, non-stock building's provider check;
composition still requires a selected native building provider or the existing
private-building declaration. Declared runtime controller evidence is unchanged.

Standard manifest XML is snapshotted alongside GPL input, including XML-only
components. Later native components/loads win before comparison. Only keys also
supplied by Merge inputs enter generated output; unrelated Standard records stay
native. Stock-relative independent XML fields combine through the existing field
merger. Divergent additions or incompatible fields use the existing mod-pair
preferences, including cycle checks and multi-party conflict handling. XML and
GPL use the same normalized Mod IDs and persisted preference map.

Original and expansion views are resolved separately. An override of a building
provided only in the other scope is not emitted there. Identical records share
the common native Mod; differing records use dataset-specific XML load directives
in the existing scoped native Mod IDs, without dummy GPL. Generated validation
reparses those directives and checks each effective runtime evidence view.

Review is completed before XML output is used for composition. If later script
analysis finds additional pairs, only unresolved pairs are requested; earlier
XML choices cannot be silently revised after their result was consumed. Cancel
occurs before profile publication. No mod names, Workshop IDs or building names
select these rules.

Reference: the existing typed Description field merger, manifest parser and
native dataset-scoped output contracts; research shared-map.xml-child-access
documents exact child lookup and duplicate ordering, not a new runtime hook.
Tests cover native ordering, XML-only input invalidation, original/expansion
separation, selected-provider admission, native XML-only manifests, shared
GPL/XML decisions, independent fields, three-party choices, cycles and cancel.

The author's actual patch is optional additional reproduction evidence, not a
prerequisite to the generic implementation. Fixture coverage is not an assertion
that an unseen package's particular resources have passed admission or gameplay.

The installed Standard component manifests and XML snapshots were also read
without preparing a profile. Three synthetic building overrides over the actual
building document exercise either preferred-mod choice. Inter-record `//` line
comments are accepted as container comments, never stripped from attribute
values or Description payloads. XML entities, duplicate record keys, malformed
documents and unexpected non-comment container text remain rejected.
