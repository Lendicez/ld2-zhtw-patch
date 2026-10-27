"""Candidate-only orchestration. Cannot adopt a selected existing game directory."""
from pathlib import Path
from .disposable import (DisposableCase,DisposableTransaction,read_source_only,
                        build_reviewed,load_payloads,observed_guard)
from .windows_capture import token
from .windows_fixture import FixtureRefusal
from .windows_readonly import process_state
from .trial_store import TrialSpace,validate_policy,new_leaf
from .patch_engine import strict_json
from .generator import resource_root


class TrialFailure(RuntimeError):
    def __init__(self,message,workspace,anchor_saved=False,denied=False):
        super().__init__(message)
        self.workspace=workspace;self.anchor_saved=anchor_saved;self.denied=denied


class TrialBackend:
    can_apply=False
    def __init__(self,policy,*,protector=None):
        self.policy=validate_policy(policy);self.protector=protector
    def plan(self,source):
        source=Path(source);parent=Path(self.policy['parent'])
        if not source.is_absolute() or source.name!='Ld95.exe':
            raise FixtureRefusal('explicit original source required')
        if parent.is_relative_to(source.parent) or source.is_relative_to(parent):
            raise FixtureRefusal('source/test-root overlap refused')
        leaf=new_leaf()
        return {'source':str(source),'leaf':leaf,'workspace':str(parent/leaf),
                'target':str(parent/leaf/'case-01/Ld95.exe'),
                'recovery_store':str(parent/leaf/'recovery-store'),
                'production_can_apply':False}

    def install(self,plan):
        expected=self.plan(plan['source'])
        # Random leaf must be supplied by our plan, never interpreted as a path.
        parent=Path(self.policy['parent'])
        if (set(plan)!=set(expected) or plan['production_can_apply'] is not False
            or plan['workspace']!=str(parent/plan['leaf'])
            or plan['target']!=str(parent/plan['leaf']/'case-01/Ld95.exe')
            or plan['recovery_store']!=str(parent/plan['leaf']/'recovery-store')):
            raise FixtureRefusal('candidate plan altered')
        saved=False
        try:
            source,_=read_source_only(Path(plan['source']))
            data=resource_root()
            built=build_reviewed(source,(data/'ui-m020.zh-TW.json').read_bytes(),
                strict_json((data/'versions.json').read_bytes()),strict_json((data/'m020-recipe.json').read_bytes()))
            with TrialSpace(self.policy,plan['leaf'],create=True,protector=self.protector) as space:
                with DisposableCase(space.root,'case-01',create=True) as case:
                    receipt=case.prepare(source,built.output)
                    space.save(receipt,token(case.root_handle.identity()));saved=True
                    tx=DisposableTransaction(case,source,built.output,
                        lambda:observed_guard(case.path('target.bin'),process_state()))
                    result=tx.install()
                    return {'status':'installed_trial','workspace':str(space.root),
                            'target':plan['target'],'recovery_store':str(space.vault),
                            'snapshot':tx.snapshot(),'result':result,'production_can_apply':False}
        except Exception as e:
            raise TrialFailure(str(e),plan['workspace'],saved,
                               isinstance(e,PermissionError) or getattr(e,'code',None)==5) from e

    def _leaf(self,workspace):
        path=Path(workspace)
        if path.parent!=Path(self.policy['parent']):
            raise FixtureRefusal('workspace is outside bound candidate root')
        return path.name

    def open_case(self,space):
        body=space.load()  # No plaintext/card/hash fallback.
        case=DisposableCase(space.root,'case-01',receipt_sha=body['receipt_sha256'])
        if token(case.root_handle.identity())!=body['case_root']:
            case.stack.close();raise FixtureRefusal('authenticated case identity differs')
        return case

    def inspect(self,workspace):
        with TrialSpace(self.policy,self._leaf(workspace),protector=self.protector) as space:
            with self.open_case(space) as case:
                source,output=load_payloads(case)
                tx=DisposableTransaction(case,source,output,lambda:'clear')
                snapshot=tx.snapshot()
                target=snapshot.get('target.bin')
                status=('already_original' if target and target['identity']==case.receipt['prepared']['original']
                        and target['sha256']==case.recipe.source_hash else 'recovery_available')
                return {'status':status,'workspace':str(space.root),'snapshot':snapshot,
                        'recovery_store':str(space.vault),'production_can_apply':False}

    def restore(self,workspace):
        with TrialSpace(self.policy,self._leaf(workspace),protector=self.protector) as space:
            with self.open_case(space) as case:
                source,output=load_payloads(case)
                tx=DisposableTransaction(case,source,output,
                    lambda:observed_guard(case.path('target.bin'),process_state()))
                before=tx.snapshot();result=tx.restore()
                return {'status':'restored_trial' if result['status']=='rolled_back' else result['status'],
                        'workspace':str(space.root),'before':before,'after':tx.snapshot(),
                        'production_can_apply':False}

