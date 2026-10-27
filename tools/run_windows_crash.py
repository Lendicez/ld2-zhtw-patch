"""Explicit non-admin OS fixture run; retains every artifact and exact manifest.

Use an existing project-owned --parent. The native factory creates a new random
subdirectory and pins all ancestors; never attach to an existing game directory.
"""
import argparse,hashlib,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tests'))
from ld2patch.windows_fixture import NativeFixture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',required=True,type=Path)
    args=parser.parse_args()
    if os.environ.get('LD2_CRASH_FIXTURE_PARENT'):
        parser.error('do not reuse an existing native fixture environment')
    with NativeFixture(args.parent,['outside.bin','result.json',*[f'worker-{i}.json' for i in range(128)]]) as batch:
        sentinel=b'OUTSIDE THE INDIVIDUAL TEST ROOTS: unchanged'
        batch.create('outside.bin',sentinel)
        os.environ['LD2_CRASH_FIXTURE_PARENT']=str(batch.root)
        import test_windows_crash
        import owned_worker
        suite=unittest.defaultTestLoader.loadTestsFromModule(test_windows_crash)
        result=unittest.TextTestRunner(verbosity=2,failfast=True).run(suite)
        unchanged=batch.read('outside.bin')==sentinel
        for i,record in enumerate(owned_worker.EVIDENCE):
            batch.create(f'worker-{i}.json',(json.dumps(record,indent=2)+'\n').encode('utf-8'))
        files=[]
        for path in sorted(batch.root.rglob('*')):
            stat=path.lstat()
            if path.is_symlink() or getattr(stat,'st_file_attributes',0)&0x400:
                files.append({'path':path.relative_to(batch.root).as_posix(),'reparse':True}); continue
            if path.is_file():
                data=path.read_bytes()
                files.append({'path':path.relative_to(batch.root).as_posix(),'bytes':len(data),
                              'sha256':hashlib.sha256(data).hexdigest()})
        evidence={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                  'skips':[{'test':str(test),'reason':reason} for test,reason in result.skipped],
                  'outside_sentinel_unchanged':unchanged,'non_admin':True,'filesystem':batch.filesystem,
                  'platform':sys.getwindowsversion().build,'files':files,'production_can_apply':False,
                  'existing_target_replacement':'fixture-only capture/promote; no overwrite', 'atomic_visibility':False,
                  'power_loss_tested':False,'files_retained':True,'owned_worker_termination_attempts':sum(x['terminated'] for x in owned_worker.EVIDENCE),'worker_blocked':owned_worker.BLOCKED}
        batch.create('result.json',(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        print(json.dumps({'fixture_root':str(batch.root),'result':str(batch.path('result.json')),
                          'tests_run':result.testsRun,'skips':len(result.skipped),'success':result.wasSuccessful() and unchanged}))
        return 0 if result.wasSuccessful() and unchanged else 1


if __name__=='__main__': sys.exit(main())
