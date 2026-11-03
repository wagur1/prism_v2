"""G2 prose tripwire; citations are pointers, never automatic support judgments."""
from pathlib import Path
import re

CITATION=re.compile(r'\[claim:([A-Za-z0-9_.-]+)\]')
NUMBER=re.compile(r'(?<![\w])[-+−]?\d+(?:[.,]\d+)*(?:\s*(?:%|pp|ms|fps|GB|hours?))?(?![\w])')


def check_markdown(path: Path, records: dict, *, readme=False):
    problems=[];fence=None
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        stripped=line.lstrip()
        if stripped.startswith(('```','~~~')):
            marker=stripped[:3];fence=None if fence==marker else marker if fence is None else fence
            continue
        if fence:
            continue
        citations=CITATION.findall(line)
        for identifier in citations:
            if identifier not in records:
                problems.append(f'{path}:{n}: unknown claim {identifier}')
            else:
                record=records[identifier]
                if record['type']=='rejected-historical' or record.get('verification_status')=='NEEDS VERIFY' or record.get('validity',{}).get('status','valid')!='valid':
                    if '[NEEDS VERIFY]' not in line and '[REJECTED]' not in line:
                        problems.append(f'{path}:{n}: unverified/rejected claim needs an explicit label')
        prose=CITATION.sub('',line)
        prose=re.sub(r'`[^`]*`','',prose)
        prose=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',prose)
        prose=re.sub(r'^\s*\d+[.)]\s+','',prose)
        if NUMBER.search(prose) and (readme or not citations):
            problems.append(f'{path}:{n}: quantitative prose '+('is forbidden in README' if readme else 'needs [claim:id] and manual support review'))
    return problems
