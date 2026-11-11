"""Private controller handoff only; no author protocol or gameplay replacement."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def adapt(source):
    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Pinned engine handoff anchor changed: ' + old[:70])
        source = source.replace(old, new)
    replace('int count=MMWE_VtableLength(vt); if(count<9 || count>VT_COPY_SLOTS)',
            'unsigned managedCount=0; void* locator=0;\n'
            '        int managed=MMWE_ManagedTable(vt,&managedCount,&locator);\n'
            '        int count=managed ? (int)managedCount : MMWE_VtableLength(vt); if(count<9 || count>VT_COPY_SLOTS)')
    replace('for (int i=0;i<=count;++i) c->vt[i]=vt[i-1];',
            'c->vt[0]=managed ? locator : vt[-1];\n'
            '        for (int i=0;i<count;++i) c->vt[i+1]=vt[i];')
    replace('    p = put_str(p, " controller ");',
            '    if (ctrl && has_lines(ctrl)) MMWE_Capture(ctrl,view,unit);\n'
            '    p = put_str(p, " controller ");')
    replace('        if (has_lines(ctrl))\n            p = put_str(p, wrap(ctrl) ? " -> behaviour lines found, wrapped" : " -> behaviour lines found, NOT wrapped (class table full)");',
            '        if (has_lines(ctrl)) {\n'
            '            if (!wrap(ctrl) || !MMWE_Wrapped(ctrl)) return 0;\n'
            '            p = put_str(p," -> behaviour lines found, wrapped");\n'
            '        }')
    declarations = ('#include ' + json.dumps((ROOT/'runtime/PanelEngineHandoff.h').as_posix()) + '\n'
                    'static int MMWE_ManagedTable(void**,unsigned*,void**);\n'
                    'static void MMWE_Capture(void*,void*,void*);\n'
                    'static int MMWE_Wrapped(void*);\n')
    return declarations + source + '\n#include ' + json.dumps((ROOT/'runtime/PanelEngineHandoffSdk.inl').as_posix()) + '\n'
