"""Private worker for explicitly registered invented fixtures; no live installer."""
import argparse,json,os,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ld2patch.windows_crash_fixture import (RegisteredFixture,PersistentCapture,validate_registration,
    INSTALL_PHASES,RESTORE_PHASES)
from ld2patch.windows_fixture import FixtureRefusal


def emit(value):print(json.dumps(value),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True,type=Path)
    p.add_argument('--mode',choices=('install','restore'),required=True)
    p.add_argument('--pause',choices=INSTALL_PHASES+RESTORE_PHASES)
    p.add_argument('--nonce',required=True);args=p.parse_args()
    data=sys.stdin.buffer.readline(16385)
    if len(data)>16384:raise FixtureRefusal('registration too large')
    r=validate_registration(data)
    if args.nonce!=r['nonce']:raise FixtureRefusal('worker nonce mismatch')
    with RegisteredFixture(args.parent,r) as f:
        emit({'event':'ready','pid':os.getpid(),'argv':sys.argv,'nonce':args.nonce})
        def hook(phase):
            if phase==args.pause:
                emit({'event':'paused','phase':phase,'pid':os.getpid(),'nonce':args.nonce})
                # If identity verification/termination is unavailable, exit
                # cooperatively after a bounded pause. Never continue mutation.
                threading.Event().wait(20)
                raise FixtureRefusal('pause deadline expired; no further mutation')
        x=PersistentCapture(f,lambda:'clear',hook)
        result=x.install() if args.mode=='install' else x.restore()
        emit({'event':'result','result':result,'pid':os.getpid(),'nonce':args.nonce})


if __name__=='__main__':
    try:main()
    except Exception as e:
        emit({'event':'error','type':type(e).__name__,'message':str(e)})
        sys.exit(2)
