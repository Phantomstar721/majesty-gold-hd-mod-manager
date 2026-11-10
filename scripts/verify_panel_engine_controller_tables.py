"""Inventory actual primary DialogController vtable spans from RTTI data.

Only initialized PE data and executable-section membership are read. No native
function implementation, constructor, actor callback or factory is followed.
The module uses these measured lengths instead of copying 40 words past every
class table. Unknown or changed tables cannot acquire engine ownership.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from panel_engine_profile_sources import ROOT, BRANCHES
from verify_panel_engine_vtables import read, words, typename, aligned_references, table_data


def controller_tables(pe, anchor):
    root_locator = words(pe, anchor - 4, 1)[0]
    root_descriptor = words(pe, root_locator, 5)[3]
    type_info_table = words(pe, root_descriptor, 1)[0]
    result = {}
    for section in pe.sections:
        if section.Characteristics & 0x20000000 or not section.Characteristics & 0x40:
            continue
        for match in re.finditer(rb'\.\?AV[^\x00]{1,150}@@\x00', section.get_data()):
            descriptor = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + match.start() - 8
            if descriptor % 4 or words(pe, descriptor, 2) != (type_info_table, 0):
                continue
            name = typename(pe, descriptor)
            for reference in aligned_references(pe, descriptor):
                locator = reference - 12
                try:
                    if words(pe, locator, 3) != (0, 0, 0):
                        continue
                    # Reuse the fully bounded hierarchy reader. First obtain
                    # a genuine table reference, then check its type ancestry.
                    for table_reference in aligned_references(pe, locator):
                        address = table_reference + 4
                        data = table_data(pe, address, 9)
                        if data['name'] != name or data['bases'][0]['name'] != name:
                            continue
                        if '.?AVDialogController@@' not in [base['name'] for base in data['bases']]:
                            continue
                        count = 0
                        while count < 128:
                            target = words(pe, address + count * 4, 1)[0]
                            target_section = pe.get_section_by_rva(target - pe.OPTIONAL_HEADER.ImageBase)
                            if target_section is None or not target_section.Characteristics & 0x20000000:
                                break
                            count += 1
                        if not 9 <= count < 128:
                            raise ValueError('Unsupported native controller table length: ' + name)
                        data = table_data(pe, address, count)
                        data['entryCount'] = count
                        if address in result and result[address] != data:
                            raise ValueError('Conflicting native controller RTTI table')
                        result[address] = data
                except (ValueError, UnicodeError):
                    # A raw descriptor reference is not itself a COL/table.
                    # Only complete validated chains enter the inventory.
                    continue
    if not result:
        raise ValueError('No qualified stock controller tables found')
    return sorted(result.values(), key=lambda row: row['va'])


def verify(fixtures):
    import pefile
    anchors = json.loads((ROOT / 'profiles/panel-engine/vtables.json').read_bytes())['profiles']
    result = {}
    for branch in BRANCHES:
        raw = fixtures[branch].read_bytes()
        if hashlib.sha256(raw).hexdigest() != anchors[branch]['fixtureSha256']:
            raise ValueError('Unsupported/changed controller-table fixture: ' + branch)
        pe = pefile.PE(data=raw)
        tables = controller_tables(pe, anchors[branch]['classes']['statsWindow']['va'])
        for known in ('statsWindow', 'basicBuilding', 'unitList'):
            matches = [row for row in tables if row['va'] == anchors[branch]['classes'][known]['va']]
            if len(matches) != 1:
                raise ValueError('Known SDK controller missing from measured table inventory: ' + known)
        result[branch] = {'fixtureSha256': anchors[branch]['fixtureSha256'], 'tables': tables,
                          'maximumEntries': max(row['entryCount'] for row in tables)}
    return {'schema': 1, 'contract': 'panel-engine.native-controller-table-spans.v1',
        'sources': ['x86 MSVC complete-object locators/type hierarchies', 'profiles/panel-engine/vtables.json'],
        'limits': 'Primary data table spans/ancestry only, not a native method or actor lifecycle proof.',
        'profiles': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify({branch: Path(os.environ['MAJESTY_' + branch.upper() + '_EXE']) for branch in BRANCHES})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
