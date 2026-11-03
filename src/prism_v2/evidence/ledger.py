"""G1 typed records and offline immutable artifact validation.

Types discriminate empirical observations from quotations, protocol constants,
estimates, and rejected history. Validation never establishes scientific support.
"""
from __future__ import annotations
from pathlib import Path
from typing import Literal, TypedDict
import hashlib
import json
import math
import re


class Artifact(TypedDict):
    path: str
    sha256: str


class Measured(TypedDict):
    id: str
    type: Literal['measured']
    statement: str
    metric: str
    value: float
    unit: str
    detector: str
    weights: Artifact
    split_manifest: Artifact
    seeds: list[int]
    crfs: list[float]
    checkpoint: Artifact
    commit: str
    build: Artifact
    patch: Artifact
    analysis_configuration: Artifact
    uncertainty: dict
    validity: dict
    result: Artifact
    harvest: Artifact


class Literature(TypedDict):
    id: str
    type: Literal['literature']
    statement: str
    source: Artifact
    citation: str
    context: str
    verification_status: Literal['verified','NEEDS VERIFY']


class DesignConstant(TypedDict):
    id: str
    type: Literal['design-constant']
    statement: str
    value: object
    unit: str
    authority: Artifact


class DerivedEstimate(TypedDict):
    id: str
    type: Literal['derived-estimate']
    statement: str
    formula: str
    inputs: dict
    assumptions: list[str]
    verification_status: Literal['verified','NEEDS VERIFY']


class RejectedHistorical(TypedDict):
    id: str
    type: Literal['rejected-historical']
    statement: str
    source: Artifact
    reason: str


Claim = Measured | Literature | DesignConstant | DerivedEstimate | RejectedHistorical
SCHEMAS={'measured':Measured,'literature':Literature,'design-constant':DesignConstant,
         'derived-estimate':DerivedEstimate,'rejected-historical':RejectedHistorical}
SHA256=re.compile(r'[0-9a-f]{64}\Z')


def artifact(value, root: Path):
    if not isinstance(value,dict) or set(value)!={'path','sha256'} or not isinstance(value['path'],str) or not isinstance(value['sha256'],str) or not SHA256.fullmatch(value['sha256']):
        raise ValueError('Artifact needs a path and complete SHA-256')
    path=(root/value['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Artifact must resolve locally inside evidence root; no network resolution')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=value['sha256']:
        raise ValueError('Artifact SHA-256 mismatch')


def validate_record(record: Claim, root: Path):
    if not isinstance(record,dict) or record.get('type') not in SCHEMAS:
        raise ValueError('Unknown claim type')
    schema=SCHEMAS[record['type']]
    if set(record)!=set(schema.__annotations__):
        raise ValueError(f'Wrong fields for {record["type"]}: expected {sorted(schema.__annotations__)}')
    for key in ('id','statement'):
        if not isinstance(record[key],str) or not record[key].strip():
            raise ValueError(f'Nonempty {key} required')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*',record['id']):
        raise ValueError('Invalid claim ID')
    kind=record['type']
    if kind=='measured':
        for key in ('metric','unit','detector','commit'):
            if not isinstance(record[key],str) or not record[key].strip():
                raise ValueError(f'Nonempty {key} required')
        if not re.fullmatch(r'[0-9a-f]{40}',record['commit']):
            raise ValueError('Measured claim requires a complete commit hash')
        if type(record['value']) not in (int,float) or not math.isfinite(record['value']):
            raise ValueError('Finite measured value required')
        for key in ('weights','split_manifest','checkpoint','build','patch','analysis_configuration','result','harvest'):
            artifact(record[key],root)
        for key in ('seeds','crfs'):
            values=record[key]
            if not isinstance(values,list) or not values or any(type(v) not in (int,float) or not math.isfinite(v) for v in values) or len(set(values))!=len(values):
                raise ValueError('Nonempty unique finite seeds/CRFs required')
        if any(type(v) is not int or v<0 for v in record['seeds']) or any(not 0<=v<=51 for v in record['crfs']):
            raise ValueError('Invalid seed/CRF domain')
        unc=record['uncertainty'];valid=record['validity']
        if not isinstance(unc,dict) or set(unc)!={'method','lower','upper','level'} or not isinstance(unc['method'],str) or not unc['method'].strip():
            raise ValueError('Explicit uncertainty method/interval/level required')
        if any(type(unc[k]) not in (int,float) or not math.isfinite(unc[k]) for k in ('lower','upper','level')) or unc['lower']>unc['upper'] or not 0<unc['level']<1:
            raise ValueError('Invalid uncertainty interval')
        if not isinstance(valid,dict) or set(valid)!={'status','reason'} or valid['status'] not in ('valid','invalid','incomplete') or not isinstance(valid['reason'],str) or not valid['reason'].strip():
            raise ValueError('Explicit validity status and reason required')
    elif kind=='design-constant':
        artifact(record['authority'],root)
        if not isinstance(record['unit'],str) or not record['unit']:
            raise ValueError('Design unit required')
    elif kind in ('literature','rejected-historical'):
        artifact(record['source'],root)
        for key in (('citation','context') if kind=='literature' else ('reason',)):
            if not isinstance(record[key],str) or not record[key].strip():
                raise ValueError(f'Nonempty {key} required')
    elif kind=='derived-estimate':
        if not isinstance(record['formula'],str) or not record['formula'].strip() or not isinstance(record['inputs'],dict) or not record['inputs']:
            raise ValueError('Estimate formula and inputs required')
        if not isinstance(record['assumptions'],list) or not record['assumptions'] or any(not isinstance(a,str) or not a.strip() for a in record['assumptions']):
            raise ValueError('Estimate assumptions required')
        # Inputs must carry immutable provenance, even when the estimate is unverified.
        for value in record['inputs'].values():
            if not isinstance(value,dict) or set(value)!={'value','unit','source'}:
                raise ValueError('Estimate input requires value, unit, and source artifact')
            artifact(value['source'],root)
    if kind in ('literature','derived-estimate') and record['verification_status'] not in ('verified','NEEDS VERIFY'):
        raise ValueError('Explicit verification status required')
    # Reject non-JSON values and NaN anywhere, including nested constant/estimate values.
    json.dumps(record,allow_nan=False)
    return record


def load_ledger(path: Path, root: Path):
    records={}
    def no_duplicates(pairs):
        result={}
        for k,v in pairs:
            if k in result:
                raise ValueError(f'Duplicate JSON field: {k}')
            result[k]=v
        return result
    for lineno,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():
            continue
        try:
            record=validate_record(json.loads(line,object_pairs_hook=no_duplicates),root)
            if record['id'] in records:
                raise ValueError('Duplicate claim ID')
            records[record['id']]=record
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError(f'{path}:{lineno}: {exc}') from exc
    return records
