"""Validate the typed ledger and flag uncited quantitative Markdown prose."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from prism_v2.evidence.ledger import load_ledger
from prism_v2.evidence.claims import check_markdown


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('markdown',nargs='*',type=Path);p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--ledger',type=Path);args=p.parse_args(argv)
    root=args.root.resolve()
    try:
        ledger=args.ledger or Path('evidence/ledger.jsonl')
        records=load_ledger(ledger if ledger.is_absolute() else root/ledger,root)
        paths=([path if path.is_absolute() else root/path for path in args.markdown]
               if args.markdown else [root/'README.md',*sorted((root/'reports').rglob('*.md'))])
        problems=[issue for path in paths for issue in check_markdown(path,records,readme=path.name.lower()=='readme.md')]
    except (ValueError,OSError,TypeError) as exc:
        print(exc);return 1
    for issue in problems:
        print(issue)
    if not problems:
        print('Ledger valid; prose tripwire clear. Manual evidence review is still required.')
    return int(bool(problems))


if __name__=='__main__':
    raise SystemExit(main())
