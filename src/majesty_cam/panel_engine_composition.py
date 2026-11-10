"""Owner-scoped WE1 relocation within the normal named-resource merge.

Only loaded SMNU/STRT pairs participate. Preferred-mod selection supplies the
winning owner before relocation. Ordinary text, row IDs, callback names and
image keys remain byte-identical unless the corresponding typed map says
otherwise. No additional controller or mod-specific replacement is generated.
"""
from dataclasses import replace

from .panel_engine import rewrite_table


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
