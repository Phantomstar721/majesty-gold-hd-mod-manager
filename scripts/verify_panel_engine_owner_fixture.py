"""Exercise the pinned SDK controller lifecycle with local provider doubles.

This is a native source fixture, not game acceptance or native ABI evidence.
It builds only in the alpha's ignored work directory and never touches payload,
EXE patches, Manager profiles or application output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import os
from build_panel_engine_modules import bounded_class_copy

ROOT = Path(__file__).resolve().parents[1]
SDK_HASH = 'd6049b8021575241027677db2df441cdb50bd0038735c3fda6058b70d1a40b9b'


def verify(sdk, work, handoff=False, candidate_labels=(), updated=False):
    expected_hash = SDK_HASH
    if updated:
        from updated_panel_engine_sources import SOURCE_PINS
        expected_hash = SOURCE_PINS['src/we_engine.cpp']
    if hashlib.sha256(sdk.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('SDK source changed; review the fixture substitutions')
    source = sdk.read_text(encoding='utf8')
    substitutions = []
    def replace(match):
        name, type_name = match.group(1), match.group(2)
        substitutions.append(name)
        return 'static ' + type_name + ' fixture_' + name + ';\n#define ' + name + ' fixture_' + name
    source = re.sub(r'^#define\s+(\w+)\s+\(\((\w+_t)\)0x[0-9a-fA-F]+\)', replace, source, flags=re.M)
    if len(substitutions) != (60 if updated else 56):
        raise ValueError('Native provider inventory changed')
    source, count = re.subn(r'^#define GPL_DEBUGGER_ON .*$', '#define GPL_DEBUGGER_ON 0', source, flags=re.M)
    if count != 1:
        raise ValueError('SDK logging gate changed')
    source=bounded_class_copy(source,17,76)
    source='static int MMWE_VtableLength(void**);\n'+source
    if updated:
        source = '#define MMM_UPDATED_SDK_FIXTURE 1\nstatic void runUpdatedFixture();\n'+source
    if handoff:
        from panel_engine_handoff_source import adapt
        source = adapt(source)
        source = '#define MMM_HANDOFF_FIXTURE 1\nstatic void runHandoffFixture();\n' + source
        if candidate_labels:
            if not 1<=len(candidate_labels)<=128: raise ValueError('Invalid candidate view count')
            source = ('#define MMM_CANDIDATE_LABEL_COUNT '+str(len(candidate_labels))+'\n'
                'static const char* candidateLabels[]={'+','.join(json.dumps(s) for s in candidate_labels)+'};\n') + source
    owner = ROOT / 'runtime/PanelEngineOwnerProbe.inl'
    fixture = ROOT / 'tests/native/panel_engine_owner_fixture.cpp'
    agent_client = ROOT / 'runtime/PanelEngineAgentClient.h'
    source += '\n#include ' + json.dumps(owner.as_posix()) + '\n#include ' + json.dumps(fixture.as_posix()) + '\n'
    if handoff:
        source += '\n#include ' + json.dumps((ROOT/'tests/native/panel_engine_handoff_fixture.cpp').as_posix()) + '\n'
    if updated:
        source += '\n#include '+json.dumps((ROOT/'tests/native/panel_engine_updated_fixture.cpp').as_posix())+'\n'
    work = work.resolve()
    boundary=Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha')).resolve()
    if not work.is_relative_to(boundary):
        raise ValueError('Native fixture output must remain under the alpha work directory')
    work.mkdir(parents=True, exist_ok=True)
    generated = work / 'owner-fixture.cpp'
    generated.write_text(source, encoding='utf8')
    compiler = Path('C:/Program Files (x86)/Microsoft Visual Studio/2017/BuildTools/VC/Tools/MSVC/14.16.27023/bin/Hostx86/x86/cl.exe')
    libraries = sorted(Path('C:/Program Files (x86)/Windows Kits/10/Lib').glob('*/um/x86/kernel32.lib'), reverse=True)
    executable = work / 'owner-fixture.exe'
    command = [str(compiler), '/nologo', '/O1', '/GS-', '/GR-', '/EHs-c-', '/Zl', '/Oi-', '/W3', '/TP',
        str(generated), '/Fo' + str(work / 'owner-fixture.obj'), '/Fe' + str(executable),
        '/link', '/NODEFAULTLIB', '/ENTRY:mainCRTStartup', '/SUBSYSTEM:CONSOLE', '/OPT:REF', str(libraries[0])]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if compiled.returncode:
        raise RuntimeError(compiled.stdout + compiled.stderr)
    tested = subprocess.run([str(executable)], capture_output=True, timeout=10)
    if tested.returncode:
        raise RuntimeError('SDK owner fixture failed, source line/exit=' + str(tested.returncode))
    receipt = {'schema': 1, 'sdkSha256': expected_hash, 'compiler': str(compiler), 'handlerHandoff': handoff,
        'updatedProtocol':updated,
        'candidateBehaviors':list(candidate_labels),
        'ownerProbeSha256': hashlib.sha256(owner.read_bytes()).hexdigest(),
        'fixtureSha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
        'agentClientSha256': hashlib.sha256(agent_client.read_bytes()).hexdigest(),
        'boundedVtableCopy': True,
        'redirectedNativeProviders': substitutions, 'nativeGameCallsExecuted': False,
        'coverage': ['ordinary panel remains untouched', 'view recognition before construction',
            'BASE keeps original view and unit', 'CLASS stock constructor handoff',
            'instance wrapper recognition', 'stock init before refresh', 'panel opener return preserved',
            'Back delegates stock navigation', 'mapped/native command return preserved',
            'event/notify forwarded once', 'one destructor with original flags and return',
            'older tall instance destruction preserves the newer panel frame',
            'null/deleted agent rejection precedes associated-unit request'],
        'limits': 'Provider doubles test SDK source ordering only; no three-build native layout/ABI or loaded-game acceptance claim.'}
    (work / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--work', type=Path, default=ROOT / 'local/panel-engine-alpha/owner-fixture')
    args = parser.parse_args()
    verify(args.sdk, args.work)
