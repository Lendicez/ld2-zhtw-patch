"""Explicit native DPAPI/store tests in a new synthetic subtree."""
import argparse,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from ld2patch.windows_fixture import NativeFixture


def main():
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True,type=Path);a=p.parse_args()
    if os.environ.get('LD2_TRIAL_STORE_PARENT'):p.error('existing test environment refused')
    with NativeFixture(a.parent,['result.json']) as f:
        os.environ['LD2_TRIAL_STORE_PARENT']=str(f.root)
        import test_trial
        result=unittest.TextTestRunner(verbosity=2,failfast=True).run(unittest.defaultTestLoader.loadTestsFromModule(test_trial))
        evidence={'total':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),
                  'skips':[{'test':str(t),'reason':r} for t,r in result.skipped],
                  'non_admin':True,'gui_opened':False,'game_executed':False}
        f.create('result.json',(json.dumps(evidence,indent=2)+'\n').encode())
        print(json.dumps({'result':str(f.path('result.json')),**evidence}))
        return 0 if result.wasSuccessful() else 1


if __name__=='__main__':sys.exit(main())

