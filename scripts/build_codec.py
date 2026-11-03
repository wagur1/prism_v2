# Ported from C:/Users/Wagur1/prism-vcm/gate0/build_gate0_stack.sh; v1 commit a34d943; port date 2026-11-04.
"""Offline Linux builder. Sources are read-only inputs; output must be new.

Preserves the v1 compiler/CMake and HM diagnostic compatibility settings.
Requires preinstalled tools and clean pinned git sources. No installs/downloads.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def run(argv, **kwargs):
    return subprocess.check_output([str(a) for a in argv],stderr=subprocess.STDOUT,**kwargs).decode().strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(x265_source: Path, hm_source: Path, output: Path, jobs: int):
    if sys.platform!='linux':
        raise ValueError('The pinned builder requires Linux')
    if not 1<=jobs<=4:
        raise ValueError('Use one through four build jobs')
    pins=json.loads((ROOT/'third_party/x265/PINNED_SOURCE.json').read_text())
    required=('git','patch','cmake','gcc','g++','make','nasm','ffmpeg')
    executables={name:shutil.which(name) for name in required}
    if not all(executables.values()):
        raise ValueError('Install prerequisites separately; this builder is offline')
    sources={'x265':x265_source.resolve(),'hm':hm_source.resolve()}
    output=output.resolve()
    if output.exists() or any(output.is_relative_to(p) or p.is_relative_to(output) for p in sources.values()):
        raise ValueError('Output must be new and separate from source trees')
    for name,path in sources.items():
        if run(['git','-C',path,'rev-parse','HEAD'])!=pins[name]['commit']:
            raise ValueError(f'Unpinned {name} source')
        if run(['git','--no-optional-locks','-C',path,'status','--porcelain','--untracked-files=no']):
            raise ValueError(f'Dirty {name} source')
    for name,expected in pins['patches'].items():
        if sha(ROOT/'third_party/x265/patches'/name)!=expected:
            raise ValueError('Patch hash mismatch')
    output.mkdir(parents=True)
    log=output/'build.log'
    def logged(argv):
        print('[BUILD] ' + ' '.join(str(a) for a in argv), flush=True)
        with log.open('ab') as stream:
            stream.write((repr([str(a) for a in argv])+'\n').encode())
            subprocess.run([str(a) for a in argv],check=True,stdout=stream,stderr=subprocess.STDOUT)
    archives={}
    for name,path in sources.items():
        raw=subprocess.check_output(['git','-C',str(path),'archive','--format=tar',pins[name]['commit']])
        archives[name]=hashlib.sha256(raw).hexdigest()
        destinations=('x265','x265-stock') if name=='x265' else ('hm',)
        for destination in destinations:
            target=output/'src'/destination;target.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    if not (target/member.name).resolve().is_relative_to(target) or member.issym() or member.islnk():
                        raise ValueError('Unsafe archive member')
                for member in archive.getmembers():
                    dest=target/member.name
                    if member.isdir():
                        dest.mkdir(parents=True,exist_ok=True)
                    elif member.isfile():
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        with archive.extractfile(member) as stream:
                            dest.write_bytes(stream.read())
                        dest.chmod(member.mode & 0o777)
                    else:
                        raise ValueError('Unsupported archive member')
    for patch in pins['patch_order']:
        args=['patch','-d',output/'src/x265','-p1','--forward','--batch','--fuzz=0',
              '-i',ROOT/'third_party/x265/patches'/patch]
        logged([*args,'--dry-run'])
        logged(args)
    built={}
    timing={}
    for label,source in [('patched','x265'),('stock','x265-stock')]:
        started=time.monotonic()
        target=output/label;install=target/'install';shim=target/'shim'
        logged(['cmake','-S',output/'src'/source/'source','-B',target/'x265','-G','Unix Makefiles',
            '-DCMAKE_C_COMPILER=gcc','-DCMAKE_CXX_COMPILER=g++','-DCMAKE_BUILD_TYPE=Release',
            f'-DCMAKE_INSTALL_PREFIX={install}','-DLIB_INSTALL_DIR=lib','-DCMAKE_INSTALL_LIBDIR=lib',
            '-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DHIGH_BIT_DEPTH=OFF','-DMAIN12=OFF',
            '-DLINKED_10BIT=OFF','-DLINKED_12BIT=OFF','-DENABLE_SHARED=ON','-DENABLE_CLI=OFF',
            '-DENABLE_PIC=ON','-DEXPORT_C_API=ON','-DENABLE_ASSEMBLY=ON','-DENABLE_LIBNUMA=ON',
            f'-DNASM_EXECUTABLE={executables["nasm"]}',f'-DCMAKE_ASM_NASM_COMPILER={executables["nasm"]}',
            '-DCMAKE_ASM_NASM_FLAGS=-w-macro-params-legacy'])
        logged(['cmake','--build',target/'x265','--parallel',jobs]);logged(['cmake','--install',target/'x265'])
        library=install/'lib/libx265.so'
        logged(['cmake','-S',ROOT/'src/prism_v2/codec/native','-B',shim,'-G','Unix Makefiles',
            '-DCMAKE_C_COMPILER=gcc','-DCMAKE_BUILD_TYPE=Release',f'-DX265_INCLUDE_DIR={install}/include',
            f'-DX265_LIBRARY={library}',f'-DCMAKE_BUILD_RPATH={install}/lib'])
        logged(['cmake','--build',shim,'--parallel',jobs])
        env={**os.environ,'PRISM_X265_LIBRARY':str(library),'PRISM_X265_SHIM':str(shim/'libprism_x265.so'),
             'PYTHONPATH':str(ROOT/'src'),'LD_LIBRARY_PATH':str(install/'lib'),'PRISM_GATE0_ASSEMBLY':'ON'}
        probe=run([sys.executable,'-c','import json; from dataclasses import asdict; from prism_v2.codec.x265_bridge import X265Library; print(json.dumps(asdict(X265Library().pin)))'],env=env)
        built[label]={'library':str(library),'shim':str(shim/'libprism_x265.so'),'pin':json.loads(probe)}
        timing[label+'_x265_and_shim']=time.monotonic()-started
    started=time.monotonic()
    wrapper=output/'hm-cxx'
    wrapper.write_text('#!/usr/bin/env bash\nargs=()\nfor a in "$@"; do\n case "$a" in -Werror|-Werror=*) ;; *) args+=("$a");; esac\ndone\nexec g++ "${args[@]}" -Wno-error -std=gnu++98\n')
    wrapper.chmod(0o755)
    hm=output/'src/hm'
    for component in ('lib/TLibCommon','lib/TLibVideoIO','lib/TLibDecoder','lib/TAppCommon','app/TAppDecoder'):
        logged(['make','-C',hm/'build/linux'/component,'-j',jobs,f'CPP={wrapper}','release'])
    decoder=hm/'bin/TAppDecoderStatic'
    timing['hm_decoder']=time.monotonic()-started
    receipt={'builds':built,'sources':pins,'source_archive_sha256':archives,'enable_assembly':True,
        'timing_seconds':timing,
        'compiler':{name:{'path':path,'sha256':sha(path),'version':run([path,'--version'])} for name,path in executables.items() if name in ('gcc','g++','nasm','cmake')},
        'decoders':{'ffmpeg':{'executable':executables['ffmpeg'],'sha256':sha(executables['ffmpeg'])},
                    'hm':{'executable':str(decoder),'sha256':sha(decoder)}},
        'shim_source_sha256':sha(ROOT/'src/prism_v2/codec/native/x265_shim.c'),
        'build_log_sha256':sha(log),'status':'BUILT_UNVERIFIED'}
    (output/'stack.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--x265-source',type=Path,required=True);p.add_argument('--hm-source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--jobs',type=int,default=4)
    args=p.parse_args();build(args.x265_source,args.hm_source,args.output,args.jobs)
