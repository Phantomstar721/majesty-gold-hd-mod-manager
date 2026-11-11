"""Read the packaged alpha's code and run isolated source/compiler fixtures."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application',type=Path,required=True)
    parser.add_argument('--merge-root',type=Path,required=True)
    parser.add_argument('--native-root',type=Path,required=True)
    parser.add_argument('--input-receipt',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    from verify_regression import BundleLoader
    bundle=BundleLoader(args.application/(args.application.name+'.exe'))
    bundle.verify_source()
    bundle.verify_data(args.application,alpha=True)
    sys.meta_path.insert(0,bundle)
    from verify_reward_contribution_candidates import verify
    verify(args.merge_root,args.native_root,args.work,infer=True,input_receipt=args.input_receipt)
    assert 'majesty_cam.reward_factoring' in bundle.loaded
