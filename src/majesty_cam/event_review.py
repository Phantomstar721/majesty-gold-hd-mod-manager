"""Preferred-mod choices for native rewrites incompatible with event observers."""
from dataclasses import replace
from uuid import UUID
from .gpl import DefinitionKind, SemanticMergeResult
from .gameplay_events import EVENT_FUNCTIONS, add_gameplay_event_observers
from .shared_features import StockGameplayEventObserver
from .script_review import ScriptCandidate, ScriptConflict
from .gpl_function_merge import FunctionMergeError

def owner_id(binding):
    return str(UUID(binding.mod_id))

def analyze(dataset, result, bindings, stock, providers, labels, review):
    records=[]
    if providers is None or review is None:return records
    events={b.feature.event for b in bindings if isinstance(b.feature,StockGameplayEventObserver)}
    for event in sorted(events):
        names=EVENT_FUNCTIONS[event]
        # Multi-owner events have several independently meaningful sites and
        # continue using their existing composition path.
        if len(names)!=1:continue
        name=names[0]; key=(DefinitionKind.FUNCTION,name)
        native=providers.native_candidate(key)
        if native is None or name not in stock:continue
        if any(c.key==key and c.dataset==dataset for c in review.conflicts):continue
        selected=tuple(b for b in bindings if isinstance(b.feature,StockGameplayEventObserver) and b.feature.event==event)
        base=stock[name]
        def make_combine(native,base,key,event,selected):
            def combine(owners):
                root=native.item if native.owner in owners else base
                callbacks=tuple(b.feature.callback_symbol for b in selected if owner_id(b) in owners)
                if not callbacks:return root
                items=tuple(i for i in result.items if i.key!=key)+(root,)
                try:
                    generated=add_gameplay_event_observers(SemanticMergeResult(items,()),
                        {event:callbacks},stock,source_loader=lambda n:providers.functions((n,)).get((DefinitionKind.FUNCTION,n)))
                except ValueError as exc:raise FunctionMergeError(str(exc)) from exc
                return next(i for i in generated.items if i.key==key)
            return combine
        combine=make_combine(native,base,key,event,selected)
        owners=tuple(sorted({native.owner}|{owner_id(b) for b in selected}))
        try:combine(owners)
        except FunctionMergeError:
            variants=tuple(ScriptCandidate(native.label if owner==native.owner else labels.get(owner,owner),
                combine((owner,)),owner) for owner in owners)
            conflict=ScriptConflict(dataset,key,name,
                'Combat or activity rewards. The preferred mod supplies this behavior; '
                'incompatible reward notifications from the other mod are not applied.',
                base,variants,combine_candidates=combine)
            review.resolve(conflict)
            records.append((conflict,event,native,base))
    return records

def apply(result, bindings, records, review):
    items={i.key:i for i in result.items}; retained=list(bindings)
    for conflict,event,native,base in records:
        owners=review.selected_owners(conflict)
        if owners is None:review.require_resolved()
        items[conflict.key]=native.item if native.owner in owners else base
        retained=[b for b in retained if not isinstance(b.feature,StockGameplayEventObserver)
                  or b.feature.event!=event or owner_id(b) in owners]
    return SemanticMergeResult(tuple(items.values()),result.conflicts),tuple(retained)
