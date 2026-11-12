"""Copy the indexed engine runtime files into a fresh payload staging folder."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from majesty_cam.engine_module import runtime_files


def copy_runtime(source,target):
    files=runtime_files(source)
    if target.exists() and any(target.iterdir()):
        raise ValueError('Engine runtime target must be a fresh staging folder')
    for name in files:
        destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,destination)
    return files


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--target',type=Path,required=True)
    args=parser.parse_args()
    copy_runtime(args.source,args.target)
