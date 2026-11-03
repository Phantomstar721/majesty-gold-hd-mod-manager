"""Preserve native quest-scoped Description loads without runtime dispatch."""
from dataclasses import replace
from .descriptions import DescriptionsDocument, parse_descriptions, merge_descriptions
from .scoped_output import SCOPES
from .package import DescriptionsLoad


def document(records):
    return DescriptionsDocument('Majesty', (), tuple(records), '<quest-scoped descriptions>')


def inventory_view(inventory, scope):
    paths = (*inventory.descriptions,
        *(path for selected, path in inventory.scoped_descriptions if selected == scope))
    package = getattr(inventory.selected, 'package', None)
    if package is not None:
        # Preserve actual manifest order, including a later Any load. Filtering
        # by inventory paths retains caller-side exclusions/compatibility input.
        allowed = set(paths)
        ordered = tuple(d.file.absolute_path for dataset in package.datasets
            if dataset.base.casefold() in ('any', scope.casefold())
            for load in dataset.loads for d in load.directives
            if isinstance(d, DescriptionsLoad) and d.file.absolute_path in allowed)
        paths = (*ordered, *(path for path in paths if path not in ordered))
    return replace(inventory, descriptions=paths)


def build_views(inventories, shared_before, shared_after, stock_views):
    """Resolve only scoped keys, retaining per-component last-load precedence.

    Shared Manager transformations are rebased as independent edits, not copied
    wholesale over a scope's spell lists or other stock gameplay fields.
    Unresolvable edits remain an ordinary Description conflict.
    """
    output = {}
    for scope in SCOPES:
        keys = {key for inv in inventories for selected, path in inv.scoped_descriptions
                if selected == scope for key in parse_descriptions(path.read_bytes(), source=str(path)).index}
        if not keys:
            continue
        variants = []
        for inv in inventories:
            records = {}
            for path in inventory_view(inv, scope).descriptions:
                records.update((key, record) for key, record in
                    parse_descriptions(path.read_bytes(), source=str(path)).index.items() if key in keys)
            if records:
                variants.append((inv.selected.alias, document(records.values())))
        selected = merge_descriptions(document(()), variants, field_merge_stock=stock_views[scope]).document
        changed = [record for key, record in shared_after.index.items()
                   if key in keys and key in shared_before.index and record._fingerprint != shared_before.index[key]._fingerprint]
        if changed:
            baseline = dict(stock_views[scope]); baseline.update(shared_before.index)
            selected = merge_descriptions(document(()),
                ((scope, selected), ('Manager generated changes', document(changed))),
                field_merge_stock=baseline).document
        output[scope] = selected
    return output


def effective_records(shared, patch):
    records = dict(shared)
    if patch is not None:
        records.update(patch.index)
    return records


def inventory_records(inventory):
    # Reuse the content-keyed parser: bytes are still read on every call, so
    # same-size edits (including preserved timestamps) cannot return stale XML.
    from .compose import _parse_description_file
    records = {}
    for path in inventory.descriptions:
        records.update(_parse_description_file(path).index)
    return records
