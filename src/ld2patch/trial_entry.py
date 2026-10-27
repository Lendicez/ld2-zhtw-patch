"""Candidate factory and CLI, bound to bundled disposable policy."""
import argparse,json,sys
from pathlib import Path
from .generator import resource_root,elevated
from .patch_engine import strict_json
from .trial_store import validate_policy
from .trial_backend import TrialBackend
from .trial_controller import TrialController
from .profiles import PROFILE_IDS,DEFAULT_TRIAL_PROFILE


def policy():
    # Frozen candidates have a build-time scope. CLI cannot override this root.
    return validate_policy(strict_json((resource_root()/'trial-policy.json').read_bytes(),16384))


def make_trial_controller(profile=DEFAULT_TRIAL_PROFILE):
    from .ui import make_controller
    return TrialController(make_controller(profile),TrialBackend(policy(),profile=profile))


def main(argv):
    p=argparse.ArgumentParser(description='只對內建範圍中的新副本操作；不啟動遊戲。')
    p.add_argument('operation',choices=['preview','install','restore','inspect'])
    p.add_argument('--source',type=Path)
    p.add_argument('--workspace',type=Path)
    p.add_argument('--confirm',action='store_true')
    p.add_argument('--profile',choices=PROFILE_IDS,default=DEFAULT_TRIAL_PROFILE,
                   help='Installation profile; restore identifies its profile from the protected anchor')
    p.add_argument('--cancel',action='store_true',help='Cancel a prepared confirmation without writing')
    a=p.parse_args(argv)
    try:
        if elevated():raise ValueError('請以一般權限啟動。')
        if a.cancel and (a.confirm or a.operation!='preview'):p.error('--cancel requires preview and no --confirm')
        c=make_trial_controller(a.profile)
        if a.operation in ('preview','install'):
            if not a.source or a.workspace:p.error('source required, workspace not accepted')
            if a.source.name!='Ld95.exe':raise ValueError('explicit Ld95.exe required')
            c.manual(str(a.source.parent));c.inspect(str(a.source.parent));c.request_install()
            if a.operation=='install':
                if not a.confirm:raise ValueError('explicit --confirm required')
                result=c.confirm()
            else:result=c.cancel() if a.cancel else c.view()
        else:
            if not a.workspace or a.source:p.error('workspace required, source not accepted')
            if a.operation=='inspect':
                result=c.backend.inspect(str(a.workspace))
            else:
                result=c.request_restore(str(a.workspace))
                if result['stage']!='restored':
                    if not a.confirm:raise ValueError('explicit --confirm required')
                    result=c.confirm()
        print(json.dumps(result,ensure_ascii=True,indent=2));return 0
    except (OSError,ValueError,RuntimeError) as e:
        print(json.dumps({'status':'refused_or_failed','reason':str(e),'production_can_apply':False,
                          'executed_game':False},ensure_ascii=True),file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main(sys.argv[1:]))

