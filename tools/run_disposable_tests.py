"""Opt-in Windows copy tests; only a new synthetic child of supplied parent."""
import argparse,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from ld2patch.windows_fixture import NativeFixture


def main():
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True,type=Path);args=p.parse_args()
    if os.environ.get('LD2_DISPOSABLE_PARENT'):
        p.error('existing fixture environment refused')
    with NativeFixture(args.parent,['outside.bin','result.json']) as batch:
        batch.create('outside.bin',b'OUTSIDE UNCHANGED')
        os.environ['LD2_DISPOSABLE_PARENT']=str(batch.root)
        import test_disposable,owned_worker
        result=unittest.TextTestRunner(verbosity=2,failfast=True).run(
            unittest.defaultTestLoader.loadTestsFromModule(test_disposable))
        for i,e in enumerate(owned_worker.EVIDENCE):
            (batch.root/f'worker-{i}.json').write_text(json.dumps(e,indent=2),encoding='utf-8')
        evidence={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                  'skips':[{'test':str(t),'reason':s} for t,s in result.skipped],
                  'outside_unchanged':batch.read('outside.bin')==b'OUTSIDE UNCHANGED',
                  'workers':len(owned_worker.EVIDENCE),
                  'verified_terminations':sum(bool(e.get('terminated') and e.get('identity_verified')) for e in owned_worker.EVIDENCE),
                  'worker_exits':[e.get('exit_code') for e in owned_worker.EVIDENCE],
                  'non_admin':True,'game_executed':False,'power_loss_tested':False,
                  'controller_memory_required_for_recovery':False,
                  'independently_retained_receipt_digest_required':True}
        batch.create('result.json',(json.dumps(evidence,indent=2)+'\n').encode())
        print(json.dumps({'result':str(batch.path('result.json')),**evidence}))
        return 0 if result.wasSuccessful() and evidence['outside_unchanged'] else 1


if __name__=='__main__':sys.exit(main())

