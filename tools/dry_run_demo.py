"""Synthetic-only preview. No CLI option accepts a real game or registry path."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from fake_steam import APP_ID,example
from ld2patch.discovery import discover
from ld2patch.planner import ProcessEvidence,plan_install
fs,root,install,config=example()
discovery=discover([root],APP_ID,fs)
plan=plan_install(discovery,config,fs,ProcessEvidence(True))
print(json.dumps({'synthetic_only':True,'discovery':discovery.to_dict(),'plan':plan.to_dict()},ensure_ascii=True,indent=2))
