"""Exact recovered criteria; no raw-drift fallback or post-hoc recalibration."""
from pathlib import Path
import hashlib
import json
from .net_effect import project_telemetry_qg, verify_net_effect_qg

SOURCE_SHA256='316134d2f2cf448f6d1e4292d7c9fee0e9fbd60c58e1cb4c196f624d9cad2cdc'
RUNTIME_SHA256='73173d5315924e3a81d8a6ff15bbefc8a5f80806f5de4bfd4df094c4ae9d4760'


def load_criteria():
    raw=(Path(__file__).with_name('criteria')/'gate0_v3.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=RUNTIME_SHA256:
        raise ValueError('Frozen criteria hash mismatch; no gate verdict is permitted')
    return json.loads(raw)


def verify_condition(zero,condition,offsets,*,name,width,height,frames=10):
    criteria=load_criteria()
    if name not in ('plus6','minus6','checkerboard'):
        raise ValueError("Unknown gate condition")
    for path in (zero,condition):
        projected=project_telemetry_qg(path,width,height)
        if set(projected['frames'])!=set(range(frames)):
            raise ValueError("Incomplete expected telemetry frames")
        if any(identity[2]!='I' or identity[3]!='CRF' for identity in projected['identities'].values()):
            raise ValueError("Only intra CRF telemetry is valid for the J0 runner")
    return verify_net_effect_qg(zero,condition,offsets,bands=criteria['bands'][name],
        min_fidelity=criteria['fidelity'][name],min_aggregate_median=criteria['aggregate_floor_magnitude'],
        i_frames=set(range(frames)),width=width,height=height)
