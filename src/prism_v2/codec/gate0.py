# Ported from C:/Users/Wagur1/prism-vcm/scripts/spike_gate0.py; v1 commit a34d943; port date 2026-11-04.
"""Historical stimuli/worker isolation, adapted to frozen CRF intra controls."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from .fixtures import synthetic_frames, synthetic_content_sha256, offset_maps
from .x265_bridge import BuildPin, EncoderConfig, X265Library, X265Encoder, file_sha256
from .net_effect import frame_bits
from .criteria import verify_condition, SOURCE_SHA256
from .decoders import DecoderPin, verify_decoders
from .sei import has_sei


def encode_worker(job):
    prefix=Path(job['prefix']);width,height=job['width'],job['height']
    codec=X265Library(pin=BuildPin(**job['build']['pin']))
    if not codec.pin.enable_assembly:
        raise ValueError('CONFIG B1 requires assembly ON')
    offsets=offset_maps(width,height).get(job['map'])
    with X265Encoder(codec,width,height,EncoderConfig(crf=job['crf']),prefix.with_suffix('.csv')) as encoder:
        stream=b''.join(encoder.encode(frame,offsets) for frame in synthetic_frames(width,height))+encoder.flush()
    prefix.with_suffix('.hevc').write_bytes(stream)
    frame_bits(prefix.with_suffix('.csv'))


def encode_condition(prefix,name,build,crf,width,height):
    if any(prefix.parent.glob(prefix.name+'.*')):
        raise ValueError('Use fresh output; stale artifacts are not evidence')
    job={'prefix':str(prefix.resolve()),'map':name,'build':build,'crf':crf,'width':width,'height':height}
    path=prefix.with_suffix('.job.json');path.write_text(json.dumps(job,indent=2)+'\n')
    env={**os.environ,'PRISM_X265_SHIM':build['shim'],'PRISM_X265_LIBRARY':build['library'],
         'LD_LIBRARY_PATH':str(Path(build['library']).parent),
         'PYTHONPATH':str(Path(__file__).resolve().parents[2])+os.pathsep+os.environ.get('PYTHONPATH','')}
    env.pop('PRISM_X265_QP_TRACE',None);env.pop('PRISM_X265_RC_TELEMETRY',None)
    if name in ('zero','plus6','minus6','checkerboard'):
        env['PRISM_X265_QP_TRACE']=str(prefix.with_suffix('.trace.csv').resolve())
        env['PRISM_X265_RC_TELEMETRY']=str(prefix.with_suffix('.telemetry.csv').resolve())
    with prefix.with_suffix('.encode.log').open('wb') as log:
        subprocess.run([sys.executable,'-m','prism_v2.codec.gate0',str(path.resolve())],env=env,check=True,stdout=log,stderr=subprocess.STDOUT)


def run_gate(output,stack,width=1920,height=1080,crfs=(20,24,28,32,36)):
    output=Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Gate output must be empty')
    if not stack.get('enable_assembly') or any(not b['pin']['enable_assembly'] for b in stack['builds'].values()):
        raise ValueError('Assembly ON build required')
    if not crfs or any(c not in (20,24,28,32,36) for c in crfs):
        raise ValueError('Use the CONFIG CRF grid')
    output.mkdir(parents=True,exist_ok=True)
    report={'status':'RUNNING','gate0_complete':False,'criteria_source_sha256':SOURCE_SHA256,
            'synthetic_content_sha256':synthetic_content_sha256(width,height),'runs':[]}
    try:
        maps=offset_maps(width,height)
        for crf in crfs:
            streams={}
            for name in ('stock','same_binary_no_map','zero','plus6','minus6','checkerboard'):
                prefix=output/f'crf{crf}_{name}'
                build=stack['builds']['stock' if name=='stock' else 'patched']
                encode_condition(prefix,name,build,crf,width,height)
                path=prefix.with_suffix('.hevc');stream=path.read_bytes();streams[name]=stream
                if has_sei(stream):
                    raise ValueError('Stock/M2 controls must not contain geometry SEI')
                decoded=verify_decoders(path,DecoderPin(**stack['decoders']['ffmpeg']),DecoderPin(**stack['decoders']['hm']),width,height,10)
                report['runs'].append({'crf':crf,'map':name,'au_bytes_including_headers':len(stream),
                    'bitstream_sha256':hashlib.sha256(stream).hexdigest(),'decode':decoded})
            if streams['stock']!=streams['zero'] or streams['same_binary_no_map']!=streams['zero']:
                raise ValueError('Stock/same-binary zero-map byte identity failed')
            for name in ('plus6','minus6','checkerboard'):
                result=verify_condition(output/f'crf{crf}_zero.telemetry.csv',output/f'crf{crf}_{name}.telemetry.csv',
                    maps[name],name=name,width=width,height=height)
                report.setdefault('net_effect',[]).append({'crf':crf,'map':name,'result':result})
        report['status']='CODEC_CONTROLS_PASS'
        report['pending']='[NEEDS VERIFY] native SEI/warped-QG acceptance and historical replay; control pass alone does not satisfy F1'
    except Exception as exc:
        report.update(status='FAIL',reason=str(exc))
        raise
    finally:
        report['artifacts']={p.name:file_sha256(p) for p in output.iterdir() if p.is_file()}
        (output/'gate0.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    encode_worker(json.loads(Path(sys.argv[1]).read_text()))
