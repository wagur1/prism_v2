"""G2 prose tripwire; citations are pointers, never automatic support judgments."""
from pathlib import Path
import re

CITATION=re.compile(r'\[claim:([A-Za-z0-9_.-]+)\]')
NUMBER=re.compile(
    r'(?<![\w.])[-+\u2212]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:[eE][-+]?\d+)?'
    r'(?:\s*(?:%|percent|pp|ms|fps|[KMGT]i?B|[GM]Hz|hours?|secs?|seconds?|'
    r'[GC]PU[- ]h|QP|[x\u00d7](?:\d+(?:[x\u00d7]\d+)*)?))?(?!\w)', re.IGNORECASE)
FENCE=re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
CODE=re.compile(r'(?<!`)(`+)(?!`)(.*?)\1(?!`)')


def _code_prose(match):
    # A quantity remains a claim when displayed in a code span. Identifier and
    # command spans stay excluded; citations inside code never support prose.
    content=match.group(2).strip()
    return content if NUMBER.fullmatch(content) else ''


def check_markdown(path: Path, records: dict, *, readme=False):
    problems=[];fence=None;comment=False
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        marker=FENCE.match(line)
        if fence:
            if marker and marker[1][0]==fence[0] and len(marker[1])>=len(fence) and not marker[2].strip():
                fence=None
            continue
        if not comment and marker and (marker[1][0]=='~' or '`' not in marker[2]):
            fence=marker[1]
            continue
        line=CODE.sub(_code_prose,line)
        visible=''
        while line:
            if comment:
                _,end,line=line.partition('-->')
                if not end:
                    break
                comment=False
            else:
                prefix,start,line=line.partition('<!--')
                visible+=prefix
                comment=bool(start)
        line=visible
        line=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',line)
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
        prose=re.sub(r'^\s*\d+[.)]\s+','',prose)
        if NUMBER.search(prose) and (readme or not citations):
            problems.append(f'{path}:{n}: quantitative prose '+('is forbidden in README' if readme else 'needs [claim:id] and manual support review'))
    return problems
