"""Write only owned section samples for the native descriptor ABI fixture."""
import os
from pathlib import Path
from majesty_cam.engine_module import install,inspect
ROOT=Path(__file__).resolve().parents[1]


def prepare():
    root=ROOT/'local/panel-engine-alpha'
    output=root/'module-descriptors';output.mkdir(parents=True,exist_ok=True)
    for branch in ('public','beta2','gog'):
        raw=Path(os.environ['MAJESTY_'+branch.upper()+'_EXE']).read_bytes()
        for service in ('window-engine','script-functions'):
            name=service+'-'+branch
            installed=install(raw,(root/'native-modules'/(name+'.mmne')).read_bytes(),branch)
            section=inspect(installed,service,branch)['section']
            (output/(name+'.bin')).write_bytes(installed[section.raw_offset:section.raw_offset+section.virtual_size])


if __name__=='__main__':prepare()
