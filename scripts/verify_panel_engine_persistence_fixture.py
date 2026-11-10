"""Run the real restore adapter against provider doubles in a disposable process."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]


def verify(work):
    boundary=Path(os.environ.get('MMM_REGRESSION_TEMP',ROOT/'local/panel-engine-alpha')).resolve()
    work=work.resolve()
    if not work.is_relative_to(boundary):raise ValueError('Persistence fixture output escapes alpha workspace')
    work.mkdir(parents=True,exist_ok=True)
    tool=Path('C:/Program Files (x86)/Microsoft Visual Studio/2017/BuildTools/VC/Tools/MSVC/14.16.27023')
    sdk=Path('C:/Program Files (x86)/Windows Kits/10')
    version=sorted((sdk/'Include').iterdir(),reverse=True)[0].name
    executable=work/'persistence-fixture.exe'
    command=[str(tool/'bin/Hostx86/x86/cl.exe'),'/nologo','/W3','/O2','/EHsc','/DCAM_PANEL_ENGINE_ALPHA=1',
             '/I'+str(tool/'include'),*['/I'+str(sdk/'Include'/version/p) for p in ('ucrt','shared','um')],
             str(ROOT/'tests/LargeModListTests.cpp'),'/Fo'+str(work/'fixture.obj'),'/Fe'+str(executable),
             '/link','/BASE:0x10000000','/DYNAMICBASE','/LIBPATH:'+str(tool/'lib/x86'),
             *['/LIBPATH:'+str(sdk/'Lib'/version/p/'x86') for p in ('ucrt','um')]]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    result=subprocess.run([str(executable)]+[os.environ['MAJESTY_'+b+'_EXE'] for b in ('PUBLIC','BETA2','GOG')],
                          capture_output=True,text=True,timeout=30)
    if result.returncode:raise RuntimeError('Persistence fixture failed: '+str(result.returncode)+' '+result.stdout+result.stderr)


if __name__=='__main__':verify(ROOT/'local/panel-engine-alpha/persistence-fixture')
