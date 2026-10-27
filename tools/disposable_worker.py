"""Fixed synthetic controller-death worker; never accepts executable input."""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from ld2patch.disposable import DisposableCase,DisposableTransaction,load_payloads
from test_disposable import RECIPE
from ld2patch.windows_fixture import FixtureRefusal


def emit(value):
    print(json.dumps(value),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--parent',required=True,type=Path)
    p.add_argument('--mode',required=True,choices=['install','restore'])
    p.add_argument('--nonce',required=True)
    p.add_argument('--pause',choices=['captured','promoted','committed','restore-gap','restored'])
    args=p.parse_args()
    raw=sys.stdin.readline(16385)
    r=json.loads(raw)
    if set(r)!={'nonce','receipt_sha','leaf'} or r['nonce']!=args.nonce:
        raise FixtureRefusal('worker request mismatch')
    def hook(phase):
        if phase==args.pause:
            emit({'event':'paused','phase':phase,'pid':os.getpid(),'nonce':args.nonce})
            time.sleep(20)
            raise FixtureRefusal('pause deadline; abort without continuing')
    with DisposableCase(args.parent,r['leaf'],receipt_sha=r['receipt_sha'],recipe=RECIPE) as case:
        source,output=load_payloads(case)
        emit({'event':'ready','pid':os.getpid(),'argv':sys.argv,'nonce':args.nonce})
        tx=DisposableTransaction(case,source,output,lambda:'clear',hook)
        result=getattr(tx,args.mode)()
        emit(result)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        emit({'event':'error','type':type(e).__name__,'message':str(e)})
        sys.exit(2)

