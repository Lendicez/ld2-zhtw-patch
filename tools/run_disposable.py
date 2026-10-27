"""Explicit, non-admin OFFLINE disposable EXE acceptance. Never launches EXEs.

Prepare creates case-01 exclusively. Install/restore require the receipt digest
saved independently at preparation; losing it means refusal, not auto-trust.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.disposable import (DisposableCase,DisposableTransaction,read_source_only,
    build_reviewed,load_payloads,observed_guard,REVIEWED)
from ld2patch.patch_engine import strict_json
from ld2patch.windows_readonly import process_state
from ld2patch.windows_fixture import FixtureRefusal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['prepare','install','restore','inspect'])
    p.add_argument('--parent',required=True,type=Path)
    p.add_argument('--source',type=Path)
    p.add_argument('--receipt-sha')
    args=p.parse_args()
    if args.operation=='prepare':
        if not args.source or args.receipt_sha:p.error('prepare requires source only')
        source,before=read_source_only(args.source)
        built=build_reviewed(source,(ROOT/'patches/ui-m020.zh-TW.json').read_bytes(),
              strict_json((ROOT/'patches/versions.json').read_bytes()),
              strict_json((ROOT/'patches/m020-recipe.json').read_bytes()))
        with DisposableCase(args.parent,'case-01',create=True) as case:
            receipt=case.prepare(source,built.output)
            source_after,after=read_source_only(args.source)
            if source_after!=source or before!=after:
                raise FixtureRefusal('source changed while preparing copy')
            result={'operation':'prepare','case':str(case.root),'receipt_sha256':receipt,
                    'source_before':before,'source_after':after,'build':built.metadata,
                    'can_apply':False,'game_executed':False}
    else:
        if args.source or not args.receipt_sha:p.error('restart requires receipt digest, no source input')
        with DisposableCase(args.parent,'case-01',receipt_sha=args.receipt_sha) as case:
            source,output=load_payloads(case)
            guard=lambda:observed_guard(case.path('target.bin'),process_state())
            tx=DisposableTransaction(case,source,output,guard)
            before=tx.snapshot()
            action={'status':'inspected'} if args.operation=='inspect' else getattr(tx,args.operation)()
            result={'operation':args.operation,'case':str(case.root),'receipt_sha256':args.receipt_sha,
                    'result':action,'before':before,'after':tx.snapshot(),'can_apply':False,
                    'game_executed':False}
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return 0


if __name__=='__main__':sys.exit(main())

