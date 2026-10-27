"""Headless confirmation/recovery state machine for newly owned trial copies."""
from dataclasses import asdict
import threading
from .discovery import EvidenceError,child
from .trial_backend import TrialFailure

NOTICE='只在新建的驗收工作區安裝副本；正式遊戲目錄安裝仍停用。'
RECOVERY_NOTICE=('復原憑據會自動存放於工作區的 recovery-store，使用目前 Windows 帳戶保護。'
    '請保留整個工作區並使用同一帳戶；資料遺失、損壞或無法驗證時會拒絕還原，不需抄寫雜湊。')


class TrialController:
    def __init__(self,base,backend):
        self.base=base;self.backend=backend;self.lock=threading.RLock()
        self.stage='choose';self.pending=None;self.workspace=None;self.issue='';self.result=None;self.stopped=False
    def _idle(self):
        if self.stage=='busy':raise EvidenceError('operation_in_progress')
        if self.stopped or self.base.stopped:raise EvidenceError('session_stopped_after_access_denial')
    def _reset(self):
        self.pending=None;self.issue='';self.result=None;self.stage='choose'
    def discover(self):
        with self.lock:
            self._idle();self._reset();self.base.discover();return self.view()
    def manual(self,folder):
        with self.lock:
            self._idle();self._reset();self.base.manual(folder);return self.view()
    def inspect(self,folder):
        with self.lock:
            self._idle();self._reset();self.base.inspect(folder)
            if self.base.preview and self.base.preview.can_generate:self.stage='ready'
            return self.view()
    def request_install(self):
        with self.lock:
            self._idle()
            if self.stage!='ready' or not self.base.preview or not self.base.preview.can_generate:
                raise EvidenceError('known_original_selection_required')
            p=self.base.preview
            self.pending={'action':'install','preview':p,
                          'plan':self.backend.plan(child(p.install_dir,'Ld95.exe'))}
            self.stage='confirm_install';return self.view()
    def cancel(self):
        with self.lock:
            self._idle();self.pending=None;self.issue=''
            self.stage='ready' if self.base.preview and self.base.preview.can_generate else 'choose'
            return self.view()
    back=cancel

    def request_restore(self,workspace):
        with self.lock:
            self._idle()
            # Inspection may read the protected store; it cannot mutate a case.
            try:info=self.backend.inspect(workspace)
            except Exception as e:
                self.issue=str(e);self.stage='failed';self.pending=None
                self.stopped=isinstance(e,PermissionError) or getattr(e,'code',None)==5
                raise
            self.workspace=info['workspace'];self.result=info;self.issue=''
            self.pending=None
            if info['status']=='already_original':
                self.stage='restored'
            else:
                self.pending={'action':'restore','workspace':info['workspace']}
                self.stage='confirm_restore'
            return self.view()

    def confirm(self):
        with self.lock:
            self._idle()
            if self.stage not in ('confirm_install','confirm_restore') or self.pending is None:
                raise EvidenceError('explicit_confirmation_required')
            action=self.pending;self.pending=None;self.stage='busy'
        try:
            if action['action']=='install':
                old=action['preview']
                self.base.inspect(old.install_dir)
                if self.base.preview!=old or not self.base.preview.can_generate:
                    raise EvidenceError('preview_changed')
                result=self.backend.install(action['plan'])
            else:result=self.backend.restore(action['workspace'])
        except Exception as e:
            with self.lock:
                self.issue=str(e);self.stage='failed'
                self.stopped=bool(getattr(e,'denied',False) or isinstance(e,PermissionError)
                                  or getattr(e,'code',None)==5 or self.base.stopped)
                if isinstance(e,TrialFailure):self.workspace=e.workspace
            raise
        with self.lock:
            self.result=result;self.workspace=result['workspace']
            self.stage='installed' if result['status']=='installed_trial' else 'restored'
            return self.view()

    def view(self):
        with self.lock:
            view=self.base.view()
            preview=self.pending.get('plan') if self.pending and self.pending['action']=='install' else None
            return {**view,'title':'LD2 繁中副本驗收候選版','stage':self.stage,
                'notice':NOTICE,'recovery_notice':RECOVERY_NOTICE,'issue':self.issue or view['issue'],
                'workspace':self.workspace,'trial_plan':preview,'result':self.result,
                'profile':self.backend.profile_info(),
                'stopped':self.stopped or view['stopped'],'install_enabled':False,
                'trial_enabled':self.stage=='ready' and not self.stopped and not view['stopped'],
                'confirm_enabled':self.stage in ('confirm_install','confirm_restore'),
                'busy':self.stage=='busy'}

