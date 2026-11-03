# Ported from C:/Users/Wagur1/prism-vcm/scripts/spike_gate0.py:main; v1 commit a34d943; port date 2026-11-04.
"""Local execution only; no scheduler, accounts, or automatic training unlock."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_v2.codec.gate0 import run_gate
from prism_v2.codec.f1 import run_f1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stack',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--f1', action='store_true', help='Run complete J0 acceptance; missing evidence fails')
    args=p.parse_args()
    if not args.stack.is_file():
        print('[NEEDS VERIFY] FAIL: no pinned local codec stack');sys.exit(1)
    result=(run_f1 if args.f1 else run_gate)(args.output,json.loads(args.stack.read_text()))
    print(result['status'])
