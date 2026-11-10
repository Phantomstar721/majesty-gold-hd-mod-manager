"""Privatize only the stock resolution-layout filename in the alpha EXE.

The stock formatter, resource loader and layout lifetime stay unchanged.
Canonical QoL utilities always receive the original filename and ordinary
UIData files in a disposable directory; only publication uses the private name.
"""
from ..engine_module import rva_offset
import hashlib
import json
import re

UI_PATCHES=frozenset(('quests-shortcut','lower-tracking','unlock-quests'))
BACKUP_NAME='_custom_quest_button_originals'


def names(name):
    if not re.fullmatch(r'UIData_[0-9]+_[0-9]+\.dat',name,re.I):
        raise ValueError('Unsupported resolution layout filename: '+name)
    return 'UIAlfa'+name[6:]


def rewrite(data,repo_root,branch,*,private):
    if branch is None:raise ValueError('Unsupported alpha UI executable profile')
    contract=json.loads((repo_root/'profiles/panel-engine/alpha-ui-layouts.json').read_bytes())
    if contract.get('schema')!=1:raise ValueError('Unsupported alpha UI filename contract')
    key='gog' if branch.key.startswith('gog') else branch.key
    profile=contract['profiles'][key]
    for frame in profile['callFrames']:
        expected=bytes.fromhex(frame['bytes']);at=rva_offset(data,frame['rva'],len(expected))
        if data[at:at+len(expected)]!=expected:raise ValueError('Stock resolution-layout filename caller changed')
    stock=contract['stock'].encode('ascii')+b'\0'
    alpha=contract['alpha'].encode('ascii')+b'\0'
    if len(stock)!=len(alpha):raise ValueError('Alpha UI filename must retain the native buffer size')
    at=rva_offset(data,profile['literalRva'],len(stock))
    current=data[at:at+len(stock)]
    if current not in (stock,alpha):raise ValueError('Resolution-layout filename is owned by another executable patch')
    result=bytearray(data);result[at:at+len(stock)]=alpha if private else stock
    return bytes(result),current==alpha


def backup_path(source,state_root,branch):
    identity=hashlib.sha256((str(source.resolve()).casefold()+'|'+branch.key).encode()).hexdigest()[:20]
    return state_root/'ui-layout-backups'/identity/BACKUP_NAME
