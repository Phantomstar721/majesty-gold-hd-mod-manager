"""Dataset-scoped XML review using authored snapshots and native load order."""
from dataclasses import replace

from .descriptions import DescriptionsDocument, parse_descriptions, serialize_descriptions
from .description_review import DescriptionReviewCandidate, DescriptionReviewConflict
from .script_review import ScriptReviewCancelled


def native_descriptions(inputs, scope):
    effective = {}
    labels = {}
    for source in inputs:
        owner = source.package.mod_id.strip('{}').casefold()
        labels[owner] = source.name
        for base, payload in source.description_payloads:
            if base not in ('any', 'majesty', 'majestyexpansion'):
                raise ValueError('Unsupported Standard XML dataset: ' + base)
            if base not in ('any', scope):
                continue
            for record in parse_descriptions(payload).records:
                effective[record.key] = (owner, record)
    grouped = {}
    for owner, record in effective.values():
        grouped.setdefault(owner, []).append(record)
    return tuple((owner, DescriptionsDocument('Majesty', (), tuple(records)))
                 for owner, records in grouped.items()), labels


def subset(result, keys):
    document = replace(result.document, records=tuple(r for r in result.document.records if r.key in keys))
    return replace(result, document=document, payload=serialize_descriptions(document),
                   selections=tuple(s for s in result.selections if s.key in keys))


def prepare_description_views(game_path, inventories, inputs, review, resolver, **kwargs):
    from .compose import merge_description_resources, _load_effective_stock_descriptions
    scopes = ('majesty', 'majestyexpansion')
    native = {scope: native_descriptions(inputs, scope) for scope in scopes}
    external_keys = {r.key for variants, _ in native.values() for _, doc in variants
                     for r in doc.records if r.to_element().get('subType') == 'Building'}
    labels = {i.selected.alias: (i.selected.package.mod_id.strip('{}').casefold(),
                               i.selected.package.metadata.display_name) for i in inventories}

    def run(scope):
        variants, names = native[scope]
        stock = {k: v[0] for k, v in _load_effective_stock_descriptions(game_path, scope).items()}
        available = set(stock) | {r.key for _, doc in variants for r in doc.records}

        def resolve(conflict):
            candidates = tuple(DescriptionReviewCandidate(
                labels[c.owner][1] if c.owner in labels else names[c.owner], c.record,
                labels[c.owner][0] if c.owner in labels else c.owner) for c in conflict.candidates)
            first = candidates[0].item.to_element()
            wrapped = DescriptionReviewConflict(scope, conflict.key, first.get('Description') or first.get('Name') or conflict.key[1],
                ', '.join(conflict.fields), conflict.stock, candidates)
            chosen = review.resolve(wrapped)
            # This provisional result only collects remaining review records;
            # it cannot leave this function before every choice is resolved.
            return chosen if chosen is not None else candidates[0].item

        return merge_description_resources(inventories, external_variants=variants,
            conflict_resolver=resolve, stock_records=stock,
            excluded_keys=external_keys - available, **kwargs)

    views = {scope: run(scope) for scope in scopes}
    if review.unresolved:
        if resolver is None:
            review.require_resolved()
        decisions = resolver(review.unresolved)
        if decisions is None:
            raise ScriptReviewCancelled('Mod preferences cancelled; your last completed setup is unchanged.')
        review.apply(decisions)
        views = {scope: run(scope) for scope in scopes}
    left, right = (views[s] for s in scopes)
    common_keys = {k for k, record in left.document.index.items()
                   if k in right.document.index and record._fingerprint == right.document.index[k]._fingerprint}
    common = subset(left, common_keys)
    patches = {scope: subset(views[scope], set(views[scope].document.index) - common_keys)
               for scope in scopes}
    return common, {s: p for s, p in patches.items() if p.document.records}, external_keys
