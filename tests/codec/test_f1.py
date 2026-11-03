import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from prism_v2.codec.f1 import F1_CHECKS, retarget_fixture, run_f1, run_retarget_fixture, verify_warped_telemetry
from prism_v2.codec.ffmpeg_stream import frame_bytes
from prism_v2.codec.fixtures import FixtureNeedsVerify


class F1Tests(unittest.TestCase):
    def test_retarget_fixture_partial_cells_and_signed_offsets(self):
        signal, offsets, yuv = retarget_fixture()
        self.assertEqual((signal.geometry.source_width, signal.geometry.source_height), (130, 98))
        self.assertEqual((signal.geometry.visible_width, signal.geometry.visible_height), (113, 65))
        self.assertEqual(len(yuv), frame_bytes(128, 80))
        self.assertEqual(offsets.shape, (8, 8))
        self.assertEqual(offsets.shape[1], (signal.coded_width + 15) // 16)
        self.assertGreaterEqual(min(signal.coded_width, signal.coded_height), 64)
        self.assertNotEqual(signal.coded_height % 64, 0)
        self.assertTrue((offsets < 0).any() and (offsets > 0).any())
        self.assertTrue((np.abs(offsets) < 6).any())

    def test_native_telemetry_rejects_wrong_offsets_and_missing_edge_qg(self):
        _, offsets, _ = retarget_fixture()
        fields = ['record_type', 'frame', 'slice_type', 'rc_mode', 'qg_x', 'qg_y',
                  'qg_size', 'requested_offset', 'has_residual', 'skip']
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y in range(5):
            for x in range(8):
                rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                                 qg_x=x * 16, qg_y=y * 16, qg_size=16,
                                 requested_offset=float(offsets[y, x]), has_residual=1, skip=0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            def write():
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader()
                    writer.writerows(rows)
            write()
            self.assertEqual(verify_warped_telemetry(path, offsets)['covered_qgs'], 40)
            rows[-1]['requested_offset'] = 0
            write()
            with self.assertRaisesRegex(ValueError, 'differ'):
                verify_warped_telemetry(path, offsets)
            rows.pop()
            write()
            with self.assertRaisesRegex(ValueError, 'coverage'):
                verify_warped_telemetry(path, offsets)

    def test_patch_qg_parent_means_duplicates_and_corroborating_edges(self):
        # Distinct values in both axes expose stride errors and averaging over
        # the leaf (x,y) rather than its reported QG parent.
        offsets = np.linspace(-6, 6, 64, dtype=np.float32).reshape(8, 8)
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y in range(5):
            for x in range(8):
                rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                    x=x*16+8, y=y*16+8, qg_x=x*16, qg_y=y*16, qg_size=16,
                    requested_offset=float(offsets[y,x]), has_residual=1, skip=0))
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            def verify(data):
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader(); writer.writerows(data)
                return verify_warped_telemetry(path, offsets)
            # v1 repeats the parent's mean for every committed sub-QG leaf.
            self.assertEqual(verify(rows + [dict(rows[1], x=0, y=0)])['direct_edge_qgs'], 22)
            interior = [r for r in rows if not (r.get('qg_x') in (32,48) and r.get('qg_y') in (32,48))]
            parent = dict(rows[1], x=32, y=32, qg_x=32, qg_y=32, qg_size=32,
                          requested_offset=float(offsets[2:4,2:4].astype(float).mean()))
            self.assertEqual(verify(interior + [parent])['covered_qgs'], 40)
            with self.assertRaisesRegex(ValueError, 'differ'):
                verify(interior + [dict(parent, requested_offset=float(offsets[2,2]))])
            # QG16 footprint means corroborate, but do not claim direct edges.
            no_corner = [r for r in rows if not (r.get('qg_x') in (0,16) and r.get('qg_y') in (0,16))]
            corner = dict(parent, x=0, y=0, qg_x=0, qg_y=0,
                          requested_offset=float(offsets[:2,:2].astype(float).mean()))
            trace = verify(no_corner + [corner])
            self.assertEqual(trace['covered_qgs'], 40)
            self.assertEqual(trace['direct_edge_qgs'], 19)
            self.assertEqual(trace['evidence'], 'cu_mean')
            # Mutate each perimeter QG separately; no edge may be ignored.
            for row in rows[1:]:
                if row['qg_x'] in (0,112) or row['qg_y'] in (0,64):
                    bad = [dict(r) for r in rows]
                    bad[rows.index(row)]['requested_offset'] += 1
                    with self.assertRaisesRegex(ValueError, 'differ'):
                        verify(bad)
            with self.assertRaisesRegex(FixtureNeedsVerify, 'strides'):
                verify_warped_telemetry(path, offsets, width=112)

    def test_qg64_exact_rows_include_every_partial_and_edge_qg(self):
        offsets = np.array([[-4., -1.], [2., 5.]])
        rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
        for y, x in np.ndindex(offsets.shape):
            rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                x=x*64+8, y=y*64+8, qg_x=x*64, qg_y=y*64, qg_size=64,
                requested_offset=offsets[y,x], has_residual=1, skip=0))
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'qg64.csv'
            def verify(data, grid=offsets):
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fields)
                    writer.writeheader(); writer.writerows(data)
                return verify_warped_telemetry(path, grid, width=128, height=80, qg_size=64)
            trace = verify(rows + [dict(rows[-1], x=120)])
            self.assertIs(trace['requested_offsets_verified'], True)
            self.assertEqual(trace['evidence'], 'per_qg')
            self.assertEqual(trace['covered_qgs'], 4)
            self.assertEqual(trace['direct_qgs'], 4)
            self.assertEqual(trace['direct_edge_qgs'], 4)
            self.assertEqual(trace['partial_qgs'], 2)
            # Every block, including both bottom partial CTUs, is mandatory.
            for i in range(1, len(rows)):
                with self.subTest(qg=i):
                    with self.assertRaisesRegex(ValueError, 'coverage'):
                        verify(rows[:i] + rows[i+1:])
                    for delta in (2e-6, float('nan'), float('inf')):
                        bad = dict(rows[i], requested_offset=rows[i]['requested_offset'] + delta)
                        # A correct duplicate must not hide a corrupt row.
                        with self.assertRaisesRegex(ValueError, 'differ'):
                            verify(rows + [bad])
            with self.assertRaisesRegex(ValueError, 'size 64'):
                verify(rows + [dict(rows[1], qg_size=32)])
            with self.assertRaisesRegex(ValueError, 'Invalid warped QG buffer'):
                verify(rows, np.zeros((8, 8)))
            with self.assertRaisesRegex(ValueError, 'coverage/residual'):
                verify([rows[0]] + [dict(r, has_residual=0) for r in rows[1:]])
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                verify([])

    def test_retarget_requires_both_passes_and_fixture_only_override(self):
        from tests.codec.test_sei import AU
        _, adapter, _ = retarget_fixture()
        stack = {'enable_assembly': True,
                 'builds': {'patched': {'shim': 's', 'library': 'l', 'pin': {'enable_assembly': True}}},
                 'decoders': {'ffmpeg': {}, 'hm': {}}}
        seen = []
        mode = {'drop_qg64': False, 'bad_qg16': False}
        def encoder(_codec, width, height, config, _csv, **kwargs):
            size = kwargs.get('qg_size_override', 16)
            self.assertIn(f'qg-size={size}', config.options(_csv, **kwargs).splitlines())
            seen.append((config.crf, size))
            def encode(_yuv, offsets):
                if offsets is not None:
                    np.testing.assert_array_equal(offsets, adapter)
                    rows = [dict(record_type='frame', frame=0, slice_type='I', rc_mode='CRF')]
                    # Reproduce the patch's clipped parent-footprint means.
                    # QG16 deliberately has no individual edge observations.
                    for y in range(0, height, 64):
                        for x in range(0, width, 64):
                            mean = offsets[y//16:min(y+64,height)//16,
                                           x//16:min(x+64,width)//16].astype(float).mean()
                            rows.append(dict(record_type='cu', frame=0, slice_type='I', rc_mode='CRF',
                                qg_x=x, qg_y=y, qg_size=64, requested_offset=mean,
                                has_residual=1, skip=0))
                    if size == 64 and mode['drop_qg64']:
                        return AU + AU
                    if size == 16 and mode['bad_qg16']:
                        rows[-1]['requested_offset'] += 1
                    fields = list(dict.fromkeys(k for row in rows for k in row))
                    with Path(os.environ['PRISM_X265_RC_TELEMETRY']).open('w', newline='') as stream:
                        writer = csv.DictWriter(stream, fields)
                        writer.writeheader(); writer.writerows(rows)
                return AU if offsets is None else AU + AU
            instance = Mock()
            instance.encode.side_effect = encode
            instance.flush.return_value = b''
            context = Mock()
            context.__enter__ = Mock(return_value=instance)
            context.__exit__ = Mock(return_value=False)
            return context
        with tempfile.TemporaryDirectory() as tmp, \
             patch('prism_v2.codec.f1.X265Library'), patch('prism_v2.codec.f1.BuildPin'), \
             patch('prism_v2.codec.f1.DecoderPin'), patch('prism_v2.codec.f1.verify_decoders') as decode, \
             patch('prism_v2.codec.encoder.X265Encoder', side_effect=encoder), \
             patch.dict(os.environ, {'PRISM_X265_RC_TELEMETRY': 'previous', 'PRISM_X265_QP_TRACE': 'previous'}):
            output = Path(tmp) / 'retarget'
            runs = run_retarget_fixture(output, stack)
            self.assertEqual(len(runs), 22)
            self.assertEqual(seen, [(crf,16) for crf in (20,24,28,32,36) for _ in range(4)] + [(20,64)]*2)
            self.assertEqual(decode.call_count, 22)
            self.assertEqual([(r['arm'],r['crf']) for r in runs if r['qg_size']==64], [('M2',20),('QR',20)])
            reduced = np.load(output / 'offsets_qg64.npy')
            for y, x in np.ndindex(reduced.shape):
                self.assertEqual(reduced[y,x], adapter[y*4:y*4+4,x*4:x*4+4].astype(float).mean())
            for run in runs:
                if run['arm'] in ('M2','QR'):
                    trace = run['warped_telemetry']
                    self.assertIs(trace['requested_offsets_verified'], True)
                    self.assertEqual(trace['direct_edge_qgs'], 4 if run['qg_size']==64 else 0)
            # A missing native QG64 trace and a bad QG16 mean both fail.
            mode['drop_qg64'] = True
            with self.assertRaises(FileNotFoundError):
                run_retarget_fixture(Path(tmp) / 'missing', stack, crfs=(20,))
            mode.update(drop_qg64=False, bad_qg16=True)
            with self.assertRaisesRegex(ValueError, 'differ'):
                run_retarget_fixture(Path(tmp) / 'corrupt', stack, crfs=(20,))
            self.assertEqual(os.environ['PRISM_X265_RC_TELEMETRY'], 'previous')
            self.assertEqual(os.environ['PRISM_X265_QP_TRACE'], 'previous')

    def test_needs_verify_keeps_f1_incomplete(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'f1'
            with patch('prism_v2.codec.f1.run_gate', side_effect=FixtureNeedsVerify('[NEEDS VERIFY] calibration')):
                with self.assertRaises(FixtureNeedsVerify):
                    run_f1(output, {})
            report = json.loads((output / 'f1.json').read_text())
            self.assertEqual(report['status'], 'FAIL')
            self.assertFalse(report['gate0_complete'])
            self.assertTrue(all(c['status'] == 'SKIP' for c in report['checks'].values()))

    def test_control_failure_cannot_leave_a_pass_receipt(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'f1'
            with patch('prism_v2.codec.f1.run_gate', side_effect=ValueError('sign failure')):
                with self.assertRaisesRegex(ValueError, 'sign failure'):
                    run_f1(output, {})
            report = json.loads((output / 'f1.json').read_text())
            self.assertFalse(report['gate0_complete'])
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(set(report['checks']), set(F1_CHECKS))
            self.assertTrue(all(c['status'] == 'FAIL' for c in report['checks'].values()))

    def test_pass_label_without_full_grid_evidence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('prism_v2.codec.f1.run_gate', return_value={'status': 'CODEC_CONTROLS_PASS'}):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    run_f1(Path(tmp) / 'f1', {})
