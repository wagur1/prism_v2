"""Standalone Kaggle CPU entry point. Upload this script and metadata only.

No local imports before cloning public main. Network is used only for public
sources and dependencies. The auditor launches; importing this module is inert.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone

REPO_URL = 'https://github.com/wagur1/prism_v2.git'
PATCH_ORDER = ('x265_residual_patch.patch', 'x265_residual_telemetry.patch')
F1_CHECKS = (
    'sign_plus6', 'sign_minus6', 'sign_checkerboard', 'zero_map_identity',
    'stock_m2_sei_free', 'sei_round_trip', 'warped_qg_partial_cells',
    'two_decoder_equality', 'quantized_map_validity', 'box_coordinate_round_trip',
)
REQUIRED_CHECKS = ('patch_sha256', 'binary_provenance', 'native_codec_pytest', *F1_CHECKS)
REQUIRED_STAGES = ('prerequisites', 'clone_repo', 'python_dependencies', 'verify_patches',
                   'clone_x265', 'clone_hm', 'build_stack', 'native_codec_pytest', 'f1')
BINARY_NAMES = ('patched_library', 'patched_shim', 'stock_library', 'stock_shim', 'ffmpeg', 'hm')
MAX_SECONDS = 8700  # 145 minutes leaves time to finalize below the 2.5 h target.


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_patch_shas(pins, patch_dir):
    """Verify *both* patches before any application, and reject reordered pins."""
    if pins.get('patch_order') != list(PATCH_ORDER) or set(pins.get('patches', {})) != set(PATCH_ORDER):
        raise ValueError('Pinned patch order/set differs from residual then telemetry')
    verified = {}
    for name in PATCH_ORDER:
        expected = pins['patches'][name]
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError(f'Invalid SHA-256 pin: {name}')
        actual = sha256(Path(patch_dir) / name)
        if actual != expected:
            raise ValueError(f'Patch SHA-256 mismatch: {name}; abort before applying patches')
        verified[name] = actual
    return verified


def validate_receipt(receipt):
    """Version 1 receipt schema and fail-closed invariants (stdlib only)."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def digest(value):
        return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

    def seconds(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    require(receipt.get('schema_version') == 1 and receipt.get('job') == 'j0_gate0', 'Unknown receipt schema')
    require(receipt.get('status') in ('PASS', 'FAIL'), 'Receipt must have a final status')
    passed = receipt['status'] == 'PASS'
    require(type(receipt.get('gate0_complete')) is bool and receipt['gate0_complete'] == passed,
            'Gate completion disagrees with status')
    require(receipt.get('training_authorized') is False, 'Receipt must not authorize training')
    commit = receipt.get('commit_sha')
    require((not passed and commit is None) or isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit),
            'Invalid repository commit SHA')
    require(isinstance(receipt.get('started_at'), str) and isinstance(receipt.get('finished_at'), str),
            'Missing timestamps')
    require(seconds(receipt.get('elapsed_seconds')), 'Invalid total timing')
    checks = receipt.get('checks', {})
    require(set(checks) == set(REQUIRED_CHECKS), 'Incomplete receipt check set')
    for name, check in checks.items():
        require(check.get('status') in ('PASS', 'FAIL') and isinstance(check.get('detail'), str)
                and bool(check['detail']), f'Invalid check: {name}')
    stages = receipt.get('stages', {})
    require(set(stages) == set(REQUIRED_STAGES), 'Incomplete stage set')
    for name, stage in stages.items():
        require(stage.get('status') in ('PASS', 'FAIL') and seconds(stage.get('seconds')), f'Invalid stage: {name}')
    patches = receipt.get('patch_shas', {})
    require(set(patches).issubset(PATCH_ORDER) and all(digest(v) for v in patches.values()), 'Invalid patch hashes')
    binaries = receipt.get('binaries', {})
    require(set(binaries).issubset(BINARY_NAMES), 'Unexpected binary')
    for binary in binaries.values():
        require(digest(binary.get('sha256')) and isinstance(binary.get('path'), str) and bool(binary['path']),
                'Invalid binary provenance')
    logs = receipt.get('logs', {})
    require(set(logs) == {'human', 'machine'}, 'Missing logs')
    for log in logs.values():
        require(isinstance(log.get('path'), str) and bool(log['path']) and digest(log.get('sha256')), 'Invalid log artifact')
    if passed:
        require(all(c['status'] == 'PASS' for c in checks.values()), 'PASS with failed/missing checks')
        require(all(s['status'] == 'PASS' for s in stages.values()), 'PASS with failed/missing stages')
        require(set(patches) == set(PATCH_ORDER) and set(binaries) == set(BINARY_NAMES), 'PASS lacks build provenance')
        require(digest(receipt.get('pinned_source_sha256')), 'PASS lacks source manifest hash')
        require(set(receipt.get('source_commits', {})) == {'x265', 'hm'} and
                all(re.fullmatch('[0-9a-f]{40}', v) for v in receipt['source_commits'].values()), 'PASS lacks source commits')
        require(receipt.get('patch_order') == list(PATCH_ORDER) and receipt.get('enable_assembly') is True,
                'PASS lacks ordered patches/assembly ON')
        for name in ('stack', 'f1'):
            artifact = receipt.get(name, {})
            require(isinstance(artifact.get('path'), str) and bool(artifact['path']) and digest(artifact.get('sha256')),
                    f'PASS lacks {name} artifact')
        tests = receipt.get('pytest', {})
        require(type(tests.get('passed')) is int and tests['passed'] >= 3 and tests.get('skipped') == 0
                and digest(tests.get('junit_sha256')), 'PASS lacks successful native pytest evidence')
    return receipt


def verify_pytest_report(path):
    """Exit 0 alone is insufficient: no skips/xfails, and native cases must run."""
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    for suite in root.iter('testsuite'):
        if any(int(suite.get(key, '0')) for key in ('failures', 'errors', 'skipped')):
            raise ValueError('Pytest suite contains failures/errors/skips')
    if not cases or any(case.find(tag) is not None for case in cases for tag in ('failure', 'error', 'skipped')):
        raise ValueError('Pytest did not pass every collected case (skips/xfails fail J0)')
    required = {'test_sign_controls_identity_and_two_decoders',
                'test_native_geometry_sei_decoder_match_and_baseline_absence',
                'test_native_warped_qg_acceptance'}
    native = {case.get('name') for case in cases if case.get('classname', '').endswith('NativeTests')}
    if not required.issubset(native):
        raise ValueError('Pytest native acceptance cases missing')
    return {'passed': len(cases), 'skipped': 0, 'native_cases': sorted(native)}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Runner:
    def __init__(self, working):
        self.working = Path(working)
        self.started = time.monotonic()
        self.deadline = self.started + MAX_SECONDS
        self.log_path = self.working / 'j0_gate0.log'
        self.events_path = self.working / 'runs/j0_gate0.events.jsonl'
        self.receipt_path = self.working / 'runs/j0_gate0_receipt.json'
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite a prior receipt/log and accidentally mix evidence.
        if any(p.exists() for p in (self.log_path, self.events_path, self.receipt_path)):
            raise ValueError('J0 needs a fresh /kaggle/working output directory')
        self.log_path.touch()
        self.events_path.touch()
        self.receipt = {
            'schema_version': 1, 'job': 'j0_gate0', 'status': 'FAIL',
            'gate0_complete': False, 'training_authorized': False,
            'started_at': utc_now(), 'finished_at': None, 'elapsed_seconds': 0,
            'commit_sha': None, 'source_commits': {}, 'patch_shas': {}, 'binaries': {},
            'checks': {name: {'status': 'FAIL', 'detail': 'Not completed'} for name in REQUIRED_CHECKS},
            'stages': {name: {'status': 'FAIL', 'seconds': 0, 'detail': 'Not completed'} for name in REQUIRED_STAGES},
        }
        self.environment = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'PYTHONUNBUFFERED': '1',
                            'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'OMP_NUM_THREADS': '1',
                            'OPENBLAS_NUM_THREADS': '1', 'PRISM_GATE0_ASSEMBLY': 'ON'}
        for key in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PRISM_X265_QP_TRACE', 'PRISM_X265_RC_TELEMETRY',
                    'PRISM_X265_SHIM', 'PRISM_X265_LIBRARY', 'PRISM_CODEC_STACK'):
            self.environment.pop(key, None)

    def event(self, event, **fields):
        row = {'time': utc_now(), 'elapsed_seconds': round(time.monotonic() - self.started, 3),
               'event': event, **fields}
        with self.events_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')

    def progress(self, message):
        line = f'[J0 {utc_now()}] {message}'
        print(line, flush=True)
        with self.log_path.open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')

    @contextmanager
    def stage(self, name):
        started = time.monotonic()
        self.progress(f'START {name}')
        self.event('stage_start', stage=name)
        stage = self.receipt['stages'][name]
        try:
            yield
            stage.update(status='PASS', detail='Completed')
        except BaseException as exc:
            stage.update(status='FAIL', detail=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            stage['seconds'] = round(time.monotonic() - started, 3)
            self.event('stage_end', stage=name, **stage)
            self.progress(f"{stage['status']} {name} ({stage['seconds']} s)")

    def run(self, argv, *, cwd=None, timeout=1800, capture=False):
        argv = [str(a) for a in argv]
        started = time.monotonic()
        limit = min(self.deadline, started + timeout)
        if started >= limit:
            raise TimeoutError('J0 total runtime budget exhausted')
        self.event('command_start', argv=argv, cwd=str(cwd or self.working))
        with self.log_path.open('ab', buffering=0) as log:
            log.write(('COMMAND ' + repr(argv) + '\n').encode())
            offset = log.tell()
            process = subprocess.Popen(argv, cwd=cwd or self.working, env=self.environment,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while True:
                    try:
                        process.wait(timeout=max(.01, min(30, limit - time.monotonic())))
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() >= limit:
                            raise TimeoutError(f'Command timeout: {argv[0]}')
                        self.progress(f'RUNNING {argv[0]} ({int(time.monotonic() - started)} s)')
                        self.event('heartbeat', command=argv[0])
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                self.event('command_aborted', argv=argv, returncode=process.returncode,
                           seconds=round(time.monotonic() - started, 3))
                raise
            end = log.tell()
        self.event('command_end', argv=argv, returncode=process.returncode,
                   seconds=round(time.monotonic() - started, 3))
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, argv)
        if capture:
            with self.log_path.open('rb') as stream:
                stream.seek(offset)
                return stream.read(end - offset).decode('utf-8').strip()

    def check(self, name, detail):
        self.receipt['checks'][name] = {'status': 'PASS', 'detail': detail}
        self.event('check', check=name, status='PASS', detail=detail)

    def prerequisites(self):
        if sys.platform != 'linux' or sys.version_info < (3, 10):
            raise ValueError('J0 requires Linux and Python >= 3.10')
        packages = {'git': 'git', 'patch': 'patch', 'gcc': 'build-essential', 'g++': 'build-essential',
                    'make': 'build-essential', 'cmake': 'cmake', 'nasm': 'nasm', 'ffmpeg': 'ffmpeg'}
        missing = {package for executable, package in packages.items() if not shutil.which(executable)}
        if not Path('/usr/include/numa.h').is_file():
            missing.add('libnuma-dev')
        if missing:
            apt = [] if os.geteuid() == 0 else ['sudo', '-n']
            self.run([*apt, 'apt-get', 'update'], timeout=600)
            self.run([*apt, 'env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install',
                      '-y', '--no-install-recommends', *sorted(missing)], timeout=900)

    def clone_pin(self, name, pin, destination):
        if not re.fullmatch('[0-9a-f]{40}', pin['commit']):
            raise ValueError(f'Invalid {name} commit pin')
        expected_urls = {'x265': 'https://bitbucket.org/multicoreware/x265_git.git',
                         'hm': 'https://vcgit.hhi.fraunhofer.de/jvet/HM.git'}
        if pin['url'] != expected_urls[name]:
            raise ValueError(f'Unexpected {name} upstream')
        self.run(['git', 'init', destination])
        self.run(['git', '-C', destination, 'remote', 'add', 'origin', pin['url']])
        self.run(['git', '-c', 'credential.helper=', '-C', destination, 'fetch', '--depth', '1',
                  'origin', pin['commit']], timeout=600)
        self.run(['git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD'])
        actual = self.run(['git', '-C', destination, 'rev-parse', 'HEAD'], capture=True)
        if actual != pin['commit']:
            raise ValueError(f'Unpinned {name} source')
        self.receipt['source_commits'][name] = actual

    def execute(self):
        repo = self.working / 'prism_v2'
        sources = self.working / 'j0_sources'
        build = self.working / 'j0_stack'
        f1_output = self.working / 'runs/j0_f1'
        with self.stage('prerequisites'):
            self.prerequisites()
        with self.stage('clone_repo'):
            self.run(['git', '-c', 'credential.helper=', 'clone', '--depth', '1', '--single-branch',
                      '--branch', 'main', REPO_URL, repo], timeout=600)
            self.receipt['commit_sha'] = self.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture=True)
            self.environment['PYTHONPATH'] = str(repo / 'src')
        with self.stage('python_dependencies'):
            self.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                      '--no-input', 'pytest>=8,<10', 'numpy>=1.24,<3'], timeout=600)
        with self.stage('verify_patches'):
            manifest = repo / 'third_party/x265/PINNED_SOURCE.json'
            pins = json.loads(manifest.read_text(encoding='utf-8'))
            if pins.get('enable_assembly') is not True:
                raise ValueError('Assembly ON is mandatory')
            self.receipt['pinned_source_sha256'] = sha256(manifest)
            self.receipt['patch_shas'] = verify_patch_shas(pins, manifest.parent / 'patches')
            self.receipt['patch_order'] = list(PATCH_ORDER)
            self.receipt['enable_assembly'] = True
            self.check('patch_sha256', 'Both patch bytes match PINNED_SOURCE.json before application')
        sources.mkdir(exist_ok=False)
        for name in ('x265', 'hm'):
            with self.stage(f'clone_{name}'):
                self.clone_pin(name, pins[name], sources / name)
        with self.stage('build_stack'):
            # The repo builder rechecks source commits and patch SHAs, archives
            # clean sources, applies residual then telemetry with --fuzz=0,
            # builds stock/patched x265 + header shims and HM TAppDecoderStatic.
            # Its flags match v1, including assembly ON and HM C++98 diagnostics.
            self.run([sys.executable, '-u', repo / 'scripts/build_codec.py',
                      '--x265-source', sources / 'x265', '--hm-source', sources / 'hm',
                      '--output', build, '--jobs', min(4, os.cpu_count() or 1)], timeout=4500)
            stack_path = build / 'stack.json'
            stack = json.loads(stack_path.read_text())
            if stack.get('enable_assembly') is not True or stack['sources'] != pins:
                raise ValueError('Build stack source/assembly provenance mismatch')
            for label in ('stock', 'patched'):
                binary = stack['builds'][label]
                if binary['pin']['enable_assembly'] is not True:
                    raise ValueError('Assembly OFF build')
                cache = (build / label / 'x265/CMakeCache.txt').read_text()
                if 'ENABLE_ASSEMBLY:BOOL=ON' not in cache:
                    raise ValueError('CMake did not configure assembly ON')
                for kind in ('library', 'shim'):
                    actual = sha256(binary[kind])
                    if actual != binary['pin'][f'{kind}_sha256']:
                        raise ValueError('Built binary hash mismatch')
                    self.receipt['binaries'][f'{label}_{kind}'] = {'path': binary[kind], 'sha256': actual}
            for name, decoder in stack['decoders'].items():
                actual = sha256(decoder['executable'])
                if actual != decoder['sha256']:
                    raise ValueError('Decoder hash mismatch')
                self.receipt['binaries'][name] = {'path': decoder['executable'], 'sha256': actual}
            self.receipt['stack'] = {'path': str(stack_path), 'sha256': sha256(stack_path)}
            self.receipt['build_timing_seconds'] = stack['timing_seconds']
            self.environment['PRISM_CODEC_STACK'] = str(stack_path)
            self.check('binary_provenance', 'Source, patch, assembly, encoder/shim and decoder hashes verified')
        with self.stage('native_codec_pytest'):
            junit = self.working / 'runs/j0_pytest.xml'
            self.run([sys.executable, '-m', 'pytest', 'tests/codec', 'tests/geometry', 'tests/evaluation',
                      '-ra', '--strict-markers', f'--junitxml={junit}'], cwd=repo, timeout=900)
            self.receipt['pytest'] = verify_pytest_report(junit)
            self.receipt['pytest']['junit_sha256'] = sha256(junit)
            self.check('native_codec_pytest', 'Every codec/geometry/evaluation case passed; no skips or xfails')
        with self.stage('f1'):
            self.run([sys.executable, '-u', repo / 'scripts/gate0.py', '--f1', '--stack', stack_path,
                      '--output', f1_output], cwd=repo, timeout=4500)
            report_path = f1_output / 'f1.json'
            report = json.loads(report_path.read_text())
            if report.get('status') != 'PASS' or report.get('gate0_complete') is not True or set(report.get('checks', {})) != set(F1_CHECKS):
                raise ValueError('Incomplete F1 receipt')
            if report.get('crfs') != [20, 24, 28, 32, 36] or report.get('control_dimensions') != [1920, 1080]:
                raise ValueError('Unexpected F1 grid/resolution')
            if report.get('net_effect_crfs') != [20]:
                raise ValueError('F1 sign checks must use the ratified CRF20 fixture')
            expected = {(crf, arm) for crf in report['crfs'] for arm in ('M1', 'M2', 'R', 'QR')}
            if len(report.get('retarget_runs', [])) != len(expected) or {(r['crf'], r['arm']) for r in report['retarget_runs']} != expected:
                raise ValueError('Incomplete/duplicate retarget fixture coverage')
            for name in F1_CHECKS:
                if report['checks'][name]['status'] != 'PASS':
                    raise ValueError(f'F1 check failed: {name}')
                self.check(name, f'{report_path}: {report["checks"][name]["detail"]}')
            self.receipt['f1'] = {'path': str(report_path), 'sha256': sha256(report_path),
                                  'timing_seconds': report['timing_seconds']}

    def finish(self, error=None):
        passed = (error is None and all(c['status'] == 'PASS' for c in self.receipt['checks'].values())
                  and all(s['status'] == 'PASS' for s in self.receipt['stages'].values()))
        self.receipt.update(status='PASS' if passed else 'FAIL', gate0_complete=passed,
                            finished_at=utc_now(), elapsed_seconds=round(time.monotonic() - self.started, 3))
        if error:
            self.receipt['error'] = error
        self.progress(f"FINAL {self.receipt['status']}; receipt={self.receipt_path}")
        self.event('final', status=self.receipt['status'], error=error, checks=self.receipt['checks'])
        self.receipt['logs'] = {name: {'path': str(path), 'sha256': sha256(path)} for name, path in
                                (('human', self.log_path), ('machine', self.events_path))}
        validate_receipt(self.receipt)
        temporary = self.receipt_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.receipt, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(self.receipt_path)
        return 0 if passed else 1


def main():
    runner = Runner('/kaggle/working')
    error = None
    def interrupted(signum, _frame):
        raise InterruptedError(f'J0 interrupted by signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        runner.execute()
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        with runner.log_path.open('a', encoding='utf-8') as stream:
            stream.write(traceback.format_exc())
    return runner.finish(error)


if __name__ == '__main__':
    sys.exit(main())
