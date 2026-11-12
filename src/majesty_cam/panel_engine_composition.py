"""Owner-scoped WE1 relocation within the normal named-resource merge.

Only loaded SMNU/STRT pairs participate. Preferred-mod selection supplies the
winning owner before relocation. Ordinary text, row IDs, callback names and
image keys remain byte-identical unless the corresponding typed map says
otherwise. No additional controller or mod-specific replacement is generated.
"""
from dataclasses import replace

from .panel_engine import rewrite_table
from .panel_engine import PanelEngineError


def validate_script_panel_references(parsed_by_owner, dialog_renames):
    """Reject an actual unsafe GPL/window namespace crossing, not arbitrary text.

    WE records have a proven typed relocation contract. GPL strings do not:
    they can be computed or consumed by an authored function with that name.
    Do not silently send SF_SetWindow to another owner's former panel ID.
    """
    from .gpl import DefinitionKind
    from .gpl_function_merge import _tokens
    renamed = {}
    for owner, old, new in dialog_renames:
        if old != new:
            renamed.setdefault(owner,set()).add(old.decode('latin1'))
    for owner,sources in parsed_by_owner.items():
        keys = renamed.get(owner)
        if not keys:
            continue
        items = [item for source in sources for item in source.items]
        if any(item.key == (DefinitionKind.FUNCTION,'sf_setwindow') for item in items):
            continue  # An authored implementation is not a typed native call.
        for item in items:
            if '$sf_setwindow' not in item.text.casefold():
                continue
            tokens = _tokens(item.text)
            for index,token in enumerate(tokens):
                if token != '$sf_setwindow' or tokens[index+1:index+2] != ('(',):
                    continue
                depth=1; arguments=[[]]
                for value in tokens[index+2:]:
                    if value in ('(', '[', '{'):depth+=1
                    elif value in (')', ']', '}'):
                        depth-=1
                        if depth==0:break
                    if value==',' and depth==1:arguments.append([])
                    else:arguments[-1].append(value)
                target=arguments[1] if depth==0 and len(arguments)==2 else []
                while len(target)>2 and target[0]=='(' and target[-1]==')':
                    nesting=0; enclosed=True
                    for offset,value in enumerate(target):
                        if value=='(':nesting+=1
                        elif value==')':nesting-=1
                        if nesting==0 and offset<len(target)-1:enclosed=False;break
                    if not enclosed:break
                    target=target[1:-1]
                if len(target)==1 and target[0].startswith('"') and '\\' not in target[0]:
                    if target[0][1:-1] not in keys:
                        continue
                    detail='targets renamed panel '+target[0]
                else:
                    detail='uses a computed window ID while panels '+', '.join(sorted(keys))+' are being renamed'
                raise PanelEngineError(owner+': SF_SetWindow '+detail+
                    '; GPL window-ID relocation is not proven for this namespace change. '
                    'Use nonconflicting panel IDs for this combination.')


def text_relocator(resources, dialog_renames):
    pairs = {(resource.owner, resource.key) for resource in resources if resource.section == b'SMNU'}
    maps = {}
    for owner, old, new in dialog_renames:
        maps.setdefault(owner, {})[old.decode('latin1')] = new.decode('latin1')

    def relocate(owner, native_key, entry):
        if (owner, native_key) not in pairs or owner not in maps:
            return entry
        data = rewrite_table(entry.data, panels=maps[owner])
        return entry if data == entry.data else replace(entry, data=data)

    return relocate
