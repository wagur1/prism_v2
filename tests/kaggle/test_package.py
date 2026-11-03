"""Offline package contracts; no subprocess is allowed to contact Kaggle."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'kaggle/job_specs/j0_gate0'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kernel = module_at('j0_kernel', SPEC / 'j0_gate0.py')
package = module_at('j0_package', ROOT / 'kaggle/package.py')


def passing_receipt():
    return {
        'schema_version': 1, 'job': 'j0_gate0', 'status': 'PASS', 'gate0_complete': True,
        'training_authorized': False, 'commit_sha': 'a' * 40,
        'started_at': '2026-11-04T00:00:00+00:00', 'finished_at': '2026-11-04T00:01:00+00:00',
        'elapsed_seconds': 60., 'enable_assembly': True,
        'checks': {name: {'status': 'PASS', 'detail': 'verified artifact'} for name in kernel.REQUIRED_CHECKS},
        'stages': {name: {'status': 'PASS', 'seconds': 1.} for name in kernel.REQUIRED_STAGES},
        'patch_order': list(kernel.PATCH_ORDER), 'patch_shas': dict.fromkeys(kernel.PATCH_ORDER, 'b' * 64),
        'binaries': {name: {'path': '/build/' + name, 'sha256': 'c' * 64} for name in kernel.BINARY_NAMES},
        'pinned_source_sha256': 'd' * 64, 'source_commits': {'x265': 'e' * 40, 'hm': 'f' * 40},
        'logs': {name: {'path': '/runs/' + name, 'sha256': 'a' * 64} for name in ('human', 'machine')},
        'stack': {'path': '/stack.json', 'sha256': 'a' * 64},
        'f1': {'path': '/f1.json', 'sha256': 'a' * 64},
        'pytest': {'passed': 3, 'skipped': 0, 'junit_sha256': 'a' * 64},
    }


class ReceiptTests(unittest.TestCase):
    def test_pass_requires_complete_evidence(self):
        self.assertIs(kernel.validate_receipt(receipt := passing_receipt()), receipt)
        mutations = [
            lambda r: r['checks'].pop('warped_qg_partial_cells'),
            lambda r: r['checks']['sei_round_trip'].update(status='SKIP'),
            lambda r: r['checks']['sign_plus6'].update(status='FAIL'),
            lambda r: r['stages']['build_stack'].update(status='FAIL'),
            lambda r: r['stages']['build_stack'].update(seconds=float('nan')),
            lambda r: r['stages']['f1'].update(seconds=-1),
            lambda r: r['binaries'].pop('stock_library'),
            lambda r: r['binaries']['hm'].update(sha256='not-a-hash'),
            lambda r: r.update(commit_sha=None),
            lambda r: r.update(training_authorized=True),
            lambda r: r.update(enable_assembly=False),
            lambda r: r.update(gate0_complete=False),
            lambda r: r.update(patch_order=list(reversed(kernel.PATCH_ORDER))),
            lambda r: r['patch_shas'].pop(kernel.PATCH_ORDER[0]),
            lambda r: r['logs'].pop('machine'),
            lambda r: r.pop('f1'),
            lambda r: r['pytest'].update(skipped=1),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                receipt = copy.deepcopy(passing_receipt())
                mutate(receipt)
                with self.assertRaises(ValueError):
                    kernel.validate_receipt(receipt)

    def test_failure_always_writes_valid_receipt_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = kernel.Runner(tmp)
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                with runner.stage('prerequisites'):
                    raise RuntimeError('fixture failure')
            self.assertEqual(runner.finish('fixture failure'), 1)
            receipt = json.loads(runner.receipt_path.read_text())
            kernel.validate_receipt(receipt)
            self.assertEqual(receipt['status'], 'FAIL')
            self.assertTrue(all(c['status'] == 'FAIL' for c in receipt['checks'].values()))
            self.assertIsNone(receipt['commit_sha'])
            for artifact in receipt['logs'].values():
                self.assertEqual(kernel.sha256(artifact['path']), artifact['sha256'])
            events = [json.loads(line) for line in runner.events_path.read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'final')
            self.assertTrue(any(e['event'] == 'stage_end' and e['status'] == 'FAIL' for e in events))
            with self.assertRaisesRegex(ValueError, 'fresh'):
                kernel.Runner(tmp)

    def test_success_without_checks_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = kernel.Runner(tmp)
            self.assertEqual(runner.finish(), 1)
            self.assertFalse(json.loads(runner.receipt_path.read_text())['gate0_complete'])


class PatchTests(unittest.TestCase):
    def test_real_patch_bytes_match_pins(self):
        pins = json.loads((ROOT / 'third_party/x265/PINNED_SOURCE.json').read_text())
        self.assertEqual(kernel.verify_patch_shas(pins, ROOT / 'third_party/x265/patches'), pins['patches'])

    def test_tamper_second_patch_missing_patch_and_reorder_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pins = {'patch_order': list(kernel.PATCH_ORDER), 'patches': {}}
            for name in kernel.PATCH_ORDER:
                raw = name.encode()
                (root / name).write_bytes(raw)
                pins['patches'][name] = hashlib.sha256(raw).hexdigest()
            kernel.verify_patch_shas(pins, root)
            second = root / kernel.PATCH_ORDER[1]
            second.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                kernel.verify_patch_shas(pins, root)
            second.unlink()
            with self.assertRaises(FileNotFoundError):
                kernel.verify_patch_shas(pins, root)
            pins['patch_order'].reverse()
            with self.assertRaisesRegex(ValueError, 'order'):
                kernel.verify_patch_shas(pins, root)


class PackageTests(unittest.TestCase):
    def test_real_job_cpu_internet_and_print_only(self):
        with patch('subprocess.run', side_effect=AssertionError('No launch allowed')), \
             patch('subprocess.Popen', side_effect=AssertionError('No launch allowed')):
            metadata = package.validate_job_spec(SPEC)
            command = package.push_command(SPEC, Path('wrapper with spaces/krun.py'))
        self.assertFalse(metadata['enable_gpu'])
        self.assertFalse(metadata['enable_tpu'])
        self.assertTrue(metadata['enable_internet'])
        self.assertEqual(metadata['dataset_sources'], [])
        self.assertIn('kernels push -p', command)
        self.assertIn('krun.py', command)

    def test_secret_tripwires_do_not_echo_secrets(self):
        examples = ['gh' + 'p_' + 'a' * 36, 'github_' + 'pat_' + 'b' * 35,
                    'KGA' + 'T_' + 'z' * 32, '"key": "' + 'a' * 32 + '"',
                    'KAGGLE_API_TOKEN = "' + 'b' * 40 + '"',
                    'Authorization: Bearer ' + 'c' * 32,
                    'https://user:' + 'password' + '@example.org/repo.git']
        for example in examples:
            with self.subTest(example=examples.index(example)):
                hits = package.secret_scan(example)
                self.assertTrue(hits)
                self.assertNotIn(example, str(hits))
        self.assertFalse(package.secret_scan('https://github.com/wagur1/prism_v2.git'))

    def test_invalid_metadata_missing_script_escape_and_secret_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = json.loads((SPEC / 'kernel-metadata.json').read_text())
            target = root / 'kernel-metadata.json'
            target.write_text('{')
            with self.assertRaises(ValueError):
                package.validate_job_spec(root)
            target.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'exist'):
                package.validate_job_spec(root)
            (root / metadata['code_file']).write_text('print("hello")')
            package.validate_job_spec(root)
            (root / 'incidental.txt').write_text('gh' + 'p_' + 's' * 36)
            with self.assertRaisesRegex(ValueError, 'tripwire') as exc:
                package.validate_job_spec(root)
            self.assertNotIn('s' * 36, str(exc.exception))
            (root / 'incidental.txt').unlink()
            metadata['code_file'] = '../outside.py'
            target.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'inside'):
                package.validate_job_spec(root)


class PytestReportTests(unittest.TestCase):
    def test_no_skip_or_missing_native_test_can_pass(self):
        names = ['test_sign_controls_identity_and_two_decoders',
                 'test_native_geometry_sei_decoder_match_and_baseline_absence',
                 'test_native_warped_qg_acceptance']
        def xml(names, status=''):
            return '<testsuites><testsuite>' + ''.join(
                f'<testcase classname="tests.codec.test_native.NativeTests" name="{name}">{status}</testcase>'
                for name in names) + '</testsuite></testsuites>'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'junit.xml'
            path.write_text(xml(names))
            self.assertEqual(kernel.verify_pytest_report(path)['passed'], 3)
            for report in (xml(names, '<skipped/>'), xml(names, '<error/>'), xml(names, '<failure/>'),
                           xml(names[:-1]), '<testsuites/>'):
                path.write_text(report)
                with self.assertRaises(ValueError):
                    kernel.verify_pytest_report(path)


if __name__ == '__main__':
    unittest.main()
